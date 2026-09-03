# Phase 6 Forensic Reconnaissance & Architecture Proposal

## 1. Existing Conversation State Inspection

In the current implementation (`app/api/service.py`):
- Conversation history is stored in an in-memory dictionary on `EngineService`:
  ```python
  self._conversations: Dict[str, List[Dict[str, Any]]] = {}
  ```
- In `/v1/tick`, outbound actions append an initial record:
  ```python
  self._conversations.setdefault(msg.conversation_id, []).append({
      "from": msg.send_as,
      "body": msg.body,
      "trigger_id": msg.trigger_id,
  })
  ```
- In `/v1/reply`, incoming turns append turn metadata:
  ```python
  self._conversations[conversation_id].append({
      "turn_number": turn_number,
      "from_role": from_role,
      "message": message,
      "received_at": received_at,
      "is_auto": is_auto,
  })
  ```
- **Finding**: There is currently **no explicit, strongly-typed conversation state machine** (`WAITING`, `ACTION`, `ENDED`). Conversation state is ephemeral and inferred per request rather than tracked as an audited state transition.

---

## 2. Existing Reply Protocol

- The API contract is defined in `app/api/schemas.py`:
  - **Request**: `ReplyRequest(conversation_id, merchant_id, customer_id, from_role, message, received_at, turn_number)`
  - **Response**: `ReplyResponse(action, wait_seconds, body, cta, rationale)`
- Actions supported by response: `"send"`, `"wait"`, `"end"`.
- Synchronous HTTP endpoint: `POST /v1/reply`.

---

## 3. Existing Role Handling

- `ReplyRequest.from_role` accepts `"merchant"` or `"customer"`.
- Currently, `app/api/service.py` records `from_role` in turn history, but evaluates intent identically regardless of role.
- Customer-scoped opt-out (`"STOP"`) must ensure customer-specific consent revocation while merchant-scoped opt-out closes merchant-level engagement.

---

## 4. Existing Auto-Reply Detection

- Patterns detected:
  ```python
  auto_reply_patterns = [
      "thank you for contacting",
      "team will respond shortly",
      "automated message",
      "auto-reply",
      "our team will respond",
      "away from the phone",
  ]
  ```
- **Consecutive Tail Tracking**: `service.py` iterates backwards over `_conversations[conversation_id]` to count consecutive auto-replies at the current tail.
- **Thresholds**:
  - Consecutive auto-replies $\ge 3 \implies `action = "end"`
  - Consecutive auto-replies $< 3 \implies `action = "wait"`, `wait_seconds = 14400` (4 hours)
- **Judge Simulator Compatibility**: The official judge sends 4 turns of auto-replies across changing IDs (`conv_auto_1` to `conv_auto_4`). The current logic returns `wait` with `wait_seconds=14400` on turn 1, satisfying the judge simulator's `_auto_reply` test.

---

## 5. Existing Hostile / Opt-Out Handling

- Patterns detected:
  ```python
  optout_patterns = [
      "stop messaging", "not interested", "useless spam",
      "unsubscribe", "stop", "don't message", "dont message", "do not contact"
  ]
  ```
- Returns `action = "end"` immediately with clear rationale.
- Satisfies official judge scenario: `"Stop messaging me. This is useless spam."` $\implies `action = "end"`.

---

## 6. Existing WAIT → ACTION Behavior

- Currently triggers on `commitment_patterns`:
  ```python
  commitment_patterns = [
      "lets do it", "let's do it", "whats next", "what's next",
      "yes", "ok", "proceed", "send", "draft", "share", "go ahead"
  ]
  ```
- Responds with actioning words: `"Drafting now — sending you the complete preview shortly. Here is the next step ready to confirm and launch. Confirm when ready to proceed!"`, avoiding qualifying questions (`would you`, `do you`, etc.).
- **Defect**: Treating `"ok"` and `"yes"` as commitment triggers action mode even when the user is merely acknowledging. Phase 6 must separate `ACKNOWLEDGEMENT` from `ACTIONABLE_INTENT`.

---

## 7. Existing ACTION → END Behavior

- Occurs when an active conversation encounters hostile opt-out or 3 consecutive auto-replies.
- No other terminal states are currently enforced.

---

## 8. Preserved Behaviors

