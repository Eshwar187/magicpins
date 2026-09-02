"""Tests for customer normalization, consent semantics, and missing value handling."""

import json
from pathlib import Path
import pytest

from app.domain.models.customer import CustomerStateModel

CUSTOMERS_SEED_FILE = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset" / "customers_seed.json"


def test_all_seed_customers_normalize_successfully():
    """Ensure all 15 seed customers normalize without errors."""
    with open(CUSTOMERS_SEED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)["customers"]

    assert len(data) == 15
    for raw in data:
        c = CustomerStateModel.from_dict(raw)
        assert c.customer_id == raw["customer_id"]
        assert c.merchant_id == raw["merchant_id"]
        assert c.identity.name == raw["identity"]["name"]
        assert c.state in ("new", "active", "lapsed_soft", "lapsed_hard", "churned")


def test_priya_seed_fidelity():
    """Verify exact values for Priya (Fixture 2: active consent, 4 visits, lapsed_soft)."""
    with open(CUSTOMERS_SEED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)["customers"]

    priya_raw = next(c for c in data if c["customer_id"] == "c_001_priya_for_m001")
    c = CustomerStateModel.from_dict(priya_raw)

    assert c.identity.name == "Priya"
    assert c.identity.language_pref == "hi-en mix"
    assert c.identity.phone_redacted == "<phone>"
    assert c.state == "lapsed_soft"
    assert c.relationship.visits_total == 4
    assert c.relationship.lifetime_value == 1696
    assert c.preferences.preferred_slots == "weekday_evening"
    assert c.preferences.reminder_opt_in is True
    assert c.consent.opted_in_at == "2025-11-04"
    assert c.consent.scope == ["recall_reminders", "appointment_reminders"]


def test_anonymous_walkin_fidelity_and_distinctions():
    """Verify exact semantics for c_015_anonymous (Fixture 4: explicit nulls, false, and empty list)."""
    with open(CUSTOMERS_SEED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)["customers"]

    anon_raw = next(c for c in data if c["customer_id"] == "c_015_anonymous_for_m010")
    c = CustomerStateModel.from_dict(anon_raw)

    assert c.identity.name == "(walk-in, no profile)"
    assert c.identity.phone_redacted is None  # Raw was JSON null -> None
    assert c.identity.age_band == "unknown"  # Raw was string "unknown"
    assert c.preferences.reminder_opt_in is False  # Explicit boolean false
    assert c.consent.opted_in_at is None  # Raw was JSON null -> None
    assert c.consent.scope == []  # Explicit empty list []


def test_consent_scope_distinction_null_vs_empty_vs_missing():
    """Ensure missing scope, null scope, empty scope [], and populated scope are distinguishable."""
    # 1. Explicit empty list
    c_empty = CustomerStateModel.from_dict({
        "customer_id": "c_empty",
        "merchant_id": "m_1",
        "identity": {"name": "Empty Scope", "language_pref": "en"},
        "relationship": {},
        "state": "new",
        "preferences": {},
        "consent": {"opted_in_at": "2026-01-01", "scope": []},
    })
    assert c_empty.consent.scope == []

    # 2. Explicit null scope
    c_null = CustomerStateModel.from_dict({
        "customer_id": "c_null",
        "merchant_id": "m_1",
        "identity": {"name": "Null Scope", "language_pref": "en"},
        "relationship": {},
        "state": "new",
        "preferences": {},
        "consent": {"opted_in_at": "2026-01-01", "scope": None},
    })
    assert c_null.consent.scope is None

    # 3. Missing scope field
    c_missing = CustomerStateModel.from_dict({
        "customer_id": "c_missing",
        "merchant_id": "m_1",
        "identity": {"name": "Missing Scope", "language_pref": "en"},
        "relationship": {},
        "state": "new",
        "preferences": {},
        "consent": {"opted_in_at": "2026-01-01"},
    })
    assert c_missing.consent.scope is None

    # 4. reminder_opt_in missing vs False
    assert c_missing.preferences.reminder_opt_in is None
