"""Phase 7.1 Hardening Regression Suite.

Verifies:
1. F1: Strict merchant resolution without hardcoded fallback.
2. F2: Natural intent generalization with absolute hostile precedence.
3. Acknowledgement vs. actionable distinction.
4. Comprehensive compound adversarial matrix.
"""

import pytest
from app.api.service import EngineService
from app.api.schemas import ReplyRequest, ReplyResponse
from app.conversation.classifier import classify_intent
from app.conversation.models import (
    ConversationEntity,
    ConversationState,
    IntentType,
    TransitionResult,
)
from app.conversation.state_machine import process_turn


# =============================================================================
# F1: REMOVE HARD-CODED MERCHANT FALLBACK TESTS
# =============================================================================

def test_f1_known_conversation_entity_merchant():
    """Verify that when merchant_id is omitted, existing conversation entity merchant_id is used."""
    from tests.test_conversation_continuation_grounding import load_dataset
    categories, merchants, triggers, customers, _, _, _, _ = load_dataset()
    svc = EngineService()
    m_data = merchants["m_007_powerhouse_gym_bangalore"].model_dump()
    svc.store.store("merchant", "m_007_powerhouse_gym_bangalore", 1, m_data)
    svc.store.store("category", "gyms", 1, categories["gyms"].model_dump())

    # Initial tick or manual record sets conversation entity merchant_id
    svc.conversations.record_tick_send(
        conversation_id="conv_f1_known",
        merchant_id="m_007_powerhouse_gym_bangalore",
        customer_id=None,
        target_scope="merchant",
        trigger_id="trg_014_seasonal_acquisition_dip_powerhouse",
        send_as="vera",
        body="Initial message",
        now="2026-04-26T10:00:00Z",
    )

    # Inbound reply with omitted merchant_id
    resp = svc.reply(
        conversation_id="conv_f1_known",
        merchant_id=None,  # OMITTED
        customer_id=None,
        from_role="merchant",
        message="Ok lets do it. Whats next?",
        received_at="2026-04-26T10:05:00Z",
        turn_number=2,
    )

    assert resp.action == "send"
    assert resp.cta == "binary_confirm"
    # Entity merchant_id was preserved
    entity = svc.conversations.get("conv_f1_known")
    assert entity.merchant_id == "m_007_powerhouse_gym_bangalore"


def test_f1_no_merchant_identity_does_not_guess():
    """Verify that when merchant_id is omitted and conversation has no merchant, engine does NOT guess."""
    svc = EngineService()
    # Context contains multiple merchants
    svc.store.store("merchant", "m_001_drmeera_dentist_delhi", 1, {"merchant_id": "m_001_drmeera_dentist_delhi", "category_slug": "dentists"})
    svc.store.store("merchant", "m_002_powerhouse_gym_pune", 1, {"merchant_id": "m_002_powerhouse_gym_pune", "category_slug": "gyms"})

    # Fresh conversation without merchant_id in request or entity
    resp = svc.reply(
        conversation_id="conv_f1_unknown",
        merchant_id=None,  # OMITTED
        customer_id=None,
        from_role="merchant",
        message="Ok lets do it. Whats next?",
        received_at="2026-04-26T10:05:00Z",
        turn_number=2,
    )

    assert resp.action == "send"
    assert resp.cta == "binary_confirm"
    # Must use identity-free fallback continuation rather than assuming Dr. Meera
    assert "patient-education" not in resp.body.lower()
    assert "dentist" not in resp.body.lower()
    assert resp.body == "Here is the draft ready to confirm. Confirm when ready to proceed!"


def test_f1_multiple_merchants_no_arbitrary_selection():
    """Verify engine never arbitrarily selects a merchant from context when merchant_id is omitted."""
    svc = EngineService()
    for i in range(5):
        svc.store.store("merchant", f"m_batch_{i}", 1, {"merchant_id": f"m_batch_{i}", "category_slug": "salons"})

    resp = svc.reply(
        conversation_id="conv_multi_no_guess",
        merchant_id=None,
        customer_id=None,
        from_role="merchant",
        message="Ok lets do it. Whats next?",
        received_at="2026-04-26T10:05:00Z",
        turn_number=2,
    )
    # Output must be identity-free fallback
    assert resp.body == "Here is the draft ready to confirm. Confirm when ready to proceed!"
    entity = svc.conversations.get("conv_multi_no_guess")
    assert entity.merchant_id is None