1. `POST /v1/reply` request and response JSON schema compatibility.
2. Consecutive auto-reply tail counting (not counting historic auto-replies separated by real conversation).
3. Backoff timing: `wait_seconds = 14400` (4h) on auto-reply.
4. Terminal transition to `end` on hostile opt-out (`"Stop messaging me. This is useless spam."`).
5. Actioning-language guarantees on actionable commitment (must contain action words, zero qualifying questions).
6. Polite redirect on CA/tax/GST inquiries.
7. Safe fallback to `wait` on empty/whitespace messages.
8. Clean isolation between conversation IDs.

---

## 9. Missing Capabilities (To Be Added in Phase 6)

1. **Dedicated Conversation Domain Models (`app/conversation/`)**:
   - Strongly typed `ConversationState` enum: `WAITING`, `ACTION`, `ENDED`.
   - Strongly typed `IntentType` enum: `HOSTILE_OPT_OUT`, `ACTIONABLE_INTENT`, `ACKNOWLEDGEMENT`, `CLARIFICATION`, `NEUTRAL`.
   - Explicit `ConversationEntity` model tracking state, turn count, last intent, and consecutive auto-reply count.
2. **Intent Precedence & Separation**:
   - `HOSTILE_OPT_OUT` strictly overrides weaker intents (e.g., `"Okay, but stop messaging me"` $\to$ `HOSTILE_OPT_OUT`).
   - `ACKNOWLEDGEMENT` (`"okay"`, `"thanks"`, `"got it"`, `"sure"`, `"understood"`) maintains `WAITING` state and does not resend action drafts or cause loop spam.
   - `ACTIONABLE_INTENT` (`"let's do it"`, `"what's next?"`, `"how do I start?"`, `"proceed with draft"`) triggers transition to `ACTION`.
3. **Thread-Safe State Machine (`ConversationStore`)**:
   - Thread-safe tracking of active conversation entities.
   - Explicit valid state transitions:
     - `WAITING` + `ACKNOWLEDGEMENT` $\to$ `WAITING` (bounded restraint)
     - `WAITING` + `ACTIONABLE_INTENT` $\to$ `ACTION`
     - `WAITING` / `ACTION` + `HOSTILE_OPT_OUT` $\to$ `ENDED`
     - `ENDED` + Any $\to$ `ENDED` (terminal fail-closed)
4. **Adversarial Input Handling**:
   - Normalization for punctuation, mixed-case, whitespace, and compound clauses.

---

## 10. Boundary Compliance Audit

- **Phase 1 Context**: Read-only. Phase 6 does not mutate raw category, merchant, or customer seed models.
- **Phase 2 Decision Engine**: Phase 6 does not create new `ActionType` values, does not re-score candidates, and does not alter Phase 2 decision authority.
- **Phase 3 Message Composer**: Composed messages for outbound continuation remain grounded and deterministic.
- **Phase 5 Outreach Governance**: Inbound replies do not bypass exact deduplication or consent rules for proactive outreach.
- **No LLM / No Network**: All classification and state transitions are 100% deterministic pattern rules.

---

## 11. Proposed Architecture & Module Structure

```text
app/conversation/
├── __init__.py           # Public exports
├── models.py             # ConversationState, IntentType, ConversationEntity, TransitionRecord
├── classifier.py         # Deterministic intent classifier with strict precedence
├── state_machine.py      # State machine transition engine
└── store.py              # Thread-safe ConversationStore managing conversation lifecycles
```

---

## 12. Proposed Test Suite

1. `tests/test_conversation_intent.py`:
   - Verification of all intent classes (`ACKNOWLEDGEMENT`, `ACTIONABLE_INTENT`, `HOSTILE_OPT_OUT`, `CLARIFICATION`, `NEUTRAL`).
   - Priority resolution (compound hostile messages like `"Okay, but stop messaging me"`).
2. `tests/test_conversation_state_machine.py`:
   - Valid state transitions (`WAITING` $\to$ `ACTION`, `WAITING` $\to$ `ENDED`, `ACTION` $\to$ `ENDED`).
   - Restraint on acknowledgement loops (`WAITING` $\to$ `WAITING`).
   - Terminality of `ENDED`.
3. `tests/test_conversation_isolation.py`:
   - Tenant and conversation ID isolation.
4. `tests/test_conversation_adversarial.py`:
   - Mixed-case, punctuation, whitespace, very long inputs, repeated messages.
5. Official Judge Simulator and full regression verification.
