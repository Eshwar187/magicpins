"""Tests verifying bit-for-bit determinism across repeated HTTP requests."""

import json
from pathlib import Path
from tests.client import TestClient

from app.main import app
from app.api.routes import get_service

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


def test_100_runs_api_determinism():
    """Verify that 100 repeated tick requests with identical input produce identical serialized JSON responses."""
    service = get_service()
    service.clear()
    client = TestClient(app)

    # 1. Setup context
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat_data = json.load(f)
    client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": cat_data})

    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        m_data = json.load(f)["merchants"][0]
    client.post("/v1/context", json={"scope": "merchant", "context_id": m_data["merchant_id"], "version": 1, "payload": m_data})

    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        trg_data = json.load(f)["triggers"][0]
    client.post("/v1/context", json={"scope": "trigger", "context_id": trg_data["id"], "version": 1, "payload": trg_data})

    # Reference run
    base_resp = client.post("/v1/tick", json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trg_data["id"]]})
    base_json = base_resp.json()
    assert len(base_json["actions"]) == 1

    # 1. Determinism with identical state (cleared history between calls)
    for _ in range(50):
        service.governance.clear()
        resp = client.post("/v1/tick", json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trg_data["id"]]})
        assert resp.json() == base_json

    # 2. Determinism of repeated ticks under governance (all suppressed duplicates)
    supp_resp = client.post("/v1/tick", json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trg_data["id"]]})
    supp_json = supp_resp.json()
    assert supp_json == {"actions": []}

    for _ in range(50):
        resp = client.post("/v1/tick", json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trg_data["id"]]})
        assert resp.json() == supp_json


def test_100_runs_reply_determinism():
    """Verify that 100 repeated reply requests with identical input produce byte-identical responses."""
    client = TestClient(app)
    payload = {
        "conversation_id": "conv_det_reply",
        "merchant_id": "m_001_drmeera",
        "from_role": "merchant",
        "message": "Ok lets do it. Whats next?",
        "received_at": "2026-04-26T10:42:00Z",
        "turn_number": 2,
    }
    base_resp = client.post("/v1/reply", json=payload)
    base_json = base_resp.json()

    for _ in range(100):
        resp = client.post("/v1/reply", json=payload)
        assert resp.json() == base_json

