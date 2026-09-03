"""Tests for POST /v1/tick endpoint."""

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


def test_tick_returns_action_for_grounded_trigger():
    """Verify tick generates action with conversation_id, body, cta, and rationale."""
    client = TestClient(app)

    # 1. Push category
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat_data = json.load(f)
    client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": cat_data})

    # 2. Push merchant
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        m_data = json.load(f)["merchants"][0]
    client.post("/v1/context", json={"scope": "merchant", "context_id": m_data["merchant_id"], "version": 1, "payload": m_data})

    # 3. Push trigger
    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        trg_data = json.load(f)["triggers"][0]
    client.post("/v1/context", json={"scope": "trigger", "context_id": trg_data["id"], "version": 1, "payload": trg_data})

    # 4. Tick
    resp = client.post("/v1/tick", json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trg_data["id"]]})
    assert resp.status_code == 200
    data = resp.json()
    assert "actions" in data
    assert len(data["actions"]) == 1

    act = data["actions"][0]
    assert act["merchant_id"] == m_data["merchant_id"]
    assert act["trigger_id"] == trg_data["id"]
    assert act["send_as"] == "vera"
    assert "Dr. Meera" in act["body"]
    assert act["cta"] == "binary_yes_no"
    assert act["suppression_key"].startswith("research:dentists:")
    assert len(act["rationale"]) > 0


def test_tick_returns_empty_actions_when_wait():
    """Verify tick returns empty actions when no trigger qualifies or decision is WAIT."""
    client = TestClient(app)
    resp = client.post("/v1/tick", json={"now": "2026-04-26T10:35:00Z", "available_triggers": []})
    assert resp.status_code == 200
    assert resp.json() == {"actions": []}
