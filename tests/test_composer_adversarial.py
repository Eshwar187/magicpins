"""Adversarial and boundary tests for the Vera message composer."""

import json
from pathlib import Path
import pytest

from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ActionType
from app.engine.decision import Decision
from app.composer.compose import compose
from app.composer.validators import validate_composed_message, validate_no_urls, validate_customer_privacy

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


@pytest.fixture
def dataset():
    cats = {}
    for p in (DATASET_DIR / "categories").glob("*.json"):
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
            cats[d["slug"]] = CategoryProfile.from_dict(d)

    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        merchants = {m["merchant_id"]: MerchantState.from_dict(m) for m in json.load(f)["merchants"]}

    with open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8") as f:
        customers = {c["customer_id"]: CustomerStateModel.from_dict(c) for c in json.load(f)["customers"]}

    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        triggers = {t["id"]: TriggerState.from_dict(t) for t in json.load(f)["triggers"]}

    return {"categories": cats, "merchants": merchants, "customers": customers, "triggers": triggers}


def test_adversarial_a_missing_supporting_offer_raises_validation_error(dataset):
    """Adversarial A: If an action requires an offer, but supporting_offer is None, composer rejects."""
    cat = dataset["categories"]["restaurants"]
    m = dataset["merchants"]["m_005_pizzajunction_restaurant_delhi"]
    trg = dataset["triggers"]["trg_010_ipl_match_delhi"]

    # Construct synthetic decision claiming delivery promo without an offer
    bad_decision = Decision(
        action=ActionType.PROMOTE_DELIVERY_OFFER.value,
        action_type=ActionType.PROMOTE_DELIVERY_OFFER,
        target_scope="merchant",
        trigger_id=trg.id,
        score=90.0,
        primary_reason="Test delivery promo",
        evidence_facts=(),
        supporting_offer=None,  # Missing!
        next_step="draft_banner",
    )

    with pytest.raises(ValueError, match="UNSUPPORTED_OFFER_CLAIM"):
        compose(bad_decision, cat, m, trg)


def test_adversarial_b_expired_offer_rejected_by_validator(dataset):
    """Adversarial B: Expired offer cannot be validated as a supporting offer."""
    cat = dataset["categories"]["restaurants"]
    m = dataset["merchants"]["m_005_pizzajunction_restaurant_delhi"]
    trg = dataset["triggers"]["trg_010_ipl_match_delhi"]

    expired_decision = Decision(
        action=ActionType.PROMOTE_DELIVERY_OFFER.value,
        action_type=ActionType.PROMOTE_DELIVERY_OFFER,
        target_scope="merchant",
        trigger_id=trg.id,
        score=90.0,
        primary_reason="Test delivery promo",
        evidence_facts=(),
        supporting_offer={"id": "o_exp", "title": "Old Offer", "status": "expired"},
        next_step="draft_banner",
    )

    with pytest.raises(ValueError, match="EXPIRED_OFFER_CLAIM"):
        compose(expired_decision, cat, m, trg)


def test_adversarial_d_missing_customer_name_graceful(dataset):
    """Adversarial D: Customer with no name or anonymous placeholder still composes gracefully."""
    cat = dataset["categories"]["dentists"]
    m = dataset["merchants"]["m_001_drmeera_dentist_delhi"]
    trg = dataset["triggers"]["trg_003_recall_due_priya"]

    anon_cust = CustomerStateModel.from_dict({
        "customer_id": "c_anon_test",
        "merchant_id": m.merchant_id,
        "identity": {"name": "(walk-in, no profile)", "language_pref": "en"},
        "relationship": {"visits_total": 1},
        "state": "lapsed_soft",
        "preferences": {"reminder_opt_in": True},
        "consent": {"opted_in_at": "2025-10-10", "scope": ["recall_reminders"]}
    })

    decision = Decision(
        action=ActionType.CUSTOMER_RECALL.value,
        action_type=ActionType.CUSTOMER_RECALL,
        target_scope="customer",
        trigger_id=trg.id,
        score=90.0,
        primary_reason="Recall due",
        evidence_facts=(),
        supporting_offer=None,
        next_step="confirm_slot",
    )

    msg = compose(decision, cat, m, trg, anon_cust)
    assert msg.action == "send"
    assert "Hi there" in msg.body or "Dr. Meera" in msg.body
    assert "c_anon_test" not in msg.body  # No ID leaked


