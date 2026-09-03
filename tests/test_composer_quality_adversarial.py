"""Adversarial quality tests verifying message differentiation across merchant, trigger, offer, metric, and customer variations."""

import json
from pathlib import Path
import pytest

from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.decide import decide
from app.composer.compose import compose

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


def test_quality_case_a_same_action_different_merchants(dataset):
    """Case A: Two different merchants receiving CURIOUS_ASK must receive distinct, personalized messages."""
    cat_salon = dataset["categories"]["salons"]
    m_studio11 = dataset["merchants"]["m_003_studio11_salon_hyderabad"]

    # Clone glamour salon with active subscription so it qualifies for CURIOUS_ASK
    glam_raw = dataset["merchants"]["m_004_glamour_salon_pune"].model_dump()
    glam_raw["subscription"] = {"status": "active", "plan": "Pro"}
    m_glamour = MerchantState.from_dict(glam_raw)

    trg_s11 = dataset["triggers"]["trg_008_curious_ask_studio11"]
    trg_glam = TriggerState.from_dict({
        "id": "trg_curious_glamour", "scope": "merchant", "kind": "curious_ask_due",
        "source": "internal", "merchant_id": m_glamour.merchant_id, "payload": {}, "urgency": 2, "suppression_key": "curious:glam"
    })

    dec1 = decide(cat_salon, m_studio11, trg_s11)
    msg1 = compose(dec1, cat_salon, m_studio11, trg_s11)

    dec2 = decide(cat_salon, m_glamour, trg_glam)
    msg2 = compose(dec2, cat_salon, m_glamour, trg_glam)

    # Both are CURIOUS_ASK
    assert msg1.action_type == msg2.action_type
    # But bodies MUST be different because merchant facts differ!
    assert msg1.body != msg2.body
    assert "Studio11 Family Salon" in msg1.body
    assert "Glamour Lounge Spa & Salon" in msg2.body
    assert "Anjali" in msg2.body
    assert "Lakshmi" in msg1.body


def test_quality_case_b_same_merchant_different_trigger_evidence(dataset):
    """Case B: Same merchant receives ADDRESS_SUPPLY_ALERT with different molecules and batch IDs."""
    cat = dataset["categories"]["pharmacies"]
    m = dataset["merchants"]["m_009_apollo_pharmacy_jaipur"]

    # Trigger 1: Atorvastatin recall
    trg1 = dataset["triggers"]["trg_018_supply_atorvastatin_recall"]
    dec1 = decide(cat, m, trg1)
    msg1 = compose(dec1, cat, m, trg1)

    # Trigger 2: Metformin recall with different batches
    trg2 = TriggerState.from_dict({
        "id": "trg_supply_metformin_alt", "scope": "merchant", "kind": "supply_alert",
        "source": "external", "merchant_id": m.merchant_id,
        "payload": {
            "alert_id": "ALT-2026-MET",
            "molecule": "metformin_500",
            "affected_batches": ["MET-9901", "MET-9902"],
            "manufacturer": "SunPharma",
            "affected_patient_count": 14,
        },
        "urgency": 5, "suppression_key": "supply:met"
    })
    dec2 = decide(cat, m, trg2)
    msg2 = compose(dec2, cat, m, trg2)

    assert msg1.body != msg2.body
    assert "atorvastatin" in msg1.body
    assert "AT2024-1102" in msg1.body
    assert "metformin 500" in msg2.body
    assert "MET-9901" in msg2.body
    assert "SunPharma" in msg2.body


def test_quality_case_c_offer_variation_reflected(dataset):
    """Case C: Two different delivery offers reflect their distinct titles in the rendered message."""
    cat = dataset["categories"]["restaurants"]
    m1 = dataset["merchants"]["m_005_pizzajunction_restaurant_delhi"]
    trg = dataset["triggers"]["trg_010_ipl_match_delhi"]

    dec1 = decide(cat, m1, trg)
    msg1 = compose(dec1, cat, m1, trg)
    assert "Buy 1 Pizza Get 1 Free (Tue-Thu)" in msg1.body

    # Modify merchant to have a different active delivery offer
    m2_raw = m1.model_dump()
    m2_raw["offers"] = [{"id": "o_combo", "title": "Matchday Feast Combo 20% Off Delivery", "status": "active"}]
    m2 = MerchantState.from_dict(m2_raw)

    dec2 = decide(cat, m2, trg)
    msg2 = compose(dec2, cat, m2, trg)
    assert "Matchday Feast Combo 20% Off Delivery" in msg2.body
    assert msg1.body != msg2.body


def test_quality_case_d_metric_variation_reflected(dataset):
    """Case D: 45% decline vs 18% decline renders the exact varied percentage."""
    cat = dataset["categories"]["gyms"]
    m = dataset["merchants"]["m_007_powerhouse_gym_bangalore"]

    trg_45 = TriggerState.from_dict({
        "id": "trg_dip_45", "scope": "merchant", "kind": "seasonal_perf_dip",
        "source": "internal", "merchant_id": m.merchant_id,
        "payload": {"metric": "views", "delta_pct": -0.45, "is_expected_seasonal": True},
        "urgency": 3, "suppression_key": "dip45"
    })
    msg_45 = compose(decide(cat, m, trg_45), cat, m, trg_45)
    assert "45%" in msg_45.body

    trg_18 = TriggerState.from_dict({
        "id": "trg_dip_18", "scope": "merchant", "kind": "seasonal_perf_dip",
        "source": "internal", "merchant_id": m.merchant_id,
        "payload": {"metric": "views", "delta_pct": -0.18, "is_expected_seasonal": True},
        "urgency": 3, "suppression_key": "dip18"
    })
    msg_18 = compose(decide(cat, m, trg_18), cat, m, trg_18)
    assert "18%" in msg_18.body
    assert msg_45.body != msg_18.body


def test_quality_case_e_customer_variation_no_information_leak(dataset):
    """Case E: Customer A's medicines and details never leak into Customer B's refill message."""
    cat = dataset["categories"]["pharmacies"]
    m = dataset["merchants"]["m_009_apollo_pharmacy_jaipur"]

    # Customer 1: Mr. Sharma with metformin/atorvastatin/telmisartan
    trg1 = dataset["triggers"]["trg_019_chronic_refill_grandfather"]
    c1 = dataset["customers"]["c_013_grandfather_for_m009"]
    msg1 = compose(decide(cat, m, trg1, c1), cat, m, trg1, c1)

    # Customer 2: Priti with calcium/vitamin_d3
    trg2 = TriggerState.from_dict({
        "id": "trg_refill_priti", "scope": "customer", "kind": "chronic_refill_due",
        "source": "internal", "merchant_id": m.merchant_id, "customer_id": "c_014_priti_for_m009",
        "payload": {"molecule_list": ["calcium_500", "vitamin_d3"], "runout_date": "2026-05-02"},
        "urgency": 3, "suppression_key": "refill:priti"
    })
    c2 = dataset["customers"]["c_014_priti_for_m009"]
    msg2 = compose(decide(cat, m, trg2, c2), cat, m, trg2, c2)

    assert "metformin" in msg1.body
    assert "Mr. Sharma" in msg1.body

    assert "calcium_500" in msg2.body
    assert "Priti" in msg2.body
    assert "metformin" not in msg2.body
    assert "Sharma" not in msg2.body