# =============================================================================
# F2: ACTIONABLE INTENT GENERALIZATION (>= 15 EXAMPLES)
# =============================================================================

ACTIONABLE_EXAMPLES = [
    "let's do it",
    "lets do it",
    "let's proceed",
    "lets proceed",
    "let's move forward",
    "move forward",
    "go ahead",
    "okay, go ahead",
    "sure, let's do it",
    "yes, let's proceed",
    "I want to do this",
    "I want to proceed",
    "how do we start?",
    "how do I start?",
    "what's next?",
    "whats next",
    "what should I do next?",
    "let's get started",
    "ready to proceed",
    "proceed with this",
    "send the draft preview",
    "share the details",
    "sign me up",
    "can we do this today?",
]


@pytest.mark.parametrize("phrase", ACTIONABLE_EXAMPLES)
def test_f2_actionable_intent_coverage(phrase):
    """Verify >= 15 natural variations are correctly classified as ACTIONABLE_INTENT."""
    intent, is_auto = classify_intent(phrase)
    assert intent == IntentType.ACTIONABLE_INTENT, f"Failed actionable classification for '{phrase}'"
    assert not is_auto

    entity = ConversationEntity(
        conversation_id="conv_test_act",
        merchant_id="m_test",
        state=ConversationState.WAITING,
        turn_count=1,
        consecutive_auto_replies=0,
        last_updated_at="2026-04-26T10:00:00Z",
    )
    res = process_turn(entity, phrase, "merchant", "2026-04-26T10:05:00Z", 2)
    assert res.previous_state == ConversationState.WAITING
    assert res.new_state == ConversationState.ACTION
    assert res.route == "CONTINUE_EXISTING_ACTION"
    assert res.action == "send"


# =============================================================================
# F2: HOSTILE / OPT-OUT GENERALIZATION (>= 15 EXAMPLES)
# =============================================================================

HOSTILE_EXAMPLES = [
    "stop",
    "STOP",
    "stop messaging me",
    "stop contacting me",
    "don't contact me",
    "do not contact me",
    "never contact me again",
    "no more messages",
    "no more messaging",
    "unsubscribe",
    "remove me",
    "take me off your list",
    "this is spam",
    "this is useless spam",
    "not interested, stop",
    "leave me alone",
    "do not message me again",
    "opt out",
    "opt-out",
]


@pytest.mark.parametrize("phrase", HOSTILE_EXAMPLES)
def test_f2_hostile_intent_coverage(phrase):
    """Verify >= 15 natural variations are correctly classified as HOSTILE_OPT_OUT."""
    intent, _ = classify_intent(phrase)
    assert intent == IntentType.HOSTILE_OPT_OUT, f"Failed hostile classification for '{phrase}'"

    entity = ConversationEntity(
        conversation_id="conv_test_hostile",
        merchant_id="m_test",
        state=ConversationState.WAITING,
        turn_count=1,
        consecutive_auto_replies=0,
        last_updated_at="2026-04-26T10:00:00Z",
    )
    res = process_turn(entity, phrase, "merchant", "2026-04-26T10:05:00Z", 2)
    assert res.new_state == ConversationState.ENDED
    assert res.route == "TERMINAL_EXIT"
    assert res.action == "end"


# =============================================================================
# F2: ACKNOWLEDGEMENT INTENT (>= 8 EXAMPLES)
# =============================================================================

ACKNOWLEDGEMENT_EXAMPLES = [
    "ok",
    "okay",
    "thanks",
    "thank you",
    "got it",
    "sure",
    "understood",
    "noted",
    "fine",
    "cool",
    "yes",
]


