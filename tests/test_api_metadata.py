"""Tests for GET and POST /v1/metadata endpoints."""

from tests.client import TestClient
from app.main import app


def test_metadata_get():
    """Verify GET /v1/metadata returns required judge fields without secrets or PII."""
    client = TestClient(app)
    resp = client.get("/v1/metadata")
    assert resp.status_code == 200
    data = resp.json()

    assert "team_name" in data
    assert "model" in data
    assert "approach" in data
    assert "version" in data
    assert "submitted_at" in data

    # Verify no secrets or PII leaked
    forbidden_keys = ["api_key", "secret", "password", "token", "env"]
    for k in forbidden_keys:
        assert k not in data


def test_metadata_post_not_allowed():
    """Verify POST /v1/metadata returns 405 Method Not Allowed per challenge contract."""
    client = TestClient(app)
    resp = client.post("/v1/metadata")
    assert resp.status_code == 405
