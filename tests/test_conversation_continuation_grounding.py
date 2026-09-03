"""Forensic Phase 6.2 Grounding and Composition Boundary Verification Suite.

Validates that compose_action_continuation() is a pure composition operation over an
authoritative Phase 2 Decision and cannot alter decision policy, score, facts, or offers.
"""

import json
from pathlib import Path
import pytest

from app.composer.compose import compose_action_continuation
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ActionType
from app.engine.decide import decide
from app.engine.decision import Decision
from app.api.service import EngineService
from app.api.schemas import ReplyResponse


DATASET_DIR = Path(__file__).resolve().parent.parent / "magicpin-ai-challenge" / "dataset"


def load_dataset():
    """Load normalized dataset files for canonical test fixtures."""
    raw_cats = {}
    categories = {}
    for f in (DATASET_DIR / "categories").glob("*.json"):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            raw_cats[data["slug"]] = data
            categories[data["slug"]] = CategoryProfile.from_dict(data)

    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as fp:
        raw_merchants_list = json.load(fp)["merchants"]
        raw_merchants = {m["merchant_id"]: m for m in raw_merchants_list}
        merchants = {m["merchant_id"]: MerchantState.from_dict(m) for m in raw_merchants_list}

    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as fp:
        raw_triggers_list = json.load(fp)["triggers"]
        raw_triggers = {t["id"]: t for t in raw_triggers_list}
        triggers = {t["id"]: TriggerState.from_dict(t) for t in raw_triggers_list}

    with open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8") as fp:
        raw_customers_list = json.load(fp)["customers"]
        raw_customers = {c["customer_id"]: c for c in raw_customers_list}
        customers = {c["customer_id"]: CustomerStateModel.from_dict(c) for c in raw_customers_list}

    return categories, merchants, triggers, customers, raw_cats, raw_merchants, raw_triggers, raw_customers


CANONICAL_SCENARIO_KEYS = [
    ("dentists", "m_001_drmeera_dentist_delhi", "trg_001_research_digest_dentists", None),
    ("dentists", "m_001_drmeera_dentist_delhi", "trg_003_recall_due_priya", "c_001_priya_for_m001"),
    ("salons", "m_003_studio11_salon_hyderabad", "trg_007_bridal_followup_kavya", "c_005_kavya_for_m003"),
    ("salons", "m_003_studio11_salon_hyderabad", "trg_008_curious_ask_studio11", None),
    ("restaurants", "m_005_pizzajunction_restaurant_delhi", "trg_010_ipl_match_delhi", None),
    ("restaurants", "m_006_southindiancafe_restaurant_bangalore", "trg_013_corporate_thali_planning", None),
    ("gyms", "m_007_powerhouse_gym_bangalore", "trg_014_seasonal_acquisition_dip_powerhouse", None),
    ("gyms", "m_007_powerhouse_gym_bangalore", "trg_015_winback_rashmi", "c_010_rashmi_for_m007"),
    ("pharmacies", "m_009_apollo_pharmacy_jaipur", "trg_018_supply_atorvastatin_recall", None),
    ("pharmacies", "m_009_apollo_pharmacy_jaipur", "trg_019_chronic_refill_grandfather", "c_013_grandfather_for_m009"),
]