@pytest.mark.parametrize("phrase", ACKNOWLEDGEMENT_EXAMPLES)
def test_f2_acknowledgement_coverage(phrase):
    """Verify pure acknowledgements remain ACKNOWLEDGEMENT and do not elevate to ACTION."""
    intent, is_auto = classify_intent(phrase)
    assert intent == IntentType.ACKNOWLEDGEMENT, f"Failed acknowledgement for '{phrase}'"
    assert not is_auto

    entity = ConversationEntity(
        conversation_id="conv_test_ack",
        merchant_id="m_test",
        state=ConversationState.WAITING,
        turn_count=1,
        consecutive_auto_replies=0,
        last_updated_at="2026-04-26T10:00:00Z",
    )
    res = process_turn(entity, phrase, "merchant", "2026-04-26T10:05:00Z", 2)
    assert res.previous_state == ConversationState.WAITING
    assert res.new_state == ConversationState.WAITING
    assert res.route == "STAND_DOWN"
    assert res.action == "wait"
    assert res.wait_seconds == 86400


# =============================================================================
# ABSOLUTE HOSTILE PRECEDENCE: COMPOUND HOSTILE + POSITIVE (>= 10 EXAMPLES)
# =============================================================================

COMPOUND_HOSTILE_EXAMPLES = [
    "yes, but stop messaging me",
    "sure, let's do it, but never contact me again",
    "okay proceed — this is spam",
    "stop, let's do it",
    "okay, but stop",
    "yes, but don't contact me",
    "let's proceed, this is spam",
    "stop, let's proceed",
    "not interested, but yes",
    "Sure, go ahead and unsubscribe me",
    "I want to do this, actually no, remove me from your list",
    "Yes please, but do not message me again",
]


@pytest.mark.parametrize("phrase", COMPOUND_HOSTILE_EXAMPLES)
def test_f2_absolute_hostile_precedence(phrase):
    """Verify hostile phrases have absolute priority across the entire utterance."""
    intent, _ = classify_intent(phrase)
    assert intent == IntentType.HOSTILE_OPT_OUT, f"Hostile precedence failed for '{phrase}'"

    entity = ConversationEntity(
        conversation_id="conv_test_prec",
        merchant_id="m_test",
        state=ConversationState.WAITING,
        turn_count=1,
        consecutive_auto_replies=0,
        last_updated_at="2026-04-26T10:00:00Z",
    )
    res = process_turn(entity, phrase, "merchant", "2026-04-26T10:05:00Z", 2)
    assert res.new_state == ConversationState.ENDED
    assert res.route == "TERMINAL_EXIT"
    assert res.action == "end"


# =============================================================================
# AMBIGUOUS / NEUTRAL INTENT (>= 10 EXAMPLES)
# =============================================================================

NEUTRAL_EXAMPLES = [
    "what time is it?",
    "my phone number is 9876543210",
    "can you call my manager?",
    "where is your office located?",
    "I will check with my partner later",
    "busy in surgery right now",
    "maybe next week",
    "who is this?",
    "is this automated?",
    "send me an email instead",
]


@pytest.mark.parametrize("phrase", NEUTRAL_EXAMPLES)
def test_f2_ambiguous_neutral_fallback(phrase):
    """Verify ambiguous or unclassified messages fall cleanly into NEUTRAL without false positive ACTION."""
    intent, _ = classify_intent(phrase)
    assert intent == IntentType.NEUTRAL, f"Expected NEUTRAL for '{phrase}', got {intent}"


# =============================================================================
# ADVERSARIAL REPLAY DETERMINISM (F1 + F2)
# =============================================================================

def test_f1_f2_determinism_replay():
    """Verify 10 repeated runs of compound inputs produce bit-for-bit identical results."""
    phrase = "sure, let's do it, but never contact me again"
    results = []
    for _ in range(10):
        intent, is_auto = classify_intent(phrase)
        results.append((intent, is_auto))

    assert len(set(results)) == 1, "Intent classification was non-deterministic!"
    assert results[0][0] == IntentType.HOSTILE_OPT_OUT
