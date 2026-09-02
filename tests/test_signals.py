"""Tests for signal extraction, percentage normalization, and grounded conditions."""

import json
from pathlib import Path
import pytest

from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.signals import SignalType, extract_signals, format_pct

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


@pytest.fixture
def dentist_category():
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        return CategoryProfile.from_dict(json.load(f))


@pytest.fixture
def meera_merchant():
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        merchants = json.load(f)["merchants"]
    return MerchantState.from_dict(next(m for m in merchants if m["merchant_id"] == "m_001_drmeera_dentist_delhi"))


@pytest.fixture
def bharat_merchant():
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        merchants = json.load(f)["merchants"]
    return MerchantState.from_dict(next(m for m in merchants if m["merchant_id"] == "m_002_bharat_dentist_mumbai"))


def test_percentage_formatting():
    """Verify standard formatting for percentages."""
    assert format_pct(0.18) == "+18%"
    assert format_pct(-0.05) == "-5%"
    assert format_pct(-0.50) == "-50%"
    assert format_pct(0.125) == "+12.5%"


def test_performance_signals_meera(dentist_category, meera_merchant):
    """Verify signals for Dr. Meera: CTR below peer, active offers, high-risk cohort."""
    trigger = TriggerState.from_dict({
        "id": "trg_test_1",
        "scope": "merchant",
        "kind": "curious_ask_due",
        "source": "internal",
        "merchant_id": meera_merchant.merchant_id,
        "payload": {},
        "urgency": 1,
        "suppression_key": "curious:m_001",
    })

    signals = extract_signals(dentist_category, meera_merchant, trigger)
    sig_map = {s.signal_type: s for s in signals}

    # Meera CTR is 0.021 vs peer 0.030 -> CTR_BELOW_PEER
    assert SignalType.CTR_BELOW_PEER in sig_map
    assert sig_map[SignalType.CTR_BELOW_PEER].value == 0.021

    # Meera has active cleaning offer
    assert SignalType.HAS_ACTIVE_OFFER in sig_map

    # Meera has 124 high risk adults in cohort
    assert SignalType.HAS_HIGH_RISK_ADULT_COHORT in sig_map
    assert sig_map[SignalType.HAS_HIGH_RISK_ADULT_COHORT].value == 124


def test_severe_dip_and_unverified_bharat(dentist_category, bharat_merchant):
    """Verify signals for Bharat Dental: calls dropped 50%, unverified listing, expiring plan."""
    trigger = TriggerState.from_dict({
        "id": "trg_004_perf_dip_bharat",
        "scope": "merchant",
        "kind": "perf_dip",
        "source": "internal",
        "merchant_id": bharat_merchant.merchant_id,
        "payload": {
            "metric": "calls",
            "delta_pct": -0.50,
            "window": "7d",
            "vs_baseline": 8,
        },
        "urgency": 4,
        "suppression_key": "perf_dip:m_002",
    })

    signals = extract_signals(dentist_category, bharat_merchant, trigger)
    sig_map = {s.signal_type: s for s in signals}

    assert SignalType.PERF_CALLS_DROP_SEVERE in sig_map
    assert sig_map[SignalType.PERF_CALLS_DROP_SEVERE].value == -0.50
    assert SignalType.UNVERIFIED_LISTING in sig_map
    assert SignalType.SUBSCRIPTION_EXPIRING in sig_map
    assert SignalType.HAS_ACTIVE_OFFER not in sig_map  # Zero active offers!


def test_customer_consent_signals():
    """Verify that customer consent status is accurately categorized."""
    # 1. Opted in customer (Priya)
    with open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8") as f:
        customers = json.load(f)["customers"]
    priya = CustomerStateModel.from_dict(next(c for c in customers if c["customer_id"] == "c_001_priya_for_m001"))

    # Minimal dummy merchant/category/trigger
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat = CategoryProfile.from_dict(json.load(f))
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        m = MerchantState.from_dict(json.load(f)["merchants"][0])
    trg = TriggerState.from_dict({
        "id": "trg_rec", "scope": "customer", "kind": "recall_due",
        "source": "internal", "merchant_id": m.merchant_id, "customer_id": priya.customer_id,
        "payload": {"service_due": "6_month_cleaning"}, "urgency": 3, "suppression_key": "rec"
    })

    signals_priya = extract_signals(cat, m, trg, priya)
    sig_types_priya = {s.signal_type for s in signals_priya}
    assert SignalType.CUSTOMER_CONSENT_VALID in sig_types_priya
    assert SignalType.CUSTOMER_OPTED_OUT not in sig_types_priya

    # 2. Opted out / Anonymous customer (c_015)
    c_015 = CustomerStateModel.from_dict(next(c for c in customers if c["customer_id"] == "c_015_anonymous_for_m010"))
    signals_anon = extract_signals(cat, m, trg, c_015)
    sig_types_anon = {s.signal_type for s in signals_anon}
    assert SignalType.CUSTOMER_OPTED_OUT in sig_types_anon
    assert SignalType.CUSTOMER_CONSENT_VALID not in sig_types_anon


def test_event_and_contrarian_home_viewing_shift():
    """Verify Saturday IPL match in restaurant vertical triggers home-viewing shift."""
    with open(DATASET_DIR / "categories" / "restaurants.json", "r", encoding="utf-8") as f:
        cat = CategoryProfile.from_dict(json.load(f))
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        m = MerchantState.from_dict(next(m for m in json.load(f)["merchants"] if m["merchant_id"] == "m_005_pizzajunction_restaurant_delhi"))

    trg = TriggerState.from_dict({
        "id": "trg_ipl", "scope": "merchant", "kind": "ipl_match_today",
        "source": "external", "merchant_id": m.merchant_id,
        "payload": {
            "match": "DC vs MI",
            "venue": "Arun Jaitley Stadium",
            "is_weeknight": False,  # Saturday match!
        },
        "urgency": 3,
        "suppression_key": "ipl"
    })

    signals = extract_signals(cat, m, trg)
    sig_types = {s.signal_type for s in signals}
    assert SignalType.EVENT_TODAY in sig_types
    assert SignalType.EVENT_HOME_VIEWING_SHIFT in sig_types
    assert SignalType.HAS_DELIVERY_OFFER in sig_types
