"""Adversarial tests specifically designed to stress-test edge cases and break naive policies."""

import json
from pathlib import Path
import pytest

from app.domain.context_store import ContextStore
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ActionType
from app.engine.decide import decide

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


def test_adversarial_a_expired_offer_cannot_be_selected(dataset):
    """Adversarial A: A merchant with only expired offers must never have an offer selected."""
    cat = dataset["categories"]["restaurants"]
    merchant_raw = {
        "merchant_id": "m_expired_only",
        "category_slug": "restaurants",
        "identity": {"name": "Expired Pizza", "city": "Delhi", "locality": "Saket", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": [
            {"id": "o_exp_1", "title": "BOGO Pizza Delivery", "status": "expired", "ended": "2025-12-31"}
        ]
    }
    m = MerchantState.from_dict(merchant_raw)
    trg = TriggerState.from_dict({
        "id": "trg_ipl", "scope": "merchant", "kind": "ipl_match_today",
        "source": "external", "merchant_id": m.merchant_id,
        "payload": {"match": "CSK vs MI", "is_weeknight": False}, "urgency": 3, "suppression_key": "ipl"
    })

    decision = decide(cat, m, trg)
    # Since the delivery offer is expired, it cannot be promoted!
    assert decision.action_type != ActionType.PROMOTE_DELIVERY_OFFER
    assert decision.supporting_offer is None


