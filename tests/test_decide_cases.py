"""Regression tests verifying that all 10 canonical cases and their perturbed variants decide correctly."""

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

    return {
        "categories": cats,
        "merchants": merchants,
        "customers": customers,
        "triggers": triggers,
    }


# =============================================================================
# 10 CANONICAL CASE STUDY REGRESSION
# =============================================================================

def test_canonical_case_1_dentist_research_digest(dataset):
    """Case 1: Dr. Meera with JIDA fluoride research digest -> USE_RESEARCH_INSIGHT."""
    cat = dataset["categories"]["dentists"]
    m = dataset["merchants"]["m_001_drmeera_dentist_delhi"]
    trg = dataset["triggers"]["trg_001_research_digest_dentists"]

    decision = decide(cat, m, trg)
    assert decision.action_type == ActionType.USE_RESEARCH_INSIGHT
    assert decision.target_scope == "merchant"
    assert len(decision.evidence_facts) > 0
    assert any("category.digest.matched" in f.name for f in decision.evidence_facts)


def test_canonical_case_2_dentist_recall_reminder(dataset):
    """Case 2: Priya 6-month cleaning recall reminder -> CUSTOMER_RECALL."""
    cat = dataset["categories"]["dentists"]
    m = dataset["merchants"]["m_001_drmeera_dentist_delhi"]
    trg = dataset["triggers"]["trg_003_recall_due_priya"]
    cust = dataset["customers"]["c_001_priya_for_m001"]

    decision = decide(cat, m, trg, cust)
    assert decision.action_type == ActionType.CUSTOMER_RECALL
    assert decision.target_scope == "customer"
    assert decision.supporting_offer is not None
    assert decision.supporting_offer["status"] == "active"


def test_canonical_case_3_salon_bridal_followup(dataset):
    """Case 3: Kavya bridal skin-prep followup -> CUSTOMER_FOLLOWUP."""
    cat = dataset["categories"]["salons"]
    m = dataset["merchants"]["m_003_studio11_salon_hyderabad"]
    trg = dataset["triggers"]["trg_007_bridal_followup_kavya"]
    cust = dataset["customers"]["c_005_kavya_for_m003"]

    decision = decide(cat, m, trg, cust)
    assert decision.action_type == ActionType.CUSTOMER_FOLLOWUP
    assert decision.target_scope == "customer"


def test_canonical_case_4_salon_curious_ask(dataset):
    """Case 4: Studio11 weekly demand ask -> CURIOUS_ASK."""
    cat = dataset["categories"]["salons"]
    m = dataset["merchants"]["m_003_studio11_salon_hyderabad"]
    trg = dataset["triggers"]["trg_008_curious_ask_studio11"]

    decision = decide(cat, m, trg)
    assert decision.action_type == ActionType.CURIOUS_ASK
    assert decision.target_scope == "merchant"


def test_canonical_case_5_restaurant_ipl_match_saturday(dataset):
    """Case 5: Pizza Junction Saturday IPL match day -> PROMOTE_DELIVERY_OFFER (contrarian pivot)."""
    cat = dataset["categories"]["restaurants"]
    m = dataset["merchants"]["m_005_pizzajunction_restaurant_delhi"]
    trg = dataset["triggers"]["trg_010_ipl_match_delhi"]

    decision = decide(cat, m, trg)
    assert decision.action_type == ActionType.PROMOTE_DELIVERY_OFFER
    assert decision.target_scope == "merchant"
    assert decision.supporting_offer is not None
    assert any(k in decision.supporting_offer["title"].lower() for k in ("bogo", "buy 1", "get 1", "delivery"))


def test_canonical_case_6_restaurant_active_planning(dataset):
    """Case 6: South Indian Cafe corporate bulk thali package -> CONTINUE_PLANNING."""
    cat = dataset["categories"]["restaurants"]
    m = dataset["merchants"]["m_006_southindiancafe_restaurant_bangalore"]
    trg = dataset["triggers"]["trg_013_corporate_thali_planning"]

    decision = decide(cat, m, trg)
    assert decision.action_type == ActionType.CONTINUE_PLANNING
    assert decision.target_scope == "merchant"


def test_canonical_case_7_gym_seasonal_dip_reframe(dataset):
    """Case 7: PowerHouse Fitness expected April seasonal lull -> REFRAME_SEASONAL_DIP."""
    cat = dataset["categories"]["gyms"]
    m = dataset["merchants"]["m_007_powerhouse_gym_bangalore"]
    trg = dataset["triggers"]["trg_014_seasonal_acquisition_dip_powerhouse"]

    decision = decide(cat, m, trg)
    assert decision.action_type == ActionType.REFRAME_SEASONAL_DIP
    assert decision.target_scope == "merchant"


def test_canonical_case_8_gym_customer_winback(dataset):
    """Case 8: Rashmi 57 days lapsed member winback -> CUSTOMER_WINBACK."""
    cat = dataset["categories"]["gyms"]
    m = dataset["merchants"]["m_007_powerhouse_gym_bangalore"]
    trg = dataset["triggers"]["trg_015_winback_rashmi"]
    cust = dataset["customers"]["c_010_rashmi_for_m007"]

    decision = decide(cat, m, trg, cust)
    assert decision.action_type == ActionType.CUSTOMER_WINBACK
    assert decision.target_scope == "customer"


