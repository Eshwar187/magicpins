"""Unit and integration tests for Vera Grounded Message Composer across all canonical cases and ActionTypes."""

import json
from pathlib import Path
import pytest

from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ActionType
from app.engine.decide import decide
from app.composer.compose import compose
from app.composer.message import ComposedMessage

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
# 10 CANONICAL CASE STUDY COMPOSITION REGRESSION
# =============================================================================

def test_canonical_case_1_research_digest_composition(dataset):
    """Case 1: Dentist research digest composition."""
    cat = dataset["categories"]["dentists"]
    m = dataset["merchants"]["m_001_drmeera_dentist_delhi"]
    trg = dataset["triggers"]["trg_001_research_digest_dentists"]

    decision = decide(cat, m, trg)
    msg = compose(decision, cat, m, trg)

    assert isinstance(msg, ComposedMessage)
    assert msg.action == "send"
    assert msg.action_type == ActionType.USE_RESEARCH_INSIGHT
    assert msg.target_scope == "merchant"
    assert msg.send_as == "vera"
    assert "Dr. Meera" in msg.body
    assert "JIDA" in msg.body
    assert "38%" in msg.body or "caries" in msg.body
    assert msg.cta == "binary_yes_no"
    assert msg.suppression_key.startswith("research:dentists:")
    assert len(msg.rationale) > 0


def test_canonical_case_2_customer_recall_composition(dataset):
    """Case 2: Dentist routine recall reminder composition."""
    cat = dataset["categories"]["dentists"]
    m = dataset["merchants"]["m_001_drmeera_dentist_delhi"]
    trg = dataset["triggers"]["trg_003_recall_due_priya"]
    cust = dataset["customers"]["c_001_priya_for_m001"]

    decision = decide(cat, m, trg, cust)
    msg = compose(decision, cat, m, trg, cust)

    assert msg.action == "send"
    assert msg.action_type == ActionType.CUSTOMER_RECALL
    assert msg.target_scope == "customer"
    assert msg.send_as == "merchant_on_behalf"
    assert "Priya" in msg.body
    assert "Dr. Meera" in msg.body
    assert "cleaning" in msg.body.lower()
    assert msg.cta == "multi_choice_slot"
    assert msg.suppression_key.startswith("recall:c_001_priya_for_m001:")


def test_canonical_case_3_salon_bridal_followup_composition(dataset):
    """Case 3: Salon bridal follow-up composition."""
    cat = dataset["categories"]["salons"]
    m = dataset["merchants"]["m_003_studio11_salon_hyderabad"]
    trg = dataset["triggers"]["trg_007_bridal_followup_kavya"]
    cust = dataset["customers"]["c_005_kavya_for_m003"]

    decision = decide(cat, m, trg, cust)
    msg = compose(decision, cat, m, trg, cust)

    assert msg.action == "send"
    assert msg.action_type == ActionType.CUSTOMER_FOLLOWUP
    assert msg.target_scope == "customer"
    assert msg.send_as == "merchant_on_behalf"
    assert "Kavya" in msg.body
    assert "wedding" in msg.body.lower()
    assert msg.cta == "binary_yes_no"
    assert msg.suppression_key.startswith("followup:c_005_kavya_for_m003:")


def test_canonical_case_4_salon_curious_ask_composition(dataset):
    """Case 4: Salon weekly curiosity cadence ask composition."""
    cat = dataset["categories"]["salons"]
    m = dataset["merchants"]["m_003_studio11_salon_hyderabad"]
    trg = dataset["triggers"]["trg_008_curious_ask_studio11"]

    decision = decide(cat, m, trg)
    msg = compose(decision, cat, m, trg)

    assert msg.action == "send"
    assert msg.action_type == ActionType.CURIOUS_ASK
    assert msg.target_scope == "merchant"
    assert msg.send_as == "vera"
    assert "Studio11" in msg.body
    assert "5 minutes" in msg.body
    assert msg.cta == "open_ended"
    assert msg.suppression_key.startswith("curious:m_003_studio11_salon_hyderabad:")


def test_canonical_case_5_restaurant_delivery_pivot_composition(dataset):
    """Case 5: Restaurant Saturday IPL match delivery promotion composition."""
    cat = dataset["categories"]["restaurants"]
    m = dataset["merchants"]["m_005_pizzajunction_restaurant_delhi"]
    trg = dataset["triggers"]["trg_010_ipl_match_delhi"]

    decision = decide(cat, m, trg)
    msg = compose(decision, cat, m, trg)

    assert msg.action == "send"
    assert msg.action_type == ActionType.PROMOTE_DELIVERY_OFFER
    assert msg.target_scope == "merchant"
    assert msg.send_as == "vera"
    assert "-12%" in msg.body
    assert "delivery" in msg.body.lower()
    assert any(k in msg.body.lower() for k in ("buy 1", "bogo"))
    assert msg.cta == "binary_yes_no"