def test_adversarial_b_category_catalog_cannot_masquerade_as_merchant_offer(dataset):
    """Adversarial B: Category has offer templates, but merchant has NO offers. Must not fabricate offer."""
    cat = dataset["categories"]["restaurants"]
    assert len(cat.offer_catalog) > 0  # Category has offers!

    merchant_raw = {
        "merchant_id": "m_no_offers",
        "category_slug": "restaurants",
        "identity": {"name": "No Offers Cafe", "city": "Delhi", "locality": "Saket", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": []  # Zero merchant offers!
    }
    m = MerchantState.from_dict(merchant_raw)
    trg = TriggerState.from_dict({
        "id": "trg_ipl", "scope": "merchant", "kind": "ipl_match_today",
        "source": "external", "merchant_id": m.merchant_id,
        "payload": {"match": "CSK vs MI", "is_weeknight": False}, "urgency": 3, "suppression_key": "ipl"
    })

    decision = decide(cat, m, trg)
    assert decision.action_type != ActionType.PROMOTE_DELIVERY_OFFER
    assert decision.supporting_offer is None


def test_adversarial_c_expected_seasonal_dip_does_not_trigger_alarmist_perf_dip(dataset):
    """Adversarial C: Large 45% drop marked as is_expected_seasonal must NOT trigger ADDRESS_PERFORMANCE_DIP."""
    cat = dataset["categories"]["gyms"]
    m = dataset["merchants"]["m_007_powerhouse_gym_bangalore"]
    trg = TriggerState.from_dict({
        "id": "trg_seasonal_dip", "scope": "merchant", "kind": "seasonal_perf_dip",
        "source": "internal", "merchant_id": m.merchant_id,
        "payload": {
            "metric": "views",
            "delta_pct": -0.45,
            "window": "7d",
            "is_expected_seasonal": True,
            "season_note": "Annual summer monsoon drop",
        },
        "urgency": 4,
        "suppression_key": "seasonal:views"
    })

    decision = decide(cat, m, trg)
    assert decision.action_type == ActionType.REFRAME_SEASONAL_DIP
    assert decision.action_type != ActionType.ADDRESS_PERFORMANCE_DIP


def test_adversarial_d_missing_consent_fails_closed(dataset):
    """Adversarial D: Customer exists, but consent is absent/None. Must fail closed -> WAIT."""
    cat = dataset["categories"]["dentists"]
    m = dataset["merchants"]["m_001_drmeera_dentist_delhi"]
    cust_raw = {
        "customer_id": "c_no_consent",
        "merchant_id": m.merchant_id,
        "identity": {"name": "No Consent Patient", "language_pref": "en"},
        "relationship": {"visits_total": 2},
        "state": "lapsed_soft",
        "preferences": {},
        "consent": {"opted_in_at": None, "scope": None}  # Explicit None consent!
    }
    cust = CustomerStateModel.from_dict(cust_raw)
    trg = TriggerState.from_dict({
        "id": "trg_recall", "scope": "customer", "kind": "recall_due",
        "source": "internal", "merchant_id": m.merchant_id, "customer_id": cust.customer_id,
        "payload": {
            "service_due": "cleaning",
            "available_slots": [{"label": "Fri 10am"}]
        },
        "urgency": 3,
        "suppression_key": "recall"
    })

    decision = decide(cat, m, trg, cust)
    assert decision.action_type == ActionType.WAIT
    assert "customer_consent" in decision.primary_reason or "No proactive action" in decision.primary_reason


def test_adversarial_e_explicit_opt_out_results_in_wait(dataset):
    """Adversarial E: Customer explicitly set reminder_opt_in=False. Must result in WAIT."""
    cat = dataset["categories"]["pharmacies"]
    m = dataset["merchants"]["m_010_sunrisepharm_pharmacy_lucknow"]
    cust = dataset["customers"]["c_015_anonymous_for_m010"]  # reminder_opt_in is False, scope is []
    trg = TriggerState.from_dict({
        "id": "trg_refill", "scope": "customer", "kind": "chronic_refill_due",
        "source": "internal", "merchant_id": m.merchant_id, "customer_id": cust.customer_id,
        "payload": {"molecule_list": ["paracetamol"]}, "urgency": 4, "suppression_key": "refill"
    })

    decision = decide(cat, m, trg, cust)
    assert decision.action_type == ActionType.WAIT


def test_adversarial_f_freshness_conflict_newer_version_wins(dataset):
    """Adversarial F: V1 has active offer, V2 updates merchant state where offer is expired.
    Newer version V2 must prevail."""
    store = ContextStore()
    cat = dataset["categories"]["restaurants"]

    m_v1_payload = {
        "merchant_id": "m_freshness_test",
        "category_slug": "restaurants",
        "identity": {"name": "Freshness Cafe", "city": "Delhi", "locality": "Saket", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": [{"id": "o_test", "title": "BOGO Delivery", "status": "active"}]
    }
    m_v2_payload = {
        "merchant_id": "m_freshness_test",
        "category_slug": "restaurants",
        "identity": {"name": "Freshness Cafe", "city": "Delhi", "locality": "Saket", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": [{"id": "o_test", "title": "BOGO Delivery", "status": "expired"}]  # Now expired!
    }

    store.store("merchant", "m_freshness_test", version=1, payload=m_v1_payload)
    store.store("merchant", "m_freshness_test", version=2, payload=m_v2_payload)

    m_current = store.get_merchant("m_freshness_test")
    trg = TriggerState.from_dict({
        "id": "trg_ipl", "scope": "merchant", "kind": "ipl_match_today",
        "source": "external", "merchant_id": "m_freshness_test",
        "payload": {"match": "DC vs MI", "is_weeknight": False}, "urgency": 3, "suppression_key": "ipl"
    })

    decision = decide(cat, m_current, trg, merchant_version=2)
    # Offer is expired in V2, so PROMOTE_DELIVERY_OFFER must NOT win
    assert decision.action_type != ActionType.PROMOTE_DELIVERY_OFFER


def test_adversarial_g_reverse_freshness_stale_update_rejected(dataset):
    """Adversarial G: V2 has active offer. A delayed stale post with version 1 is rejected by store."""
    store = ContextStore()
    m_v2_payload = {
        "merchant_id": "m_rev_fresh",
        "category_slug": "restaurants",
        "identity": {"name": "Rev Fresh", "city": "Delhi", "locality": "Saket", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": [{"id": "o_active", "title": "BOGO Delivery", "status": "active"}]
    }
    store.store("merchant", "m_rev_fresh", version=2, payload=m_v2_payload)

    # Delayed V1 arrives
    m_v1_payload = dict(m_v2_payload)
    m_v1_payload["offers"] = []
    res = store.store("merchant", "m_rev_fresh", version=1, payload=m_v1_payload)
    assert res.accepted is False

    m_authoritative = store.get_merchant("m_rev_fresh")
    assert len(m_authoritative.offers) == 1
    assert m_authoritative.offers[0].status == "active"


def test_adversarial_h_weak_evidence_high_urgency_loses_to_grounded_action(dataset):
    """Adversarial H: Urgency alone cannot force an action when evidence is absent."""
    cat = dataset["categories"]["dentists"]
    m = dataset["merchants"]["m_001_drmeera_dentist_delhi"]
    # Trigger has urgency 5, but is an unknown trigger with empty payload
    trg_empty = TriggerState.from_dict({
        "id": "trg_urgent_empty", "scope": "merchant", "kind": "unknown_future_alert",
        "source": "external", "merchant_id": m.merchant_id,
        "payload": {}, "urgency": 5, "suppression_key": "unknown"
    })

    decision = decide(cat, m, trg_empty)
    # Must fallback to WAIT rather than guessing an ungrounded action!
    assert decision.action_type == ActionType.WAIT


def test_adversarial_k_contrarian_event_without_delivery_offer(dataset):
    """Adversarial K: Saturday IPL match occurs, but restaurant only has a dine-in offer.
    Must NOT promote delivery offer since none exists!"""
    cat = dataset["categories"]["restaurants"]
    merchant_raw = {
        "merchant_id": "m_dinein_only",
        "category_slug": "restaurants",
        "identity": {"name": "DineIn Bistro", "city": "Delhi", "locality": "CP", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": [
            {"id": "o_dinein", "title": "15% off Dine-in Table Reservation", "status": "active"}
        ]
    }
    m = MerchantState.from_dict(merchant_raw)
    trg = TriggerState.from_dict({
        "id": "trg_ipl", "scope": "merchant", "kind": "ipl_match_today",
        "source": "external", "merchant_id": m.merchant_id,
        "payload": {"match": "CSK vs MI", "is_weeknight": False}, "urgency": 3, "suppression_key": "ipl"
    })

    decision = decide(cat, m, trg)
    # Cannot promote delivery offer because no delivery offer exists
    assert decision.action_type != ActionType.PROMOTE_DELIVERY_OFFER
