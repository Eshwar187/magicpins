"""Tests for merchant normalization and missing-value fidelity."""

import json
from pathlib import Path
import pytest

from app.domain.models.merchant import MerchantState

MERCHANTS_SEED_FILE = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset" / "merchants_seed.json"


def test_all_seed_merchants_normalize_successfully():
    """Ensure all 10 seed merchants normalize without errors."""
    with open(MERCHANTS_SEED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)["merchants"]

    assert len(data) == 10
    for raw in data:
        m = MerchantState.from_dict(raw)
        assert m.merchant_id == raw["merchant_id"]
        assert m.category_slug == raw["category_slug"]
        assert m.identity.name == raw["identity"]["name"]
        assert m.subscription.status in ("active", "expired", "trial")
        assert m.performance.window_days == 30


def test_missing_values_are_not_converted_to_zero():
    """Verify that missing performance metrics remain None, NOT 0 or 0.0."""
    partial_merchant = {
        "merchant_id": "m_test_missing",
        "category_slug": "dentists",
        "identity": {
            "name": "Missing Test Clinic",
            "city": "Delhi",
            "locality": "Saket",
            "place_id": "ChIJ_TEST",
            "verified": False,
            "languages": ["en"],
        },
        "subscription": {
            "status": "active",
            "plan": "Pro",
        },
        "performance": {
            "window_days": 30,
            # views, calls, ctr intentionally missing!
        },
    }

    m = MerchantState.from_dict(partial_merchant)
    assert m.performance.views is None
    assert m.performance.calls is None
    assert m.performance.ctr is None
    assert m.performance.delta_7d is None
    assert m.identity.owner_first_name is None
    assert m.identity.established_year is None
    assert m.subscription.days_remaining is None
    assert m.subscription.days_since_expiry is None


def test_dr_meera_seed_fidelity():
    """Verify exact values for Dr. Meera (Fixture 1)."""
    with open(MERCHANTS_SEED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)["merchants"]

    meera_raw = next(m for m in data if m["merchant_id"] == "m_001_drmeera_dentist_delhi")
    m = MerchantState.from_dict(meera_raw)

    assert m.identity.name == "Dr. Meera's Dental Clinic"
    assert m.identity.owner_first_name == "Meera"
    assert m.identity.verified is True
    assert m.subscription.status == "active"
    assert m.subscription.days_remaining == 82
    assert m.performance.views == 2410
    assert m.performance.calls == 18
    assert m.performance.ctr == 0.021
    assert m.performance.delta_7d is not None
    assert m.performance.delta_7d.views_pct == 0.18
    assert m.performance.delta_7d.calls_pct == -0.05
    assert len(m.offers) == 2
    assert m.offers[0].status == "active"
    assert m.offers[1].status == "expired"
    assert m.customer_aggregate["high_risk_adult_count"] == 124


def test_bharat_seed_fidelity():
    """Verify exact values for Bharat Dental (Fixture 3: unverified, empty offers, severe dip)."""
    with open(MERCHANTS_SEED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)["merchants"]

    bharat_raw = next(m for m in data if m["merchant_id"] == "m_002_bharat_dentist_mumbai")
    m = MerchantState.from_dict(bharat_raw)

    assert m.identity.name == "Bharat Dental Care"
    assert m.identity.verified is False
    assert m.subscription.days_remaining == 12
    assert m.performance.calls == 4
    assert m.performance.delta_7d.calls_pct == -0.50
    assert len(m.offers) == 0  # Crucial: no active offers fabricated!
