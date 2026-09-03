"""Deterministic intent classification with strict whole-utterance precedence ordering."""

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
    re.compile(r"\bstop contacting\b", re.IGNORECASE),
    re.compile(r"\b(don'?t|do not|never)\s+(contact|message)\b", re.IGNORECASE),
    re.compile(r"\bno\s+more\s+(messages?|messaging)\b", re.IGNORECASE),
    re.compile(r"\bunsubscribe\b", re.IGNORECASE),
    re.compile(r"\bremove\s+me\b", re.IGNORECASE),
    re.compile(r"\btake\s+me\s+off(\s+your\s+list)?\b", re.IGNORECASE),
    re.compile(r"\b(this\s+is\s+)?(useless\s+)?spam\b", re.IGNORECASE),
    re.compile(r"\bnot\s+interested\b", re.IGNORECASE),
    re.compile(r"\bleave\s+me\s+alone\b", re.IGNORECASE),
    re.compile(r"\bopt[- ]?out\b", re.IGNORECASE),
    re.compile(r"\bstop\b", re.IGNORECASE),
]

ACTIONABLE_PATTERNS = [
    re.compile(r"\blet'?s\s+(do\s+it|proceed|move\s+forward|get\s+started)\b", re.IGNORECASE),
    re.compile(r"\blets\s+(do\s+it|proceed|move\s+forward|get\s+started)\b", re.IGNORECASE),
    re.compile(r"\bmove\s+forward\b", re.IGNORECASE),
    re.compile(r"\bgo\s+ahead\b", re.IGNORECASE),
    re.compile(r"\b(do\s+it|proceed|proceed\s+with\s+this|ready\s+to\s+proceed)\b", re.IGNORECASE),
    re.compile(r"\b(i\s+)?(want|would\s+like)\s+to\s+(do\s+this|proceed|start)\b", re.IGNORECASE),
    re.compile(r"\bhow\s+(do|should|can)\s+(i|we)\s+(start|proceed|begin)\b", re.IGNORECASE),
    re.compile(r"\bwhat'?s\s+next\b", re.IGNORECASE),
    re.compile(r"\bwhats\s+next\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+should\s+(i|we)\s+do\s+next\b", re.IGNORECASE),
    re.compile(r"\b(yes|sure|okay|ok)[, ]+(let'?s|please|do\s+it|proceed|go\s+ahead|start|move\s+forward)\b", re.IGNORECASE),
    re.compile(r"\bsend\s+(the\s+)?(draft|preview|details)\b", re.IGNORECASE),
    re.compile(r"\bshare\s+(the\s+)?(draft|preview|details)\b", re.IGNORECASE),
    re.compile(r"\bsign\s+me\s+up\b", re.IGNORECASE),
    re.compile(r"\bcan\s+we\s+do\s+this\b", re.IGNORECASE),
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
    return text.strip()


def is_auto_reply(text: str) -> bool:
    """Detect canned auto-responder messages."""
    return any(p.search(text) for p in AUTO_REPLY_PATTERNS)


def classify_intent(text: str) -> Tuple[IntentType, bool]:
    """Deterministically classify intent with strict whole-utterance priority ordering.
    
    Priority Order:
    1. Empty / Whitespace -> NEUTRAL
    2. Auto-reply detection -> checked independently, flagged
    3. HOSTILE_OPT_OUT (Strictly overrides all other intents across whole utterance)
    4. ACTIONABLE_INTENT (Overrides passive acknowledgement if actioning verbs are present)
    5. ACKNOWLEDGEMENT (Pure passive receipt, prevents acknowledgement loop)
    6. NEUTRAL (General default)
    
    Returns:
        (IntentType, is_auto_flag)
    """
    cleaned = normalize_text(text)
    if not cleaned:
        return IntentType.NEUTRAL, False

    auto_flag = is_auto_reply(cleaned)

    # 1. Hostile / Opt-Out has absolute precedence across whole utterance
    # e.g., "stop, let's do it", "okay, but stop messaging me", "sure, but don't contact me again"
    for pattern in HOSTILE_PATTERNS:
        if pattern.search(cleaned):
            return IntentType.HOSTILE_OPT_OUT, auto_flag

    # 2. Actionable intent (e.g. "sure, let's do it", "yes, let's proceed", "what's next?")
    for pattern in ACTIONABLE_PATTERNS:
        if pattern.search(cleaned):
            return IntentType.ACTIONABLE_INTENT, auto_flag

    # 3. Pure acknowledgement detection
    # Text matches acknowledgement words/phrases without actionable verbs
    text_alpha_only = re.sub(r"[^\w\s]", "", cleaned).lower().strip()
    words = text_alpha_only.split()
    if text_alpha_only in ACKNOWLEDGEMENT_WORDS:
        return IntentType.ACKNOWLEDGEMENT, auto_flag
    if len(words) <= 3 and all(w in ACKNOWLEDGEMENT_WORDS for w in words):
        return IntentType.ACKNOWLEDGEMENT, auto_flag

    return IntentType.NEUTRAL, auto_flag
