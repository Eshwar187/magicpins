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

    for _ in range(100):
        resp = client.post("/v1/tick", json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trg_data["id"]]})
        assert resp.json() == base_json