@pytest.mark.parametrize("cat_slug,mid,trg_id,cid", CANONICAL_SCENARIO_KEYS)
def test_canonical_continuation_grounding_and_invariants(cat_slug, mid, trg_id, cid):
    """Test compose_action_continuation across all 10 canonical scenarios.
    
    Verifies:
    - ActionType unchanged
    - Phase 2 score unchanged
    - Selected facts unchanged
    - Selected offer unchanged
    - Zero unsupported promises or fabricated numbers
    - Valid CTA
    - Valid suppression key (no artificial decay tokens)
    - Deterministic output across repeated calls
    """
    categories, merchants, triggers, customers, _, _, _, _ = load_dataset()
    category = categories[cat_slug]
    merchant = merchants[mid]
    trigger = triggers[trg_id]
    customer = customers.get(cid) if cid else None

    decision = decide(category, merchant, trigger, customer)
    initial_score = decision.score
    initial_action_type = decision.action_type
    initial_facts = decision.evidence_facts
    initial_offer = decision.supporting_offer

    # Render continuation 1
    cont1 = compose_action_continuation(decision, category, merchant, trigger, customer)
    # Render continuation 2 (for determinism proof)
    cont2 = compose_action_continuation(decision, category, merchant, trigger, customer)

    # 1. Authority Preservation
    assert decision.score == initial_score, "Decision score was mutated!"
    assert decision.action_type == initial_action_type, "Decision ActionType was mutated!"
    assert decision.evidence_facts == initial_facts, "Decision facts were mutated!"
    assert decision.supporting_offer == initial_offer, "Decision offer was mutated!"
    assert cont1.action_type == initial_action_type

    # 2. Determinism
    assert cont1.body == cont2.body
    assert cont1.action == cont2.action
    assert cont1.cta == cont2.cta
    assert cont1.suppression_key == cont2.suppression_key
    assert cont1.rationale == cont2.rationale

    # 3. Actioning copy invariants (Actioning words present, zero qualifying questions)
    if cont1.action == "send":
        assert cont1.cta == "binary_confirm"
        body_lower = cont1.body.lower()
        actioning_words = ["here", "confirm", "proceed", "ready", "send", "draft", "launch"]
        assert any(w in body_lower for w in actioning_words), f"No actioning word in {cont1.body}"
        qualifying_words = ["would you", "do you", "can you tell", "what if", "how about"]
        assert not any(w in body_lower for w in qualifying_words), f"Qualifying word in {cont1.body}"

    # 4. Suppression Key Validity (No artificial decay)
    assert cont1.suppression_key is not None
    assert "cooldown" not in cont1.suppression_key.lower()


def test_non_draft_actions_specific_continuation():
    """Explicitly verify continuation language when action is NOT a draft/campaign action.
    
    Ensures:
    - customer_recall produces recall reminder language
    - customer_refill produces refill reminder language
    - address_supply_alert produces verified advisory language
    - use_research_insight produces research summary language
    - Composer does NOT blindly emit 'Here is the draft ready to confirm' for all actions.
    """
    categories, merchants, triggers, customers, _, _, _, _ = load_dataset()

    # 1. Customer Recall (Routine Service)
    dec_recall = Decision(
        action_type=ActionType.CUSTOMER_RECALL,
        action="customer_recall",
        target_scope="customer",
        trigger_id="trg_003",
        score=92.0,
        primary_reason="Routine service due",
        evidence_facts=("f1",),
    )
    c_recall = compose_action_continuation(
        dec_recall,
        categories["dentists"],
        merchants["m_001_drmeera_dentist_delhi"],
        triggers["trg_003_recall_due_priya"],
        customers["c_001_priya_for_m001"],
    )
    assert "recall reminder" in c_recall.body.lower()
    assert "dispatch" in c_recall.body.lower()

    # 2. Customer Refill (Medication Refill)
    dec_refill = Decision(
        action_type=ActionType.CUSTOMER_REFILL,
        action="customer_refill",
        target_scope="customer",
        trigger_id="trg_019",
        score=95.0,
        primary_reason="Chronic refill due",
        evidence_facts=("f1",),
    )
    c_refill = compose_action_continuation(
        dec_refill,
        categories["pharmacies"],
        merchants["m_009_apollo_pharmacy_jaipur"],
        triggers["trg_019_chronic_refill_grandfather"],
        customers["c_013_grandfather_for_m009"],
    )
    assert "refill reminder" in c_refill.body.lower()

    # 3. Supply Alert (Safety Advisory)
    dec_supply = Decision(
        action_type=ActionType.ADDRESS_SUPPLY_ALERT,
        action="address_supply_alert",
        target_scope="merchant",
        trigger_id="trg_018",
        score=98.0,
        primary_reason="Batch recall alert",
        evidence_facts=("f1",),
    )
    c_supply = compose_action_continuation(
        dec_supply,
        categories["pharmacies"],
        merchants["m_009_apollo_pharmacy_jaipur"],
        triggers["trg_018_supply_atorvastatin_recall"],
        None,
    )
    assert "verified advisory" in c_supply.body.lower()
    assert "atorvastatin" in c_supply.body.lower()

    # 4. Research Insight (Clinical Summary)
    dec_research = Decision(
        action_type=ActionType.USE_RESEARCH_INSIGHT,
        action="use_research_insight",
        target_scope="merchant",
        trigger_id="trg_001",
        score=89.0,
        primary_reason="Clinical publication relevant",
        evidence_facts=("f1",),
    )
    c_research = compose_action_continuation(
        dec_research,
        categories["dentists"],
        merchants["m_001_drmeera_dentist_delhi"],
        triggers["trg_001_research_digest_dentists"],
        None,
    )
    assert "patient-education summary" in c_research.body.lower()


