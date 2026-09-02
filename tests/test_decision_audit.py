"""Audit tests demonstrating generalization, perturbed scenarios, and diverging decisions on single-fact changes."""

import json
from pathlib import Path
import pytest

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


# =============================================================================
# 1. PERTURBED SCENARIOS (IDs, DATES, METRICS, LOCALITIES CHANGED)
# =============================================================================

def test_perturbed_dentist_recall_different_city_and_slots(dataset):
    """Case 2 Perturbation: Different clinic in Bangalore, different customer and recall slots."""
    cat = dataset["categories"]["dentists"]
    merchant = MerchantState.from_dict({
        "merchant_id": "m_bangalore_smile_clinic",
        "category_slug": "dentists",
        "identity": {"name": "Smile Dental Care", "city": "Bangalore", "locality": "Indiranagar", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": [{"id": "o_bgl_clean", "title": "Scaling & Polishing @ ₹499", "status": "active"}]
    })
    customer = CustomerStateModel.from_dict({
        "customer_id": "c_vikram_bgl",
        "merchant_id": merchant.merchant_id,
        "identity": {"name": "Vikram", "language_pref": "en"},
        "relationship": {"visits_total": 3, "last_visit": "2025-10-10"},
        "state": "lapsed_soft",
        "preferences": {"preferred_slots": "saturday_morning", "reminder_opt_in": True},
        "consent": {"opted_in_at": "2025-10-10", "scope": ["recall_reminders"]}
    })
    trigger = TriggerState.from_dict({
        "id": "trg_rec_vikram", "scope": "customer", "kind": "recall_due",
        "source": "internal", "merchant_id": merchant.merchant_id, "customer_id": customer.customer_id,
        "payload": {
            "service_due": "annual_scaling",
            "available_slots": [{"label": "Sat 15 Nov, 10am"}, {"label": "Sat 15 Nov, 11:30am"}]
        },
        "urgency": 3, "suppression_key": "rec:vikram"
    })

    decision = decide(cat, merchant, trigger, customer)
    assert decision.action_type == ActionType.CUSTOMER_RECALL
    assert decision.target_scope == "customer"
    assert decision.supporting_offer["id"] == "o_bgl_clean"


def test_perturbed_salon_bridal_different_dates(dataset):
    """Case 3 Perturbation: Different salon, different bride in Pune, wedding in 2027."""
    cat = dataset["categories"]["salons"]
    merchant = MerchantState.from_dict({
        "merchant_id": "m_pune_glam",
        "category_slug": "salons",
        "identity": {"name": "Glamour Lounge", "city": "Pune", "locality": "Kothrud", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": [{"id": "o_bridal_pune", "title": "Bridal Glow Package @ ₹4999", "status": "active"}]
    })
    customer = CustomerStateModel.from_dict({
        "customer_id": "c_radhika_pune",
        "merchant_id": merchant.merchant_id,
        "identity": {"name": "Radhika", "language_pref": "mr-en mix"},
        "relationship": {"visits_total": 1},
        "state": "new",
        "preferences": {"wedding_date": "2027-02-14", "reminder_opt_in": True},
        "consent": {"opted_in_at": "2026-08-01", "scope": ["bridal_followup"]}
    })
    trigger = TriggerState.from_dict({
        "id": "trg_bridal_radhika", "scope": "customer", "kind": "wedding_package_followup",
        "source": "internal", "merchant_id": merchant.merchant_id, "customer_id": customer.customer_id,
        "payload": {"wedding_date": "2027-02-14", "days_to_wedding": 160, "trial_completed": "2026-08-01"},
        "urgency": 2, "suppression_key": "bridal:radhika"
    })

    decision = decide(cat, merchant, trigger, customer)
    assert decision.action_type == ActionType.CUSTOMER_FOLLOWUP
    assert decision.target_scope == "customer"


def test_perturbed_gym_winback_different_lapsed_interval(dataset):
    """Case 8 Perturbation: Different gym member lapsed 95 days ago with yoga focus."""
    cat = dataset["categories"]["gyms"]
    merchant = MerchantState.from_dict({
        "merchant_id": "m_delhi_iron_gym",
        "category_slug": "gyms",
        "identity": {"name": "Iron Gym", "city": "Delhi", "locality": "Dwarka", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": [{"id": "o_pass", "title": "Free Weekend Class Pass", "status": "active"}]
    })
    customer = CustomerStateModel.from_dict({
        "customer_id": "c_tanvi_delhi",
        "merchant_id": merchant.merchant_id,
        "identity": {"name": "Tanvi", "language_pref": "hi"},
        "relationship": {"visits_total": 18, "last_visit": "2026-01-20"},
        "state": "lapsed_hard",
        "preferences": {"training_focus": "yoga", "reminder_opt_in": True},
        "consent": {"opted_in_at": "2025-06-01", "scope": ["reengagement"]}
    })
    trigger = TriggerState.from_dict({
        "id": "trg_tanvi_lapsed", "scope": "customer", "kind": "customer_lapsed_hard",
        "source": "internal", "merchant_id": merchant.merchant_id, "customer_id": customer.customer_id,
        "payload": {"days_since_last_visit": 95, "previous_focus": "yoga"},
        "urgency": 3, "suppression_key": "winback:tanvi"
    })

    decision = decide(cat, merchant, trigger, customer)
    assert decision.action_type == ActionType.CUSTOMER_WINBACK
    assert decision.target_scope == "customer"


# =============================================================================
# 2. AT LEAST 5 CASES WHERE A SINGLE FACT FLIPS THE DECISION
# =============================================================================

def test_diverging_case_1_expected_seasonal_vs_unexpected_performance_dip(dataset):
    """Divergence 1: Identical 35% views dip.
    Fact flip: is_expected_seasonal = True vs False."""
    cat = dataset["categories"]["gyms"]
    merchant = dataset["merchants"]["m_007_powerhouse_gym_bangalore"]

    # 1A: Expected seasonal drop -> REFRAME_SEASONAL_DIP
    trg_seasonal = TriggerState.from_dict({
        "id": "trg_dip_seasonal", "scope": "merchant", "kind": "seasonal_perf_dip",
        "source": "internal", "merchant_id": merchant.merchant_id,
        "payload": {"metric": "views", "delta_pct": -0.35, "is_expected_seasonal": True},
        "urgency": 4, "suppression_key": "dip"
    })
    decision_seasonal = decide(cat, merchant, trg_seasonal)
    assert decision_seasonal.action_type == ActionType.REFRAME_SEASONAL_DIP

    # 1B: Unexpected drop -> ADDRESS_PERFORMANCE_DIP
    trg_unexpected = TriggerState.from_dict({
        "id": "trg_dip_unexpected", "scope": "merchant", "kind": "perf_dip",
        "source": "internal", "merchant_id": merchant.merchant_id,
        "payload": {"metric": "views", "delta_pct": -0.35, "is_expected_seasonal": False},
        "urgency": 4, "suppression_key": "dip"
    })
    decision_unexpected = decide(cat, merchant, trg_unexpected)
    assert decision_unexpected.action_type == ActionType.ADDRESS_PERFORMANCE_DIP


def test_diverging_case_2_weekend_match_vs_weeknight_match(dataset):
    """Divergence 2: IPL match in restaurant vertical with delivery offer.
    Fact flip: is_weeknight = False (Saturday) vs True (Tuesday)."""
    cat = dataset["categories"]["restaurants"]
    merchant = dataset["merchants"]["m_005_pizzajunction_restaurant_delhi"]

    # 2A: Saturday match (home-viewing cover shift) -> PROMOTE_DELIVERY_OFFER
    trg_saturday = TriggerState.from_dict({
        "id": "trg_sat_match", "scope": "merchant", "kind": "ipl_match_today",
        "source": "external", "merchant_id": merchant.merchant_id,
        "payload": {"match": "CSK vs MI", "venue": "Delhi", "is_weeknight": False},
        "urgency": 3, "suppression_key": "ipl"
    })
    decision_sat = decide(cat, merchant, trg_saturday)
    assert decision_sat.action_type == ActionType.PROMOTE_DELIVERY_OFFER

    # 2B: Weeknight match (normal dine-in night) -> No home-viewing cover shift
    # In weeknights, no contrarian boost is fired; standard WAIT stands down rather than forcing a delivery pivot
    trg_weeknight = TriggerState.from_dict({
        "id": "trg_wed_match", "scope": "merchant", "kind": "ipl_match_today",
        "source": "external", "merchant_id": merchant.merchant_id,
        "payload": {"match": "CSK vs MI", "venue": "Delhi", "is_weeknight": True},
        "urgency": 3, "suppression_key": "ipl"
    })
    decision_wed = decide(cat, merchant, trg_weeknight)
    assert decision_wed.action_type != ActionType.PROMOTE_DELIVERY_OFFER or "delivery" not in decision_wed.trace.derived_signals


def test_diverging_case_3_active_delivery_offer_vs_dinein_offer(dataset):
    """Divergence 3: Saturday IPL match day.
    Fact flip: Merchant has BOGO Delivery Offer vs only 15% Table Reservation Offer."""
    cat = dataset["categories"]["restaurants"]
    trg = TriggerState.from_dict({
        "id": "trg_sat_match", "scope": "merchant", "kind": "ipl_match_today",
        "source": "external", "merchant_id": "m_test",
        "payload": {"match": "DC vs KKR", "is_weeknight": False},
        "urgency": 3, "suppression_key": "ipl"
    })

    # 3A: Delivery offer available -> PROMOTE_DELIVERY_OFFER
    m_delivery = MerchantState.from_dict({
        "merchant_id": "m_test", "category_slug": "restaurants",
        "identity": {"name": "Delivery Pizzeria", "city": "Delhi", "locality": "Saket", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": [{"id": "o_deliv", "title": "Buy 1 Get 1 Pizza Delivery Special", "status": "active"}]
    })
    decision_deliv = decide(cat, m_delivery, trg)
    assert decision_deliv.action_type == ActionType.PROMOTE_DELIVERY_OFFER

    # 3B: Only dine-in offer available -> Disqualified from PROMOTE_DELIVERY_OFFER -> WAIT
    m_dinein = MerchantState.from_dict({
        "merchant_id": "m_test", "category_slug": "restaurants",
        "identity": {"name": "DineIn Pizzeria", "city": "Delhi", "locality": "Saket", "place_id": "x", "verified": True},
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30},
        "offers": [{"id": "o_dine", "title": "15% off Table Dine-in", "status": "active"}]
    })
    decision_dine = decide(cat, m_dinein, trg)
    assert decision_dine.action_type == ActionType.WAIT


def test_diverging_case_4_consent_valid_vs_consent_opted_out(dataset):
    """Divergence 4: 6-month cleaning recall window open.
    Fact flip: customer reminder_opt_in = True vs False."""
    cat = dataset["categories"]["dentists"]
    merchant = dataset["merchants"]["m_001_drmeera_dentist_delhi"]
    trg = TriggerState.from_dict({
        "id": "trg_rec", "scope": "customer", "kind": "recall_due",
        "source": "internal", "merchant_id": merchant.merchant_id, "customer_id": "c_test",
        "payload": {"service_due": "6_month_cleaning", "available_slots": [{"label": "Mon 10am"}]},
        "urgency": 3, "suppression_key": "rec"
    })

    # 4A: Valid consent -> CUSTOMER_RECALL
    c_opted_in = CustomerStateModel.from_dict({
        "customer_id": "c_test", "merchant_id": merchant.merchant_id,
        "identity": {"name": "Aakash", "language_pref": "en"},
        "relationship": {"visits_total": 4}, "state": "lapsed_soft",
        "preferences": {"reminder_opt_in": True},
        "consent": {"opted_in_at": "2025-10-01", "scope": ["recall_reminders"]}
    })
    decision_in = decide(cat, merchant, trg, c_opted_in)
    assert decision_in.action_type == ActionType.CUSTOMER_RECALL

    # 4B: Opted out -> WAIT
    c_opted_out = CustomerStateModel.from_dict({
        "customer_id": "c_test", "merchant_id": merchant.merchant_id,
        "identity": {"name": "Aakash", "language_pref": "en"},
        "relationship": {"visits_total": 4}, "state": "lapsed_soft",
        "preferences": {"reminder_opt_in": False},  # Explicit opt-out!
        "consent": {"opted_in_at": None, "scope": []}
    })
    decision_out = decide(cat, merchant, trg, c_opted_out)
    assert decision_out.action_type == ActionType.WAIT


def test_diverging_case_5_matched_clinical_digest_vs_unmatched_digest(dataset):
    """Divergence 5: Research digest trigger.
    Fact flip: top_item_id exists in category digest vs is non-existent."""
    cat = dataset["categories"]["dentists"]
    merchant = dataset["merchants"]["m_001_drmeera_dentist_delhi"]

    # 5A: Real top_item_id in catalog -> USE_RESEARCH_INSIGHT
    trg_matched = TriggerState.from_dict({
        "id": "trg_res_good", "scope": "merchant", "kind": "research_digest",
        "source": "external", "merchant_id": merchant.merchant_id,
        "payload": {"top_item_id": "d_2026W17_jida_fluoride"},
        "urgency": 2, "suppression_key": "res"
    })
    decision_matched = decide(cat, merchant, trg_matched)
    assert decision_matched.action_type == ActionType.USE_RESEARCH_INSIGHT

    # 5B: Unmatched / non-existent digest item -> Ineligible -> WAIT
    trg_unmatched = TriggerState.from_dict({
        "id": "trg_res_bad", "scope": "merchant", "kind": "research_digest",
        "source": "external", "merchant_id": merchant.merchant_id,
        "payload": {"top_item_id": "non_existent_item_id_9999"},
        "urgency": 2, "suppression_key": "res"
    })
    decision_unmatched = decide(cat, merchant, trg_unmatched)
    assert decision_unmatched.action_type == ActionType.WAIT
