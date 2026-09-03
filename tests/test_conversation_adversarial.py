"""Adversarial and boundary test suite for Phase 6 conversation handling."""

import pytest
from tests.client import TestClient
from app.main import app
from app.api.routes import get_service


@pytest.fixture
def client():
    service = get_service()
    service.clear()
    return TestClient(app)


def test_adversarial_phrases(client):
    """Verify adversarial phrases map to expected actions without crashes."""
    test_cases = [
        # Neutral acknowledgements -> wait
        ("ok", "wait"),
        ("okay", "wait"),
        ("ok thanks", "wait"),
        ("great", "wait"),
        ("interesting", "wait"),
        ("yes", "wait"),
        # Actionable commitment -> send
        ("yes let's do it", "send"),
        ("what's next?", "send"),
        ("can we do this?", "send"),
        ("do it", "send"),
        # Hostile / Opt-out -> end
        ("stop", "end"),
        ("STOP", "end"),
        ("stop messaging me", "end"),
        ("this is spam", "end"),
        ("not interested", "end"),
        ("not interested, stop messaging me", "end"),
        ("fine, but don't contact me again", "end"),
    ]

    for msg, expected_action in test_cases:
        cid = f"conv_adv_{abs(hash(msg))}"
        resp = client.post("/v1/reply", json={
            "conversation_id": cid,
            "merchant_id": "m_test",
            "from_role": "merchant",
            "message": msg,
            "received_at": "2026-04-26T10:00:00Z",
            "turn_number": 1,
        })
        assert resp.status_code == 200, f"Failed HTTP 200 on '{msg}'"
        data = resp.json()
        assert data["action"] == expected_action, f"Failed on '{msg}': expected {expected_action}, got {data['action']}"


def test_adversarial_edge_cases(client):
    """Verify empty, whitespace, very long, and mixed-case inputs are handled safely."""
    # 1. Empty message
    r_empty = client.post("/v1/reply", json={
        "conversation_id": "conv_edge_empty",
        "merchant_id": "m_001",
        "message": "",
        "received_at": "2026-04-26T10:00:00Z",
        "turn_number": 1,
    }).json()
    assert r_empty["action"] == "wait"

    # 2. Whitespace-only
    r_ws = client.post("/v1/reply", json={
        "conversation_id": "conv_edge_ws",
        "merchant_id": "m_001",
        "message": "    \t\n   ",
        "received_at": "2026-04-26T10:00:00Z",
        "turn_number": 1,
    }).json()
    assert r_ws["action"] == "wait"

    # 3. Very long message (10,000 characters)
    long_msg = "Hello Vera! " * 800 + "Let's do it, what's next?"
    r_long = client.post("/v1/reply", json={
        "conversation_id": "conv_edge_long",
        "merchant_id": "m_001",
        "message": long_msg,
        "received_at": "2026-04-26T10:00:00Z",
        "turn_number": 1,
    }).json()
    assert r_long["action"] == "send"

    # 4. Mixed-case and punctuation variants
    mixed_msg = "oK! lEt'S dO iT... wHaT's NeXt???"
    r_mixed = client.post("/v1/reply", json={
        "conversation_id": "conv_edge_mixed",
        "merchant_id": "m_001",
        "message": mixed_msg,
        "received_at": "2026-04-26T10:00:00Z",
        "turn_number": 1,
    }).json()
    assert r_mixed["action"] == "send"


def test_reply_determinism(client):
    """Verify identical inputs produce bit-for-bit identical responses across 10 iterations."""
    payload = {
        "conversation_id": "conv_det_test",
        "merchant_id": "m_001",
        "from_role": "merchant",
        "message": "Ok lets do it. Whats next?",
        "received_at": "2026-04-26T10:00:00Z",
        "turn_number": 1,
    }
    responses = []
    for _ in range(10):
        get_service().clear()
        resp = client.post("/v1/reply", json=payload).json()
        responses.append(resp)

    for i in range(1, 10):
        assert responses[i] == responses[0], f"Determinism mismatch at run {i}"