def test_canonical_case_9_pharmacy_supply_alert(dataset):
    """Case 9: Apollo Pharmacy voluntary atorvastatin batch recall -> ADDRESS_SUPPLY_ALERT."""
    cat = dataset["categories"]["pharmacies"]
    m = dataset["merchants"]["m_009_apollo_pharmacy_jaipur"]
    trg = dataset["triggers"]["trg_018_supply_atorvastatin_recall"]

    decision = decide(cat, m, trg)
    assert decision.action_type == ActionType.ADDRESS_SUPPLY_ALERT
    assert decision.target_scope == "merchant"


def test_canonical_case_10_pharmacy_chronic_refill(dataset):
    """Case 10: Mr. Sharma 3 monthly medicines run-out reminder -> CUSTOMER_REFILL."""
    cat = dataset["categories"]["pharmacies"]
    m = dataset["merchants"]["m_009_apollo_pharmacy_jaipur"]
    trg = dataset["triggers"]["trg_019_chronic_refill_grandfather"]
    cust = dataset["customers"]["c_013_grandfather_for_m009"]

    decision = decide(cat, m, trg, cust)
    assert decision.action_type == ActionType.CUSTOMER_REFILL
    assert decision.target_scope == "customer"


# =============================================================================
# PERTURBED VARIANT TESTS (PROVING GENERALITY, ZERO HARDCODING)
# =============================================================================

def test_perturbed_case_1_different_dentist_and_city(dataset):
    """Verify research digest logic on a completely synthetic merchant in Chennai."""
    cat = dataset["categories"]["dentists"]
    synthetic_merchant = MerchantState.from_dict({
        "merchant_id": "m_999_synthetic_chennai",
        "category_slug": "dentists",
        "identity": {
            "name": "Dr. Ananya Dental",
            "city": "Chennai",
            "locality": "Anna Nagar",
            "place_id": "ChIJ_SYNTH",
            "verified": True,
            "languages": ["en", "ta"],
        },
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30, "views": 1500, "calls": 25, "ctr": 0.025},
        "customer_aggregate": {"high_risk_adult_count": 88},
    })
    trg = dataset["triggers"]["trg_001_research_digest_dentists"]

    decision = decide(cat, synthetic_merchant, trg)
    assert decision.action_type == ActionType.USE_RESEARCH_INSIGHT
    assert decision.target_scope == "merchant"
    assert "Dr. Ananya Dental" in [f.value for f in decision.evidence_facts if f.name == "merchant.name"]


def test_perturbed_case_5_different_restaurant_and_match(dataset):
    """Verify contrarian delivery pivot on another restaurant with a different match in Pune."""
    cat = dataset["categories"]["restaurants"]
    pune_restaurant = MerchantState.from_dict({
        "merchant_id": "m_888_pune_burger",
        "category_slug": "restaurants",
        "identity": {
            "name": "Pune Burger House",
            "city": "Pune",
            "locality": "Koregaon Park",
            "place_id": "ChIJ_PUNE",
            "verified": True,
            "languages": ["en", "mr"],
        },
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30, "views": 3200, "calls": 40, "ctr": 0.035},
        "offers": [
            {"id": "o_pune_deliv", "title": "Buy 1 Get 1 Burger Delivery Only", "status": "active"}
        ],
    })
    pune_ipl_trigger = TriggerState.from_dict({
        "id": "trg_ipl_pune_synthetic",
        "scope": "merchant",
        "kind": "ipl_match_today",
        "source": "external",
        "merchant_id": pune_restaurant.merchant_id,
        "payload": {
            "match": "CSK vs RCB",
            "venue": "Gahunje Stadium",
            "is_weeknight": False,  # Weekend!
        },
        "urgency": 3,
        "suppression_key": "ipl:pune",
    })

    decision = decide(cat, pune_restaurant, pune_ipl_trigger)
    assert decision.action_type == ActionType.PROMOTE_DELIVERY_OFFER
    assert decision.supporting_offer["id"] == "o_pune_deliv"


def test_perturbed_case_9_different_pharmacy_and_molecule(dataset):
    """Verify supply alert logic on a different pharmacy in Kolkata with different batches."""
    cat = dataset["categories"]["pharmacies"]
    kolkata_pharmacy = MerchantState.from_dict({
        "merchant_id": "m_777_kolkata_chem",
        "category_slug": "pharmacies",
        "identity": {
            "name": "Bengal Chemists",
            "city": "Kolkata",
            "locality": "Salt Lake",
            "place_id": "ChIJ_KOLKATA",
            "verified": True,
            "languages": ["en", "bn"],
        },
        "subscription": {"status": "active", "plan": "Pro"},
        "performance": {"window_days": 30, "views": 1800, "calls": 50, "ctr": 0.04},
        "customer_aggregate": {"chronic_rx_count": 310},
    })
    synthetic_supply_trigger = TriggerState.from_dict({
        "id": "trg_supply_synth_999",
        "scope": "merchant",
        "kind": "supply_alert",
        "source": "external",
        "merchant_id": kolkata_pharmacy.merchant_id,
        "payload": {
            "alert_id": "ALT-2026-X9",
            "molecule": "metformin_500",
            "affected_batches": ["MET-9901", "MET-9902"],
            "manufacturer": "PharmaCorp Ltd",
        },
        "urgency": 5,
        "suppression_key": "supply:metformin",
    })

    decision = decide(cat, kolkata_pharmacy, synthetic_supply_trigger)
    assert decision.action_type == ActionType.ADDRESS_SUPPLY_ALERT
    assert decision.target_scope == "merchant"
    assert decision.score >= 80.0
