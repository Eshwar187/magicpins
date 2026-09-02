"""Tests verifying strict factual grounding of composed messages."""

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


def test_research_digest_grounded_numbers_and_citation(dataset):
    """Verify research digest message contains grounded trial N, percentage, and citation."""
    cat = dataset["categories"]["dentists"]
    m = dataset["merchants"]["m_001_drmeera_dentist_delhi"]
    trg = dataset["triggers"]["trg_001_research_digest_dentists"]

    decision = decide(cat, m, trg)
    msg = compose(decision, cat, m, trg)

    # Must contain verified citation
    assert "JIDA" in msg.body
    assert "p.14" in msg.body or "Oct 2026" in msg.body
    # Must contain patient trial number or cohort
    assert "2,100" in msg.body or "124" in msg.body
    # Must NOT contain taboo phrases
    for taboo in cat.voice.vocab_taboo:
        assert taboo.lower() not in msg.body.lower()


def test_supply_alert_grounded_batches_and_counts(dataset):
    """Verify pharmacy supply alert contains exact grounded batch IDs and affected counts."""
    cat = dataset["categories"]["pharmacies"]
    m = dataset["merchants"]["m_009_apollo_pharmacy_jaipur"]
    trg = dataset["triggers"]["trg_018_supply_atorvastatin_recall"]

    decision = decide(cat, m, trg)
    msg = compose(decision, cat, m, trg)

    # Must contain exact batch numbers from trigger payload
    batches = trg.payload.get("affected_batches", [])
    for b in batches:
        assert b in msg.body
    # Must contain grounded affected patient count
    assert "22" in msg.body
    # Must contain manufacturer
    assert "Mfr Z" in msg.body or trg.payload.get("manufacturer") in msg.body


def test_contrarian_delivery_grounded_offer_and_shift(dataset):
    """Verify contrarian delivery message cites active offer and exact shift percentage."""
    cat = dataset["categories"]["restaurants"]
    m = dataset["merchants"]["m_005_pizzajunction_restaurant_delhi"]
    trg = dataset["triggers"]["trg_010_ipl_match_delhi"]

    decision = decide(cat, m, trg)
    msg = compose(decision, cat, m, trg)

    # Shift is -12% for Saturday match
    assert "-12%" in msg.body
    # Supporting offer is active BOGO pizza offer
    assert "Buy 1" in msg.body or "Free" in msg.body
    # Team names from payload
    assert "DC vs MI" in msg.body


def test_no_category_template_synthesis(dataset):
    """Verify that category catalog templates never leak into composed messages as merchant offers."""
    cat = dataset["categories"]["restaurants"]
    merchant_raw = {
        "merchant_id": "m_no_offers",
        "category_slug": "restaurants",
        "identity": {"name": "Test Diner", "city": "Delhi", "locality": "CP", "place_id": "x", "verified": True},
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
    msg = compose(decision, cat, m, trg)

    # Since no active delivery offer exists, decide returned WAIT
    assert msg.action == "wait"
    assert msg.body == ""
    assert msg.cta == "none"
