"""Unit tests for Phase 6.1 deterministic intent classification and compound precedence."""

import pytest
from app.conversation.classifier import classify_intent
from app.conversation.models import IntentType


def test_intent_acknowledgement():
    """Verify simple acknowledgements are classified as ACKNOWLEDGEMENT."""
    samples = [
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
        "received",
        "yes",
    ]
    for text in samples:
        intent, is_auto = classify_intent(text)
        assert intent == IntentType.ACKNOWLEDGEMENT, f"Failed for '{text}': got {intent}"
        assert not is_auto


def test_intent_actionable():
    """Verify actionable commitment is classified as ACTIONABLE_INTENT."""
    samples = [
        "let's do it",
        "lets do it",
        "what's next?",
        "whats next",
        "how do i start?",
        "proceed",
        "go ahead",
        "do it",
        "yes let's do it",
        "send the draft",
        "share the preview",
        "can we do this?",
    ]
    for text in samples:
        intent, is_auto = classify_intent(text)
        assert intent == IntentType.ACTIONABLE_INTENT, f"Failed for '{text}': got {intent}"
        assert not is_auto


def test_intent_hostile_opt_out():
    """Verify hostility and opt-out are classified as HOSTILE_OPT_OUT."""
    samples = [
        "stop messaging me",
        "stop",
        "STOP",
        "this is useless spam",
        "not interested",
        "unsubscribe",
        "don't contact me",
        "do not message",
        "leave me alone",
        "remove me",
        "opt out",
    ]
    for text in samples:
        intent, is_auto = classify_intent(text)
        assert intent == IntentType.HOSTILE_OPT_OUT, f"Failed for '{text}': got {intent}"


def test_required_compound_intent_matrix():
    """Verify all explicit compound intent combinations required by Phase 6.1 specification."""
    compound_matrix = [
        ("sure", IntentType.ACKNOWLEDGEMENT),
        ("sure, let's do it", IntentType.ACTIONABLE_INTENT),
        ("yes", IntentType.ACKNOWLEDGEMENT),
        ("yes, let's proceed", IntentType.ACTIONABLE_INTENT),
        ("okay, but stop messaging me", IntentType.HOSTILE_OPT_OUT),
        ("sure, but don't contact me again", IntentType.HOSTILE_OPT_OUT),
        ("stop, let's do it", IntentType.HOSTILE_OPT_OUT),
    ]

    for text, expected_intent in compound_matrix:
        actual_intent, _ = classify_intent(text)
        assert actual_intent == expected_intent, (
            f"Compound test failed for '{text}': expected {expected_intent.value}, got {actual_intent.value}"
        )


def test_whole_utterance_hostile_absolute_precedence():
    """Verify that hostile keywords anywhere in utterance override positive words."""
    adversarial_hostile = [
        "Yes please, but stop messaging me.",
        "Proceed, actually nevermind unsubscribe.",
        "Let's do it. Stop sending spam.",
        "Sure, but do not contact me ever again.",
    ]
    for text in adversarial_hostile:
        intent, _ = classify_intent(text)
        assert intent == IntentType.HOSTILE_OPT_OUT, f"Hostile precedence failed for '{text}': got {intent}"
