"""Deterministic intent classification with strict precedence ordering."""

from __future__ import annotations

import re
from typing import Tuple
from app.conversation.models import IntentType

# Compiled regex patterns for robust matching
AUTO_REPLY_PATTERNS = [
    re.compile(r"\bthank you for contacting\b", re.IGNORECASE),
    re.compile(r"\bteam will respond shortly\b", re.IGNORECASE),
    re.compile(r"\bautomated message\b", re.IGNORECASE),
    re.compile(r"\bauto[- ]reply\b", re.IGNORECASE),
    re.compile(r"\bour team will respond\b", re.IGNORECASE),
    re.compile(r"\baway from the phone\b", re.IGNORECASE),
]

HOSTILE_PATTERNS = [
    re.compile(r"\bstop messaging\b", re.IGNORECASE),
    re.compile(r"\buseless spam\b", re.IGNORECASE),
    re.compile(r"\bnot interested\b", re.IGNORECASE),
    re.compile(r"\bunsubscribe\b", re.IGNORECASE),
    re.compile(r"\bdo not contact\b", re.IGNORECASE),
    re.compile(r"\bdon'?t contact\b", re.IGNORECASE),
    re.compile(r"\bdo not message\b", re.IGNORECASE),
    re.compile(r"\bdon'?t message\b", re.IGNORECASE),
    re.compile(r"\bleave me alone\b", re.IGNORECASE),
    re.compile(r"\bremove me\b", re.IGNORECASE),
    re.compile(r"\bthis is spam\b", re.IGNORECASE),
    re.compile(r"\bopt[- ]?out\b", re.IGNORECASE),
    re.compile(r"^\s*stop\s*$", re.IGNORECASE),
    re.compile(r"\bstop\b.*?\b(spam|messaging|calling|contacting)\b", re.IGNORECASE),
]

ACTIONABLE_PATTERNS = [
    re.compile(r"\blet'?s do it\b", re.IGNORECASE),
    re.compile(r"\bwhat'?s next\b", re.IGNORECASE),
    re.compile(r"\bhow do i start\b", re.IGNORECASE),
    re.compile(r"\bhow to start\b", re.IGNORECASE),
    re.compile(r"\bproceed\b", re.IGNORECASE),
    re.compile(r"\bgo ahead\b", re.IGNORECASE),
    re.compile(r"\bdo it\b", re.IGNORECASE),
    re.compile(r"\bsend (the )?(draft|preview|details)\b", re.IGNORECASE),
    re.compile(r"\bshare (the )?(draft|preview|details)\b", re.IGNORECASE),
    re.compile(r"\bcan we do this\b", re.IGNORECASE),
    re.compile(r"\bsign me up\b", re.IGNORECASE),
    re.compile(r"\byes[, ]+(let'?s|please|do it|proceed)\b", re.IGNORECASE),
]

CLARIFICATION_PATTERNS = [
    re.compile(r"\bgst\b", re.IGNORECASE),
    re.compile(r"\btax(es)?\b", re.IGNORECASE),
    re.compile(r"\bfiling\b", re.IGNORECASE),
    re.compile(r"\baccounting\b", re.IGNORECASE),
    re.compile(r"\bloan(s)?\b", re.IGNORECASE),
    re.compile(r"\blegal advice\b", re.IGNORECASE),
]

ACKNOWLEDGEMENT_WORDS = {
    "ok",
    "okay",
    "thanks",
    "thank you",
    "got it",
    "sure",
    "understood",
    "interesting",
    "great",
    "fine",
    "noted",
    "cool",
    "received",
    "yes",
    "yep",
    "thumbs up",
}


def normalize_text(text: str) -> str:
    """Strip whitespace and normalize casing and punctuation."""
    cleaned = text.strip()
    return cleaned


def is_auto_reply(text: str) -> bool:
    """Detect canned auto-responder messages."""
    return any(p.search(text) for p in AUTO_REPLY_PATTERNS)


def classify_intent(text: str) -> Tuple[IntentType, bool]:
    """Deterministically classify intent with strict priority ordering.
    
    Priority Order:
    1. Empty / Whitespace -> NEUTRAL
    2. Auto-reply detection -> checked independently, flagged
    3. HOSTILE_OPT_OUT (Strictly overrides all other intents)
    4. ACTIONABLE_INTENT
    5. CLARIFICATION (Domain boundary / redirect)
    6. ACKNOWLEDGEMENT (Passive receipt, prevents acknowledgement loop)
    7. NEUTRAL
    
    Returns:
        (IntentType, is_auto_flag)
    """
    cleaned = normalize_text(text)
    if not cleaned:
        return IntentType.NEUTRAL, False

    auto_flag = is_auto_reply(cleaned)

    # 1. Hostile / Opt-out has absolute highest priority over words in compound sentences
    # e.g., "Okay, but stop messaging me" -> HOSTILE_OPT_OUT
    for pattern in HOSTILE_PATTERNS:
        if pattern.search(cleaned):
            return IntentType.HOSTILE_OPT_OUT, auto_flag

    # 2. Actionable intent (e.g. "Ok lets do it. Whats next?")
    for pattern in ACTIONABLE_PATTERNS:
        if pattern.search(cleaned):
            return IntentType.ACTIONABLE_INTENT, auto_flag

    # 3. Clarification / Out-of-scope redirection
    for pattern in CLARIFICATION_PATTERNS:
        if pattern.search(cleaned):
            return IntentType.CLARIFICATION, auto_flag

    # 4. Pure acknowledgement detection
    # If the text (stripped of punctuation) matches acknowledgement vocabulary
    text_alpha_only = re.sub(r"[^\w\s]", "", cleaned).lower().strip()
    words = text_alpha_only.split()
    if text_alpha_only in ACKNOWLEDGEMENT_WORDS:
        return IntentType.ACKNOWLEDGEMENT, auto_flag
    if len(words) <= 3 and all(w in ACKNOWLEDGEMENT_WORDS for w in words):
        return IntentType.ACKNOWLEDGEMENT, auto_flag

    return IntentType.NEUTRAL, auto_flag
