"""Tests for POST /v1/context endpoint handling versioning, validation, and freshness."""

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


def test_push_valid_category_context():
    """Verify pushing valid category returns 200 with ack_id and stored_at."""
    client = TestClient(app)
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat_data = json.load(f)

    resp = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "delivered_at": "2026-04-26T09:45:00Z",
        "payload": cat_data,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] is True
    assert data["ack_id"] == "ack_dentists_v1"
    assert "stored_at" in data


def test_push_stale_version_rejected_with_409():
    """Verify pushing same or lower version returns 409 with stale_version and current_version."""
    client = TestClient(app)
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat_data = json.load(f)

    # Push v1 -> 200
    resp1 = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "delivered_at": "2026-04-26T09:45:00Z",
        "payload": cat_data,
    })
    assert resp1.status_code == 200

    # Push v1 again -> 409
    resp2 = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "delivered_at": "2026-04-26T09:45:10Z",
        "payload": cat_data,
    })
    assert resp2.status_code == 409
    data2 = resp2.json()
    assert data2["accepted"] is False
    assert data2["reason"] == "stale_version"
    assert data2["current_version"] == 1


def test_push_version_bump_replaces_atomically():
    """Verify version 2 replaces version 1 smoothly."""
    client = TestClient(app)
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat_data = json.load(f)

    # Push v1
    client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": cat_data,
    })

    # Push v2
    resp = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 2,
        "delivered_at": "2026-04-26T10:30:00Z",
        "payload": cat_data,
    })
    assert resp.status_code == 200
    assert resp.json()["ack_id"] == "ack_dentists_v2"


def test_push_invalid_scope_returns_400():
    """Verify unknown scope returns 400 error."""
    client = TestClient(app)
    resp = client.post("/v1/context", json={
        "scope": "unknown_scope",
        "context_id": "test_id",
        "version": 1,
        "payload": {"some": "data"},
    })
    assert resp.status_code in (400, 422)


def test_push_malformed_payload_returns_400():
    """Verify invalid domain payload returns 400."""
    client = TestClient(app)
    resp = client.post("/v1/context", json={
        "scope": "merchant",
        "context_id": "m_bad",
        "version": 1,
        "payload": {"missing_required_fields": True},
    })
    assert resp.status_code == 400
    data = resp.json()
    assert data["accepted"] is False
    assert data["reason"] == "invalid_payload"
