"""Deterministic validators enforcing grounding, safety, URL policy, and formatting constraints."""

import re
from typing import List, Optional, Tuple

from app.composer.message import ComposedMessage
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.actions import ActionType
from app.engine.decision import Decision

# URL detection pattern
URL_PATTERN = re.compile(
    r'(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.(com|in|org|net|co|io|ai|app)/[^\s]*)',
    re.IGNORECASE
)

# Internal database ID pattern (m_001..., c_001..., trg_001...)
INTERNAL_ID_PATTERN = re.compile(
    r'\b(m_\d{3}_[a-zA-Z0-9_]+|c_\d{3}_[a-zA-Z0-9_]+|trg_\d{3}_[a-zA-Z0-9_]+)\b',
    re.IGNORECASE
)

# Recognized CTA types
VALID_CTA_TYPES = {
    "binary_yes_no",
    "multi_choice_slot",
    "binary_confirm",
    "open_ended",
    "none",
}


def validate_no_urls(body: str) -> Tuple[bool, Optional[str]]:
    """Reject raw URLs in message bodies (Meta / WhatsApp business policy)."""
    if not body:
        return True, None
    matches = URL_PATTERN.findall(body)
    if matches:
        return False, f"URL_PROHIBITED: Raw URLs detected in message body: {matches}"
    return True, None


def validate_no_taboos(body: str, taboos: List[str]) -> Tuple[bool, Optional[str]]:
    """Reject vertical-specific taboo terms (e.g. 'guaranteed', '100% safe', 'cure')."""
    if not body or not taboos:
        return True, None
    body_lower = body.lower()
    for taboo in taboos:
        if taboo.lower() in body_lower:
            return False, f"TABOO_PROHIBITED: Taboo phrase '{taboo}' found in message body."
    return True, None


def validate_cta(body: str, cta: str, action: str) -> Tuple[bool, Optional[str]]:
    """Ensure a single, recognized primary CTA exists where required."""
    if action in ("wait", "end"):
        if cta != "none":
            return False, f"CTA_INVALID: Non-actionable action '{action}' must have cta='none'."
        return True, None

    if cta not in VALID_CTA_TYPES:
        return False, f"CTA_UNKNOWN: Unrecognized CTA type '{cta}'."

    # Verify message does not ask multiple competing questions
    question_marks = body.count("?")
    if question_marks > 2:
        return False, f"MULTIPLE_CTAS: Message contains {question_marks} questions; exactly one primary ask expected."

    return True, None


def validate_customer_privacy(body: str, customer_id: Optional[str], merchant_id: str) -> Tuple[bool, Optional[str]]:
    """Ensure internal database IDs and keys never leak into recipient-facing messages."""
    if not body:
        return True, None

    # Check for raw internal IDs
    matches = INTERNAL_ID_PATTERN.findall(body)
    if matches:
        return False, f"PRIVACY_LEAK: Internal identifier leaked in message: {matches}"

    if customer_id and customer_id in body:
        return False, f"PRIVACY_LEAK: Raw customer_id '{customer_id}' found in message text."

    if merchant_id in body:
        return False, f"PRIVACY_LEAK: Raw merchant_id '{merchant_id}' found in message text."

    return True, None


def validate_target_scope(send_as: str, target_scope: str) -> Tuple[bool, Optional[str]]:
    """Ensure sender persona strictly matches recipient target scope."""
    if target_scope == "customer" and send_as != "merchant_on_behalf":
        return False, f"TARGET_SCOPE_MISMATCH: Customer-scoped message must have send_as='merchant_on_behalf'."
    if target_scope == "merchant" and send_as != "vera":
        return False, f"TARGET_SCOPE_MISMATCH: Merchant-scoped message must have send_as='vera'."
    return True, None


def validate_offer_claims(action_type: ActionType, supporting_offer: Optional[dict]) -> Tuple[bool, Optional[str]]:
    """Verify that actions requiring an offer have a verified, active supporting offer."""
    if action_type == ActionType.PROMOTE_DELIVERY_OFFER:
        if not supporting_offer:
            return False, "UNSUPPORTED_OFFER_CLAIM: PROMOTE_DELIVERY_OFFER requires supporting_offer."
        if supporting_offer.get("status") != "active":
            return False, f"EXPIRED_OFFER_CLAIM: Offer status is '{supporting_offer.get('status')}', expected 'active'."
    return True, None


def validate_message_structure(composed: ComposedMessage) -> Tuple[bool, Optional[str]]:
    """Validate structural constraints (length, non-empty fields)."""
    if composed.action in ("wait", "end"):
        if composed.body != "":
            return False, f"STRUCTURE_INVALID: Action '{composed.action}' must have an empty body."
        return True, None

    if composed.action == "send":
        if not composed.body or len(composed.body.strip()) == 0:
            return False, "STRUCTURE_INVALID: Send action has empty message body."
        if len(composed.body) > 1000:
            return False, f"MESSAGE_TOO_LONG: Message length {len(composed.body)} exceeds 1000 chars."

    if not composed.suppression_key:
        return False, "STRUCTURE_INVALID: Missing suppression key."

    if not composed.rationale:
        return False, "STRUCTURE_INVALID: Missing rationale."

    return True, None


def validate_composed_message(
    composed: ComposedMessage,
    decision: Decision,
    category: CategoryProfile,
    merchant: MerchantState,
    trigger: TriggerState,
    customer: Optional[CustomerStateModel] = None,
) -> Tuple[bool, List[str]]:
    """Run all validation checks and aggregate errors."""
    errors: List[str] = []

    # 1. Structure
    ok, err = validate_message_structure(composed)
    if not ok and err:
        errors.append(err)

    # 2. URLs
    ok, err = validate_no_urls(composed.body)
    if not ok and err:
        errors.append(err)

    # 3. Taboo phrases
    taboos = category.voice.vocab_taboo if category and category.voice else []
    ok, err = validate_no_taboos(composed.body, taboos)
    if not ok and err:
        errors.append(err)

    # 4. CTA
    ok, err = validate_cta(composed.body, composed.cta, composed.action)
    if not ok and err:
        errors.append(err)

    # 5. Customer Privacy
    cid = customer.customer_id if customer else None
    ok, err = validate_customer_privacy(composed.body, cid, merchant.merchant_id)
    if not ok and err:
        errors.append(err)

    # 6. Target Scope & Persona
    ok, err = validate_target_scope(composed.send_as, composed.target_scope)
    if not ok and err:
        errors.append(err)

    # 7. Offer Claims
    ok, err = validate_offer_claims(composed.action_type, decision.supporting_offer)
    if not ok and err:
        errors.append(err)

    return len(errors) == 0, errors