def test_canonical_case_6_restaurant_active_planning_composition(dataset):
    """Case 6: Restaurant corporate lunch planning composition."""
    cat = dataset["categories"]["restaurants"]
    m = dataset["merchants"]["m_006_southindiancafe_restaurant_bangalore"]
    trg = dataset["triggers"]["trg_013_corporate_thali_planning"]

    decision = decide(cat, m, trg)
    msg = compose(decision, cat, m, trg)

    assert msg.action == "send"
    assert msg.action_type == ActionType.CONTINUE_PLANNING
    assert msg.target_scope == "merchant"
    assert msg.send_as == "vera"
    assert "Indiranagar" in msg.body
    assert "thali" in msg.body.lower() or "corporate" in msg.body.lower()
    assert msg.cta == "binary_yes_no"


def test_canonical_case_7_gym_seasonal_dip_reframe_composition(dataset):
    """Case 7: Gym seasonal performance reframe composition."""
    cat = dataset["categories"]["gyms"]
    m = dataset["merchants"]["m_007_powerhouse_gym_bangalore"]
    trg = dataset["triggers"]["trg_014_seasonal_acquisition_dip_powerhouse"]

    decision = decide(cat, m, trg)
    msg = compose(decision, cat, m, trg)

    assert msg.action == "send"
    assert msg.action_type == ActionType.REFRAME_SEASONAL_DIP
    assert msg.target_scope == "merchant"
    assert msg.send_as == "vera"
    assert "lull" in msg.body.lower() or "dip" in msg.body.lower()
    assert "245" in msg.body
    assert msg.cta == "binary_yes_no"


def test_canonical_case_8_gym_customer_winback_composition(dataset):
    """Case 8: Gym lapsed customer winback composition."""
    cat = dataset["categories"]["gyms"]
    m = dataset["merchants"]["m_007_powerhouse_gym_bangalore"]
    trg = dataset["triggers"]["trg_015_winback_rashmi"]
    cust = dataset["customers"]["c_010_rashmi_for_m007"]

    decision = decide(cat, m, trg, cust)
    msg = compose(decision, cat, m, trg, cust)

    assert msg.action == "send"
    assert msg.action_type == ActionType.CUSTOMER_WINBACK
    assert msg.target_scope == "customer"
    assert msg.send_as == "merchant_on_behalf"
    assert "Rashmi" in msg.body
    assert "zero judgment" in msg.body or "no judgment" in msg.body
    assert "no commitment" in msg.body
    assert msg.cta == "binary_yes_no"


def test_canonical_case_9_pharmacy_supply_alert_composition(dataset):
    """Case 9: Pharmacy supply recall alert composition."""
    cat = dataset["categories"]["pharmacies"]
    m = dataset["merchants"]["m_009_apollo_pharmacy_jaipur"]
    trg = dataset["triggers"]["trg_018_supply_atorvastatin_recall"]

    decision = decide(cat, m, trg)
    msg = compose(decision, cat, m, trg)

    assert msg.action == "send"
    assert msg.action_type == ActionType.ADDRESS_SUPPLY_ALERT
    assert msg.target_scope == "merchant"
    assert msg.send_as == "vera"
    assert "atorvastatin" in msg.body.lower()
    assert "sub-potency" in msg.body.lower()
    assert "22" in msg.body
    assert msg.cta == "binary_yes_no"


def test_canonical_case_10_pharmacy_chronic_refill_composition(dataset):
    """Case 10: Pharmacy chronic prescription refill reminder composition."""
    cat = dataset["categories"]["pharmacies"]
    m = dataset["merchants"]["m_009_apollo_pharmacy_jaipur"]
    trg = dataset["triggers"]["trg_019_chronic_refill_grandfather"]
    cust = dataset["customers"]["c_013_grandfather_for_m009"]

    decision = decide(cat, m, trg, cust)
    msg = compose(decision, cat, m, trg, cust)

    assert msg.action == "send"
    assert msg.action_type == ActionType.CUSTOMER_REFILL
    assert msg.target_scope == "customer"
    assert msg.send_as == "merchant_on_behalf"
    assert "Namaste" in msg.body
    assert "metformin" in msg.body.lower()
    assert msg.cta == "binary_confirm"
