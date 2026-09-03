"""Tests for POST /v1/reply endpoint covering auto-reply, opt-out, commitment, and curveballs."""

from tests.client import TestClient
from app.main import app


def test_reply_auto_reply_hell():
    """Verify bot detects canned auto-reply message and returns action=wait with wait_seconds."""
    client = TestClient(app)
    resp = client.post("/v1/reply", json={
        "conversation_id": "conv_test_auto",
        "merchant_id": "m_001_drmeera",
        "customer_id": None,
        "from_role": "merchant",
        "message": "Thank you for contacting Dr. Meera's Dental Clinic! Our team will respond shortly.",
        "received_at": "2026-04-26T10:42:00Z",
        "turn_number": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "wait"
    assert data["wait_seconds"] == 14400
    assert "auto-reply" in data["rationale"].lower()


def test_reply_hostile_opt_out():
    """Verify bot ends conversation on hostile opt-out."""
    client = TestClient(app)
    resp = client.post("/v1/reply", json={
        "conversation_id": "conv_test_hostile",
        "merchant_id": "m_001_drmeera",
        "from_role": "merchant",
        "message": "Stop messaging me. This is useless spam.",
        "received_at": "2026-04-26T10:42:00Z",
        "turn_number": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "end"
    assert "opted out" in data["rationale"].lower()


def test_reply_intent_commitment():
    """Verify bot switches to actioning mode and avoids qualifying questions on merchant commitment."""
    client = TestClient(app)
    resp = client.post("/v1/reply", json={
        "conversation_id": "conv_test_commitment",
        "merchant_id": "m_001_drmeera",
        "from_role": "merchant",
        "message": "Ok lets do it. Whats next?",
        "received_at": "2026-04-26T10:42:00Z",
        "turn_number": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    body = data["body"].lower()

    # Judge simulator verification: must contain actioning words
    actioning = ["done", "sending", "draft", "here", "confirm", "proceed", "next"]
    qualifying = ["would you", "do you", "can you tell", "what if", "how about"]

    assert any(w in body for w in actioning)
    assert not any(w in body for w in qualifying)


def test_reply_curveball_redirect():
    """Verify bot politely redirects out-of-scope asks without losing thread."""
    client = TestClient(app)
    resp = client.post("/v1/reply", json={
        "conversation_id": "conv_test_curveball",
        "merchant_id": "m_001_drmeera",
        "from_role": "merchant",
        "message": "Can you also help me with my GST filing this month?",
        "received_at": "2026-04-26T10:42:00Z",
        "turn_number": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "send"
    assert "tax" in data["body"].lower() or "ca" in data["body"].lower() or "accounting" in data["body"].lower()
