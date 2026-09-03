"""Tests for GET /v1/healthz endpoint."""

import pytest
from tests.client import TestClient
from app.main import app
from app.api.routes import get_service


@pytest.fixture(autouse=True)
def clean_service():
    service = get_service()
    service.clear()
    yield
    service.clear()


def test_healthz_initial_state():
    """Verify healthz returns 200, status=ok, uptime, and 0 counts initially."""
    client = TestClient(app)
    resp = client.get("/v1/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0
    assert data["contexts_loaded"] == {
        "category": 0,
        "merchant": 0,
        "customer": 0,
        "trigger": 0,
    }


def test_healthz_counts_increment_on_context_push():
    """Verify healthz context counts increment accurately when contexts are pushed."""
    from pathlib import Path
    import json
    dataset_dir = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"
    client = TestClient(app)
    service = get_service()

    with open(dataset_dir / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat_data = json.load(f)
    with open(dataset_dir / "merchants_seed.json", "r", encoding="utf-8") as f:
        m_data = json.load(f)["merchants"][0]

    service.push_context(
        scope="category",
        context_id="dentists",
        version=1,
        payload=cat_data,
    )
    service.push_context(
        scope="merchant",
        context_id=m_data["merchant_id"],
        version=1,
        payload=m_data,
    )

    resp = client.get("/v1/healthz")
    assert resp.status_code == 200
    counts = resp.json()["contexts_loaded"]
    assert counts["category"] == 1
    assert counts["merchant"] == 1
    assert counts["customer"] == 0
    assert counts["trigger"] == 0
