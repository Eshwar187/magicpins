"""Unit tests for Phase 6 deterministic intent classification and precedence."""

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


def test_intent_priority_hostile_overrides_all():
    """Verify compound hostile messages strictly resolve to HOSTILE_OPT_OUT."""
    compound_samples = [
        "Okay, but stop messaging me.",
        "Yes, but do not contact me again.",
        "Thanks, but unsubscribe me please.",
        "Let's do it, wait no, leave me alone.",
        "Got it, this is useless spam.",
    ]
    for text in compound_samples:
        intent, _ = classify_intent(text)
        assert intent == IntentType.HOSTILE_OPT_OUT, f"Expected HOSTILE_OPT_OUT for '{text}', got {intent}"


def test_intent_clarification():
    """Verify tax/GST questions are classified as CLARIFICATION."""
    samples = [
        "Can you help with my GST filing?",
        "What about taxes?",
        "Do you provide business loans?",
        "Need legal advice on this.",
    ]
    for text in samples:
        intent, _ = classify_intent(text)
        assert intent == IntentType.CLARIFICATION, f"Failed for '{text}': got {intent}"