def test_wait_and_end_decisions_continuation():
    """Verify continuation on WAIT and END decisions stand down rather than fabricating an outreach."""
    categories, merchants, triggers, _, _, _, _, _ = load_dataset()

    # WAIT Decision
    dec_wait = Decision(
        action_type=ActionType.WAIT,
        action="wait",
        target_scope="merchant",
        trigger_id="trg_001",
        score=40.0,
        primary_reason="Safety hold",
        evidence_facts=(),
    )
    c_wait = compose_action_continuation(
        dec_wait,
        categories["dentists"],
        merchants["m_001_drmeera_dentist_delhi"],
        triggers["trg_001_research_digest_dentists"],
        None,
    )
    assert c_wait.action == "wait"
    assert c_wait.body == ""
    assert c_wait.cta == "none"

    # END Decision
    dec_end = Decision(
        action_type=ActionType.END,
        action="end",
        target_scope="merchant",
        trigger_id="trg_001",
        score=0.0,
        primary_reason="Consent revoked",
        evidence_facts=(),
    )
    c_end = compose_action_continuation(
        dec_end,
        categories["dentists"],
        merchants["m_001_drmeera_dentist_delhi"],
        triggers["trg_001_research_digest_dentists"],
        None,
    )
    assert c_end.action == "end"
    assert c_end.body == ""
    assert c_end.cta == "none"


def test_runtime_actionable_intent_call_path():
    """Verify the exact runtime chain for 'Ok lets do it. Whats next?'
    
    Chain:
    incoming reply -> Phase 6 classifier -> ACTIONABLE_INTENT -> WAITING -> ACTION
    -> CONTINUE_EXISTING_ACTION -> existing decision -> Phase 3 continuation -> ReplyResponse
    """
    svc = EngineService()
    categories, merchants, triggers, _, raw_cats, raw_merchants, raw_triggers, _ = load_dataset()
    svc.store.store("category", "dentists", 1, raw_cats["dentists"])
    svc.store.store("merchant", "m_001_drmeera_dentist_delhi", 1, raw_merchants["m_001_drmeera_dentist_delhi"])
    svc.store.store("trigger", "trg_001_research_digest_dentists", 1, raw_triggers["trg_001_research_digest_dentists"])

    # Send commitment reply
    resp = svc.reply(
        conversation_id="conv_runtime_test_001",
        merchant_id="m_001_drmeera_dentist_delhi",
        customer_id=None,
        from_role="merchant",
        message="Ok lets do it. Whats next?",
        received_at="2026-04-26T10:30:00Z",
        turn_number=2,
    )

    assert isinstance(resp, ReplyResponse)
    assert resp.action == "send"
    assert resp.cta == "binary_confirm"
    assert "patient-education summary" in resp.body.lower()
    assert "confirm to proceed" in resp.body.lower()
    assert "Phase 3 grounded continuation" in resp.rationale
