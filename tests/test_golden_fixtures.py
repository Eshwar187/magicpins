"""Tests against the 4 canonical golden fixtures from the challenge dataset."""

import json
from pathlib import Path
import pytest

from app.domain.facts.extractor import extract_facts
from app.domain.facts.inventory import format_fact_inventory
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


@pytest.fixture
def categories():
    cats = {}
    for p in (DATASET_DIR / "categories").glob("*.json"):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            cats[data["slug"]] = CategoryProfile.from_dict(data)
    return cats


@pytest.fixture
def merchants():
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        data = json.load(f)["merchants"]
    return {m["merchant_id"]: MerchantState.from_dict(m) for m in data}


@pytest.fixture
def customers():
    with open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8") as f:
        data = json.load(f)["customers"]
    return {c["customer_id"]: CustomerStateModel.from_dict(c) for c in data}


@pytest.fixture
def triggers():
    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        data = json.load(f)["triggers"]
    return {t["id"]: TriggerState.from_dict(t) for t in data}


def test_golden_fixture_1_dr_meera_research(categories, merchants, triggers):
    """Fixture 1: Dr. Meera with JIDA fluoride research digest trigger."""
    cat = categories["dentists"]
    m = merchants["m_001_drmeera_dentist_delhi"]
    trg = triggers["trg_001_research_digest_dentists"]

    facts = extract_facts(cat, m, trg)
    fact_map = {f.name: f for f in facts}

    # Verify merchant identity & location
    assert fact_map["merchant.name"].value == "Dr. Meera's Dental Clinic"
    assert fact_map["merchant.name"].source_path == "identity.name"
    assert fact_map["merchant.owner_first_name"].value == "Meera"
    assert fact_map["merchant.locality"].value == "Lajpat Nagar"
    assert fact_map["merchant.verified"].value is True

    # Verify performance
    assert fact_map["merchant.performance.ctr"].value == 0.021
    assert fact_map["merchant.performance.views"].value == 2410
    assert fact_map["merchant.performance.delta_7d.views_pct"].value == 0.18
    assert fact_map["merchant.performance.delta_7d.calls_pct"].value == -0.05

    # Verify customer aggregate cohort
    assert fact_map["merchant.customer_aggregate.high_risk_adult_count"].value == 124

    # Verify trigger
    assert fact_map["trigger.kind"].value == "research_digest"
    assert fact_map["trigger.payload.top_item_id"].value == "d_2026W17_jida_fluoride"

    # Verify matched digest evidence from category
    assert "category.digest.matched" in fact_map
    matched_ev = fact_map["category.digest.matched"].value
    assert matched_ev["trial_n"] == 2100
    assert matched_ev["patient_segment"] == "high_risk_adults"
    assert "JIDA Oct 2026, p.14" in matched_ev["source"]

    # Verify fact inventory output
    inv_text = format_fact_inventory(facts)
    assert "GROUNDED FACTS" in inv_text
    assert "Dr. Meera's Dental Clinic" in inv_text
    assert "m_001_drmeera_dentist_delhi" in inv_text


def test_golden_fixture_2_priya_recall(categories, merchants, customers, triggers):
    """Fixture 2: Priya 6-month cleaning recall customer trigger."""
    cat = categories["dentists"]
    m = merchants["m_001_drmeera_dentist_delhi"]
    trg = triggers["trg_003_recall_due_priya"]
    cust = customers["c_001_priya_for_m001"]

    facts = extract_facts(cat, m, trg, cust)
    fact_map = {f.name: f for f in facts}

    # Verify customer identity and state
    assert fact_map["customer.name"].value == "Priya"
    assert fact_map["customer.language_pref"].value == "hi-en mix"
    assert fact_map["customer.state"].value == "lapsed_soft"
    assert fact_map["customer.visits_total"].value == 4
    assert fact_map["customer.preferred_slots"].value == "weekday_evening"
    assert fact_map["customer.reminder_opt_in"].value is True
    assert fact_map["customer.consent.scope"].value == ["recall_reminders", "appointment_reminders"]

    # Verify trigger slots
    assert "trigger.payload.available_slots" in fact_map
    slots = fact_map["trigger.payload.available_slots"].value
    assert len(slots) == 2
    assert "Wed 5 Nov, 6pm" in [s["label"] for s in slots]


def test_golden_fixture_3_bharat_severe_dip(categories, merchants, triggers):
    """Fixture 3: Bharat Dental unverified, severe call drop, no active offers."""
    cat = categories["dentists"]
    m = merchants["m_002_bharat_dentist_mumbai"]
    trg = triggers["trg_004_perf_dip_bharat"]

    facts = extract_facts(cat, m, trg)
    fact_map = {f.name: f for f in facts}

    assert fact_map["merchant.verified"].value is False
    assert fact_map["merchant.subscription.days_remaining"].value == 12
    assert fact_map["merchant.performance.calls"].value == 4
    assert fact_map["merchant.performance.delta_7d.calls_pct"].value == -0.50
    assert fact_map["trigger.payload.metric"].value == "calls"
    assert fact_map["trigger.payload.delta_pct"].value == -0.50

    # Ensure zero active offers were fabricated
    offer_facts = [f for f in facts if f.fact_type == "offer"]
    assert len(offer_facts) == 0


def test_golden_fixture_4_anonymous_walkin(categories, merchants, customers, triggers):
    """Fixture 4: Anonymous walk-in with explicit nulls, false opt-in, and empty scope."""
    cat = categories["pharmacies"]
    m = merchants["m_010_sunrisepharm_pharmacy_lucknow"]
    trg = triggers["trg_021_unverified_gbp_sunrise"]
    cust = customers["c_015_anonymous_for_m010"]

    facts = extract_facts(cat, m, trg, cust)
    fact_map = {f.name: f for f in facts}

    assert fact_map["customer.name"].value == "(walk-in, no profile)"
    assert "customer.phone_redacted" not in fact_map  # Was null in raw data, skipped!
    assert fact_map["customer.reminder_opt_in"].value is False  # Explicit boolean false
    assert fact_map["customer.consent.scope"].value == []  # Explicit empty list []
    assert "customer.consent.opted_in_at" not in fact_map  # Was null in raw data, skipped!
