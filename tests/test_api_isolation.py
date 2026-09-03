"""Tests verifying state isolation and request independence across merchants and customers."""

import json
from pathlib import Path
import pytest
from tests.client import TestClient

from app.main import app
from app.api.routes import get_service

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


@pytest.fixture(autouse=True)
def clean_service():
    service = get_service()
    service.clear()
    yield
    service.clear()


def test_merchant_context_isolation():
    """Verify tick requests for two different merchants use only their respective contexts."""
    client = TestClient(app)

    # 1. Push category
    with open(DATASET_DIR / "categories" / "salons.json", "r", encoding="utf-8") as f:
        cat_data = json.load(f)
    client.post("/v1/context", json={"scope": "category", "context_id": "salons", "version": 1, "payload": cat_data})

    # 2. Push Merchant A (Studio11)
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        merchants = {m["merchant_id"]: m for m in json.load(f)["merchants"]}
    m_a = merchants["m_003_studio11_salon_hyderabad"]
    client.post("/v1/context", json={"scope": "merchant", "context_id": m_a["merchant_id"], "version": 1, "payload": m_a})

    # 3. Push Merchant B (Glamour) with active subscription
    m_b = dict(merchants["m_004_glamour_salon_pune"])
    m_b["subscription"] = {"status": "active", "plan": "Pro"}
    client.post("/v1/context", json={"scope": "merchant", "context_id": m_b["merchant_id"], "version": 1, "payload": m_b})

    # 4. Push Triggers for both
    trg_a = {
        "id": "trg_a", "scope": "merchant", "kind": "curious_ask_due",
        "source": "internal", "merchant_id": m_a["merchant_id"], "payload": {}, "urgency": 2, "suppression_key": "cur_a"
    }
    trg_b = {
        "id": "trg_b", "scope": "merchant", "kind": "curious_ask_due",
        "source": "internal", "merchant_id": m_b["merchant_id"], "payload": {}, "urgency": 2, "suppression_key": "cur_b"
    }
    client.post("/v1/context", json={"scope": "trigger", "context_id": "trg_a", "version": 1, "payload": trg_a})
    client.post("/v1/context", json={"scope": "trigger", "context_id": "trg_b", "version": 1, "payload": trg_b})

    # 5. Tick A
    resp_a = client.post("/v1/tick", json={"now": "2026-04-26T10:00:00Z", "available_triggers": ["trg_a"]})
    act_a = resp_a.json()["actions"][0]
    assert "Studio11 Family Salon" in act_a["body"]
    assert "Glamour" not in act_a["body"]

    # 6. Tick B
    resp_b = client.post("/v1/tick", json={"now": "2026-04-26T10:00:00Z", "available_triggers": ["trg_b"]})
    act_b = resp_b.json()["actions"][0]
    assert "Glamour Lounge Spa & Salon" in act_b["body"]
    assert "Studio11" not in act_b["body"]


def test_interleaved_context_updates_do_not_contaminate():
    """Verify updating Merchant A's context does not change Merchant B's rendered output."""
    client = TestClient(app)

    with open(DATASET_DIR / "categories" / "salons.json", "r", encoding="utf-8") as f:
        cat_data = json.load(f)
    client.post("/v1/context", json={"scope": "category", "context_id": "salons", "version": 1, "payload": cat_data})

    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        merchants = {m["merchant_id"]: m for m in json.load(f)["merchants"]}
    m_b = dict(merchants["m_004_glamour_salon_pune"])
    m_b["subscription"] = {"status": "active", "plan": "Pro"}
    client.post("/v1/context", json={"scope": "merchant", "context_id": m_b["merchant_id"], "version": 1, "payload": m_b})

    trg_b = {
        "id": "trg_b", "scope": "merchant", "kind": "curious_ask_due",
        "source": "internal", "merchant_id": m_b["merchant_id"], "payload": {}, "urgency": 2, "suppression_key": "cur_b"
    }
    client.post("/v1/context", json={"scope": "trigger", "context_id": "trg_b", "version": 1, "payload": trg_b})

    # Baseline response for B
    resp_b1 = client.post("/v1/tick", json={"now": "2026-04-26T10:00:00Z", "available_triggers": ["trg_b"]})
    body_b1 = resp_b1.json()["actions"][0]["body"]

    # Now update unrelated Merchant A
    m_a = merchants["m_003_studio11_salon_hyderabad"]
    client.post("/v1/context", json={"scope": "merchant", "context_id": m_a["merchant_id"], "version": 1, "payload": m_a})
    client.post("/v1/context", json={"scope": "merchant", "context_id": m_a["merchant_id"], "version": 2, "payload": m_a})

    # Response for B should be bit-for-bit identical
    resp_b2 = client.post("/v1/tick", json={"now": "2026-04-26T10:00:00Z", "available_triggers": ["trg_b"]})
    body_b2 = resp_b2.json()["actions"][0]["body"]
    assert body_b1 == body_b2
