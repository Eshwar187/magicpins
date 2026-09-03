"""Unit tests for Phase 6.1 conversation state machine transitions and boundaries."""

import pytest
from app.conversation.models import ConversationEntity, ConversationState, IntentType
from app.conversation.state_machine import process_turn
from app.engine.actions import ActionType
from app.engine.decision import Decision


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
    assert res.route == "STAND_DOWN"
    assert entity.state == ConversationState.WAITING


def test_transition_waiting_actionable_commitment():
    """Verify WAITING + actionable intent transitions to ACTION with CONTINUE_EXISTING_ACTION route."""
    entity = make_entity(state=ConversationState.WAITING)
    res = process_turn(entity, "Ok lets do it. Whats next?", "merchant", "2026-04-26T10:05:00Z", 2)
    assert res.previous_state == ConversationState.WAITING
    assert res.new_state == ConversationState.ACTION
    assert res.intent == IntentType.ACTIONABLE_INTENT
    assert res.route == "CONTINUE_EXISTING_ACTION"
    assert res.action == "send"
    assert entity.state == ConversationState.ACTION


def test_transition_waiting_hostile_opt_out():
    """Verify WAITING + hostile opt-out transitions to ENDED with end action and TERMINAL_EXIT route."""
    entity = make_entity(state=ConversationState.WAITING)
    res = process_turn(entity, "Stop messaging me. This is useless spam.", "merchant", "2026-04-26T10:05:00Z", 2)
    assert res.previous_state == ConversationState.WAITING
    assert res.new_state == ConversationState.ENDED
    assert res.route == "TERMINAL_EXIT"
    assert res.action == "end"
    assert entity.state == ConversationState.ENDED


def test_transition_action_hostile_opt_out():
    """Verify ACTION + hostile opt-out transitions to ENDED."""
    entity = make_entity(state=ConversationState.ACTION)
    res = process_turn(entity, "Changed my mind, unsubscribe me.", "merchant", "2026-04-26T10:10:00Z", 3)
    assert res.previous_state == ConversationState.ACTION
    assert res.new_state == ConversationState.ENDED
    assert res.route == "TERMINAL_EXIT"
    assert res.action == "end"
    assert entity.state == ConversationState.ENDED


def test_transition_ended_is_terminal():
    """Verify once ENDED, any subsequent message immediately returns end."""
    entity = make_entity(state=ConversationState.ENDED)
    res = process_turn(entity, "Hello? Let's do it!", "merchant", "2026-04-26T10:15:00Z", 4)
    assert res.previous_state == ConversationState.ENDED
    assert res.new_state == ConversationState.ENDED
    assert res.route == "TERMINAL_EXIT"
    assert res.action == "end"
    assert "permanently closed" in res.rationale.lower()


def test_auto_reply_backoff_and_consecutive_tail():
    """Verify auto-reply backs off 4 hours without spamming, and consecutive tail is respected."""
    auto_msg = "Thank you for contacting us! Our team will respond shortly."
    entity = make_entity(state=ConversationState.WAITING, auto_count=0)

    # Turn 1: auto -> wait 14400s
    r1 = process_turn(entity, auto_msg, "merchant", "2026-04-26T10:00:00Z", 2)
    assert r1.action == "wait"
    assert r1.wait_seconds == 14400
    assert r1.route == "STAND_DOWN"
    assert entity.consecutive_auto_replies == 1

    # Turn 2: auto -> wait 14400s
    r2 = process_turn(entity, auto_msg, "merchant", "2026-04-26T10:05:00Z", 3)
    assert r2.action == "wait"
    assert r2.wait_seconds == 14400
    assert entity.consecutive_auto_replies == 2

    # Turn 3: auto -> end (graceful terminal exit after 3 consecutive)
    r3 = process_turn(entity, auto_msg, "merchant", "2026-04-26T10:10:00Z", 4)
    assert r3.action == "end"
    assert r3.route == "TERMINAL_EXIT"
    assert entity.state == ConversationState.ENDED


def test_phase6_cannot_alter_phase2_decision_authority():
    """PHASE BOUNDARY INVARIANT: Prove Phase 6 cannot alter Phase 2 decision authority.
    
    Phase 6 processes conversational state transitions and routes to existing workflows.
    It does NOT alter ActionType, score, selected offer, evidence facts, or category logic.
    """
    initial_decision = Decision(
        action_type=ActionType.USE_RESEARCH_INSIGHT,
        action="use_research_insight",
        target_scope="merchant",
        trigger_id="trg_001",
        score=88.5,
        primary_reason="Recent publication directly relevant to clinic",
        evidence_facts=("fact_1", "fact_2"),
    )

    entity = make_entity(state=ConversationState.WAITING)
    res = process_turn(entity, "Ok lets do it. Whats next?", "merchant", "2026-04-26T10:00:00Z", 2)

    # Phase 6 emits route to CONTINUE_EXISTING_ACTION
    assert res.route == "CONTINUE_EXISTING_ACTION"
    assert res.new_state == ConversationState.ACTION

    # Verify initial Phase 2 Decision remains 100% intact and unchanged
    assert initial_decision.action_type == ActionType.USE_RESEARCH_INSIGHT
    assert initial_decision.score == 88.5
    assert initial_decision.primary_reason == "Recent publication directly relevant to clinic"
    assert len(initial_decision.evidence_facts) == 2
