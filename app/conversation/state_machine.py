"""Deterministic Conversation State Machine and Transition Engine."""

from __future__ import annotations

from typing import Optional
from app.conversation.classifier import classify_intent
from app.conversation.models import (
    ConversationEntity,
    ConversationState,
    ConversationTurn,
    IntentType,
    TransitionResult,
)


def process_turn(
    entity: ConversationEntity,
    message: str,
    from_role: str,
    received_at: str,
    turn_number: int,
) -> TransitionResult:
    """Evaluate an incoming message against the conversation entity and return a deterministic transition."""
    # 1. Terminal State Check
    if entity.state == ConversationState.ENDED:
        turn = ConversationTurn(
            turn_number=turn_number,
            from_role=from_role,
            message=message,
            received_at=received_at,
            is_auto=False,
            intent=IntentType.NEUTRAL,
            action_taken="end",
        )
        entity.turns.append(turn)
        entity.turn_count += 1
        entity.last_updated_at = received_at
        return TransitionResult(
            previous_state=ConversationState.ENDED,
            new_state=ConversationState.ENDED,
            intent=IntentType.NEUTRAL,
            action="end",
            rationale="Conversation is permanently closed. Stand down fail-closed.",
        )

    # 2. Empty / Whitespace Message Handling
    if not message or not message.strip():
        turn = ConversationTurn(
            turn_number=turn_number,
            from_role=from_role,
            message=message,
            received_at=received_at,
            is_auto=False,
            intent=IntentType.NEUTRAL,
            action_taken="wait",
        )
        entity.turns.append(turn)
        entity.turn_count += 1
        entity.last_updated_at = received_at
        return TransitionResult(
            previous_state=entity.state,
            new_state=entity.state,
            intent=IntentType.NEUTRAL,
            action="wait",
            wait_seconds=300,
            rationale="Empty message received. Standing by for message content.",
        )

    # 3. Intent Classification
    intent, is_auto = classify_intent(message)

    # 4. Auto-Reply Handling
    if is_auto:
        entity.consecutive_auto_replies += 1
        turn = ConversationTurn(
            turn_number=turn_number,
            from_role=from_role,
            message=message,
            received_at=received_at,
            is_auto=True,
            intent=intent,
            action_taken="end" if entity.consecutive_auto_replies >= 3 else "wait",
        )
        entity.turns.append(turn)
        entity.turn_count += 1
        entity.last_updated_at = received_at

        if entity.consecutive_auto_replies >= 3:
            prev_state = entity.state
            entity.state = ConversationState.ENDED
            entity.last_action = "end"
            entity.last_intent = intent
            return TransitionResult(
                previous_state=prev_state,
                new_state=ConversationState.ENDED,
                intent=intent,
                action="end",
                rationale="Persistent merchant auto-reply detected (3 consecutive auto-replies). Gracefully closing conversation.",
            )

        entity.last_action = "wait"
        entity.last_intent = intent
        return TransitionResult(
            previous_state=entity.state,
            new_state=entity.state,
            intent=intent,
            action="wait",
            wait_seconds=14400,
            rationale="Detected merchant auto-reply (canned response). Backing off 4 hours to wait for owner.",
        )

    # Genuine human message: reset the consecutive auto-reply tail counter!
    entity.consecutive_auto_replies = 0

    # 5. Hostile / Opt-Out Handling (Terminal)
    if intent == IntentType.HOSTILE_OPT_OUT:
        prev_state = entity.state
        entity.state = ConversationState.ENDED
        entity.last_action = "end"
        entity.last_intent = intent
        turn = ConversationTurn(
            turn_number=turn_number,
            from_role=from_role,
            message=message,
            received_at=received_at,
            is_auto=False,
            intent=intent,
            action_taken="end",
        )
        entity.turns.append(turn)
        entity.turn_count += 1
        entity.last_updated_at = received_at
        return TransitionResult(
            previous_state=prev_state,
            new_state=ConversationState.ENDED,
            intent=intent,
            action="end",
            rationale="Merchant explicitly opted out. Closing conversation and suppressing conversation_id.",
        )

    # 6. Actionable Intent (WAITING -> ACTION)
    if intent == IntentType.ACTIONABLE_INTENT:
        prev_state = entity.state
        entity.state = ConversationState.ACTION
        entity.last_action = "send"
        entity.last_intent = intent
        turn = ConversationTurn(
            turn_number=turn_number,
            from_role=from_role,
            message=message,
            received_at=received_at,
            is_auto=False,
            intent=intent,
            action_taken="send",
        )
        entity.turns.append(turn)
        entity.turn_count += 1
        entity.last_updated_at = received_at
        return TransitionResult(
            previous_state=prev_state,
            new_state=ConversationState.ACTION,
            intent=intent,
            action="send",
            body=(
                "Drafting now — sending you the complete preview shortly. "
                "Here is the next step ready to confirm and launch. Confirm when ready to proceed!"
            ),
            cta="binary_confirm",
            rationale="Switched to action mode upon merchant commitment. Honoring request directly.",
        )

    # 7. Clarification / Out-of-Scope (e.g. GST, taxes, loans)
    if intent == IntentType.CLARIFICATION:
        turn = ConversationTurn(
            turn_number=turn_number,
            from_role=from_role,
            message=message,
            received_at=received_at,
            is_auto=False,
            intent=intent,
            action_taken="send",
        )
        entity.turns.append(turn)
        entity.turn_count += 1
        entity.last_action = "send"
        entity.last_intent = intent
        entity.last_updated_at = received_at
        return TransitionResult(
            previous_state=entity.state,
            new_state=entity.state,
            intent=intent,
            action="send",
            body=(
                "I will have to leave tax and accounting to your CA — that is outside what I directly handle. "
                "Coming back to our priority — sending the draft preview now. Ready to confirm?"
            ),
            cta="binary_yes_no",
            rationale="Out-of-scope ask politely declined; redirected back to the core trigger without losing thread.",
        )

    # 8. Acknowledgement Handling (Prevent Acknowledgement Loop!)
    if intent == IntentType.ACKNOWLEDGEMENT:
        turn = ConversationTurn(
            turn_number=turn_number,
            from_role=from_role,
            message=message,
            received_at=received_at,
            is_auto=False,
            intent=intent,
            action_taken="wait" if entity.state == ConversationState.WAITING else "send",
        )
        entity.turns.append(turn)
        entity.turn_count += 1
        entity.last_intent = intent
        entity.last_updated_at = received_at

        # If in WAITING: prevent acknowledgement loop by not re-pitching or sending proactive spam
        if entity.state == ConversationState.WAITING:
            entity.last_action = "wait"
            return TransitionResult(
                previous_state=entity.state,
                new_state=entity.state,
                intent=intent,
                action="wait",
                wait_seconds=86400,
                rationale="Acknowledged merchant receipt. Standing by for merchant instructions without repetitive outreach.",
            )

        # If already in ACTION: confirm receipt and wait for confirmation
        entity.last_action = "send"
        return TransitionResult(
            previous_state=entity.state,
            new_state=entity.state,
            intent=intent,
            action="send",
            body="Got it! Sending the finalized preview over right away. Confirm when ready.",
            cta="binary_confirm",
            rationale="Acknowledged actionable confirmation.",
        )

    # 9. General Neutral Active Response
    turn = ConversationTurn(
        turn_number=turn_number,
        from_role=from_role,
        message=message,
        received_at=received_at,
        is_auto=False,
        intent=intent,
        action_taken="send",
    )
    entity.turns.append(turn)
    entity.turn_count += 1
    entity.last_action = "send"
    entity.last_intent = intent
    entity.last_updated_at = received_at
    return TransitionResult(
        previous_state=entity.state,
        new_state=entity.state,
        intent=intent,
        action="send",
        body="Got it! Sending the updated details over right away. Here is the draft ready to confirm.",
        cta="binary_confirm",
        rationale="Acknowledged message and advanced actionable conversation.",
    )
