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
    assert "draft" in data["body"].lower() or "confirm" in data["body"].lower() or "details" in data["body"].lower()


def test_reply_consecutive_vs_interleaved_auto_replies():
    """Verify consecutive auto-replies trigger END on 3rd run, but interleaved do not."""
    client = TestClient(app)
    auto_msg = "Thank you for contacting us! Our team will respond shortly."
    normal_msg = "Can you share the draft?"

    # --- Scenario 1: 3 Consecutive Auto-Replies -> END ---
    cid_consec = "conv_consecutive_test"
    r1 = client.post("/v1/reply", json={"conversation_id": cid_consec, "merchant_id": "m_001", "message": auto_msg, "received_at": "2026-04-26T10:00:00Z", "turn_number": 1}).json()
    assert r1["action"] == "wait"
    assert r1["wait_seconds"] == 14400

    r2 = client.post("/v1/reply", json={"conversation_id": cid_consec, "merchant_id": "m_001", "message": auto_msg, "received_at": "2026-04-26T10:05:00Z", "turn_number": 2}).json()
    assert r2["action"] == "wait"

    r3 = client.post("/v1/reply", json={"conversation_id": cid_consec, "merchant_id": "m_001", "message": auto_msg, "received_at": "2026-04-26T10:10:00Z", "turn_number": 3}).json()
    assert r3["action"] == "end"
    assert "3 consecutive auto-replies" in r3["rationale"]

    # --- Scenario 2: Interleaved (auto -> normal -> auto -> normal -> auto) -> NOT END ---
    cid_inter = "conv_interleaved_test"
    # Turn 1: auto (consecutive: 1)
    i1 = client.post("/v1/reply", json={"conversation_id": cid_inter, "merchant_id": "m_001", "message": auto_msg, "received_at": "2026-04-26T10:00:00Z", "turn_number": 1}).json()
    assert i1["action"] == "wait"

    # Turn 2: normal
    i2 = client.post("/v1/reply", json={"conversation_id": cid_inter, "merchant_id": "m_001", "message": normal_msg, "received_at": "2026-04-26T10:05:00Z", "turn_number": 2}).json()
    assert i2["action"] == "send"

    # Turn 3: auto (consecutive: 1, reset by turn 2)
    i3 = client.post("/v1/reply", json={"conversation_id": cid_inter, "merchant_id": "m_001", "message": auto_msg, "received_at": "2026-04-26T10:10:00Z", "turn_number": 3}).json()
    assert i3["action"] == "wait"

    # Turn 4: normal
    i4 = client.post("/v1/reply", json={"conversation_id": cid_inter, "merchant_id": "m_001", "message": normal_msg, "received_at": "2026-04-26T10:15:00Z", "turn_number": 4}).json()
    assert i4["action"] == "send"

    # Turn 5: auto (consecutive: 1, reset by turn 4) -> must still be WAIT, NOT END!
    i5 = client.post("/v1/reply", json={"conversation_id": cid_inter, "merchant_id": "m_001", "message": auto_msg, "received_at": "2026-04-26T10:20:00Z", "turn_number": 5}).json()
    assert i5["action"] == "wait"
    assert i5["wait_seconds"] == 14400


def test_reply_empty_message_handling():
    """Verify empty or whitespace message returns deterministic wait rather than crashing."""
    client = TestClient(app)
    resp = client.post("/v1/reply", json={
        "conversation_id": "conv_empty",
        "merchant_id": "m_001",
        "message": "   ",
        "received_at": "2026-04-26T10:00:00Z",
        "turn_number": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "wait"
    assert "Empty message" in data["rationale"]

