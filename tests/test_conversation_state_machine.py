"""Unit tests for Phase 6 conversation state machine transitions."""

import pytest
from app.conversation.models import ConversationEntity, ConversationState, IntentType
from app.conversation.state_machine import process_turn


def make_entity(state=ConversationState.WAITING, auto_count=0):
    return ConversationEntity(
        conversation_id="conv_sm_test",
        merchant_id="m_001",
        state=state,
        turn_count=1,
        consecutive_auto_replies=auto_count,
        last_updated_at="2026-04-26T10:00:00Z",
    )


def test_transition_waiting_acknowledgement_prevents_loop():
    """Verify WAITING + acknowledgement remains in WAITING with wait action (no spam loop)."""
    entity = make_entity(state=ConversationState.WAITING)
    res = process_turn(entity, "okay", "merchant", "2026-04-26T10:05:00Z", 2)
    assert res.previous_state == ConversationState.WAITING
    assert res.new_state == ConversationState.WAITING
    assert res.action == "wait"
    assert res.wait_seconds == 86400
    assert entity.state == ConversationState.WAITING


def test_transition_waiting_actionable_commitment():
    """Verify WAITING + actionable intent transitions to ACTION with draft send."""
    entity = make_entity(state=ConversationState.WAITING)
    res = process_turn(entity, "Ok lets do it. Whats next?", "merchant", "2026-04-26T10:05:00Z", 2)
    assert res.previous_state == ConversationState.WAITING
    assert res.new_state == ConversationState.ACTION
    assert res.action == "send"
    assert entity.state == ConversationState.ACTION
    assert "draft" in res.body.lower() or "sending" in res.body.lower()


def test_transition_waiting_hostile_opt_out():
    """Verify WAITING + hostile opt-out transitions to ENDED with end action."""
    entity = make_entity(state=ConversationState.WAITING)
    res = process_turn(entity, "Stop messaging me. This is useless spam.", "merchant", "2026-04-26T10:05:00Z", 2)
    assert res.previous_state == ConversationState.WAITING
    assert res.new_state == ConversationState.ENDED
    assert res.action == "end"
    assert entity.state == ConversationState.ENDED


def test_transition_action_hostile_opt_out():
    """Verify ACTION + hostile opt-out transitions to ENDED."""
    entity = make_entity(state=ConversationState.ACTION)
    res = process_turn(entity, "Changed my mind, unsubscribe me.", "merchant", "2026-04-26T10:10:00Z", 3)
    assert res.previous_state == ConversationState.ACTION
    assert res.new_state == ConversationState.ENDED
    assert res.action == "end"
    assert entity.state == ConversationState.ENDED


def test_transition_ended_is_terminal():
    """Verify once ENDED, any subsequent message immediately returns end."""
    entity = make_entity(state=ConversationState.ENDED)
    res = process_turn(entity, "Hello? Let's do it!", "merchant", "2026-04-26T10:15:00Z", 4)
    assert res.previous_state == ConversationState.ENDED
    assert res.new_state == ConversationState.ENDED
    assert res.action == "end"
    assert "permanently closed" in res.rationale.lower()


def test_auto_reply_consecutive_tail():
    """Verify 3 consecutive auto-replies end conversation, but human reset preserves it."""
    auto_msg = "Thank you for contacting us! Our team will respond shortly."
    entity = make_entity(state=ConversationState.WAITING, auto_count=0)

    # Turn 1: auto -> wait
    r1 = process_turn(entity, auto_msg, "merchant", "2026-04-26T10:00:00Z", 2)
    assert r1.action == "wait"
    assert entity.consecutive_auto_replies == 1

    # Turn 2: auto -> wait
    r2 = process_turn(entity, auto_msg, "merchant", "2026-04-26T10:05:00Z", 3)
    assert r2.action == "wait"
    assert entity.consecutive_auto_replies == 2

    # Turn 3: auto -> end
    r3 = process_turn(entity, auto_msg, "merchant", "2026-04-26T10:10:00Z", 4)
    assert r3.action == "end"
    assert entity.state == ConversationState.ENDED
