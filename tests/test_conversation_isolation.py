"""Tests proving strict conversation and tenant isolation."""

from tests.client import TestClient
from app.main import app
from app.api.routes import get_service


def test_conversation_isolation():
    """Verify conversation A state transitions do not bleed into conversation B."""
    service = get_service()
    service.clear()
    client = TestClient(app)

    # Conversation A ends via hostile opt-out
    r_a = client.post("/v1/reply", json={
        "conversation_id": "conv_alpha",
        "merchant_id": "m_001",
        "from_role": "merchant",
        "message": "Stop messaging me. This is useless spam.",
        "received_at": "2026-04-26T10:00:00Z",
        "turn_number": 1,
    }).json()
    assert r_a["action"] == "end"

    # Conversation B for same merchant remains healthy and actionable
    r_b = client.post("/v1/reply", json={
        "conversation_id": "conv_beta",
        "merchant_id": "m_001",
        "from_role": "merchant",
        "message": "Ok lets do it. Whats next?",
        "received_at": "2026-04-26T10:05:00Z",
        "turn_number": 1,
    }).json()
    assert r_b["action"] == "send"
    assert "draft" in r_b["body"].lower() or "sending" in r_b["body"].lower()

    # Conversation C for different merchant with same turn message remains waiting
    r_c = client.post("/v1/reply", json={
        "conversation_id": "conv_gamma",
        "merchant_id": "m_002",
        "from_role": "merchant",
        "message": "okay thanks",
        "received_at": "2026-04-26T10:10:00Z",
        "turn_number": 1,
    }).json()
    assert r_c["action"] == "wait"