def test_adversarial_e_missing_merchant_owner_name_graceful(dataset):
    """Adversarial E: Merchant with no owner_first_name falls back cleanly to business name."""
    cat = dataset["categories"]["gyms"]
    gym_no_owner = MerchantState.from_dict({
        "merchant_id": "m_gym_anon",
        "category_slug": "gyms",
        "identity": {
            "name": "Titan Fitness", "city": "Bangalore", "locality": "Whitefield",
            "place_id": "x", "verified": True, "owner_first_name": None
        },
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
    })
    trg = TriggerState.from_dict({
        "id": "trg_seasonal", "scope": "merchant", "kind": "seasonal_perf_dip",
        "source": "internal", "merchant_id": gym_no_owner.merchant_id,
        "payload": {"metric": "views", "delta_pct": -0.30, "is_expected_seasonal": True},
        "urgency": 3, "suppression_key": "season"
    })

    decision = Decision(
        action=ActionType.REFRAME_SEASONAL_DIP.value,
        action_type=ActionType.REFRAME_SEASONAL_DIP,
        target_scope="merchant",
        trigger_id=trg.id,
        score=85.0,
        primary_reason="Seasonal reframe",
        evidence_facts=(),
        supporting_offer=None,
        next_step="retention_challenge",
    )

    msg = compose(decision, cat, gym_no_owner, trg)
    assert msg.action == "send"
    assert "Titan Fitness" in msg.body


def test_adversarial_g_url_policy_enforcement():
    """Adversarial G: Raw URLs in message bodies are rejected by validator."""
    url_body = "Check our offers at https://magicpin.in/deals now!"
    ok, err = validate_no_urls(url_body)
    assert ok is False
    assert "URL_PROHIBITED" in err

    clean_body = "Check our offers on the magicpin app today."
    ok, err = validate_no_urls(clean_body)
    assert ok is True
    assert err is None


def test_adversarial_i_wait_produces_noop_action(dataset):
    """Adversarial I: WAIT decision produces action='wait', empty body, and cta='none'."""
    cat = dataset["categories"]["dentists"]
    m = dataset["merchants"]["m_001_drmeera_dentist_delhi"]
    trg = dataset["triggers"]["trg_001_research_digest_dentists"]

    wait_decision = Decision(
        action=ActionType.WAIT.value,
        action_type=ActionType.WAIT,
        target_scope="merchant",
        trigger_id=trg.id,
        score=10.0,
        primary_reason="Standing down: no proactive intervention justified",
        evidence_facts=(),
        supporting_offer=None,
        next_step=None,
    )

    msg = compose(wait_decision, cat, m, trg)
    assert msg.action == "wait"
    assert msg.body == ""
    assert msg.cta == "none"
    assert msg.send_as == "vera"


def test_adversarial_j_privacy_internal_id_never_leaks():
    """Adversarial J: Internal customer or merchant database IDs must never leak."""
    body_with_leak = "Hi Priya, your record c_001_priya_for_m001 has a recall due."
    ok, err = validate_customer_privacy(body_with_leak, "c_001_priya_for_m001", "m_001_drmeera")
    assert ok is False
    assert "PRIVACY_LEAK" in err

    clean_body = "Hi Priya, Dr. Meera's clinic here — your 6-month cleaning is due."
    ok, err = validate_customer_privacy(clean_body, "c_001_priya_for_m001", "m_001_drmeera")
    assert ok is True


def test_adversarial_l_decision_tampering_composer_obeys_phase2_decision(dataset):
    """Adversarial L: Even if context contains facts tempting action B, composer strictly renders decision A."""
    cat = dataset["categories"]["gyms"]
    m = dataset["merchants"]["m_007_powerhouse_gym_bangalore"]
    trg = dataset["triggers"]["trg_014_seasonal_acquisition_dip_powerhouse"]

    # Force decision to be CURIOUS_ASK rather than REFRAME_SEASONAL_DIP
    forced_decision = Decision(
        action=ActionType.CURIOUS_ASK.value,
        action_type=ActionType.CURIOUS_ASK,
        target_scope="merchant",
        trigger_id=trg.id,
        score=80.0,
        primary_reason="Weekly curious checkin",
        evidence_facts=(),
        supporting_offer=None,
        next_step="inquire_demand",
    )

    msg = compose(forced_decision, cat, m, trg)
    # Composer MUST obey CURIOUS_ASK and not re-infer seasonal dip!
    assert msg.action_type == ActionType.CURIOUS_ASK
    assert msg.template_name == "vera_curious_ask_v1"
    assert "most asked-for this week" in msg.body
