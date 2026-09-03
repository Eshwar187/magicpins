# Phase 6 — Deterministic Conversation & Reply Intelligence Policy (Phase 6.1 Corrected)

## 1. Executive Summary & Core Architectural Invariants

Phase 2 answers: **WHAT should Vera do?**  
Phase 3 answers: **HOW should Vera express it?**  
Phase 5 answers: **CAN THIS EXACT OUTREACH BE TRANSMITTED RIGHT NOW?**  
Phase 6 answers: **HOW SHOULD VERA INTERPRET INBOUND REPLIES AND TRANSITION CONVERSATIONAL STATE SAFELY?**

```text
Inbound Merchant / Customer Reply (/v1/reply)
                   ↓
Phase 6: Deterministic Intent Classification (Whole-Utterance Priority Order)
                   ↓
Phase 6: Conversation State Machine (WAITING / ACTION / ENDED)
                   ↓
Route Decision (CONTINUE_EXISTING_ACTION / STAND_DOWN / TERMINAL_EXIT)
                   ↓
If CONTINUE_EXISTING_ACTION: Phase 3 Grounded Composition (compose_action_continuation)
                   ↓
Phase 4 Synchronous API Response
```

### Critical Authority Boundaries:
> **Phase 6 interprets conversational intent, enforces safety restraint, and controls state transitions. It does NOT independently compose business message prose, select business actions, score candidates, or alter Phase 2 decision authority.**

> **Phase 6 owns message composition: NO**  
> **Phase 3 remains authoritative: YES**  
> **Phase 2 remains authoritative: YES**  
> **Phase 5 remains authoritative: YES**

---

## 2. Auto-Reply Semantics & Resolution of Blocker 1

### Authoritative Evidence & Semantics:
- **`examples/api-call-examples.md` Example 2.5**:
  ```json
  {
    "action": "wait",
    "wait_seconds": 14400,
    "rationale": "Detected merchant auto-reply (canned 'Thank you for contacting' phrasing). Backing off 4 hours to wait for owner."
  }
  ```
- **`judge_simulator.py` lines 692–714**:
  ```python
  for i in range(1, 5):
      data, err, _ = self.client.reply(f"conv_auto_{i}", mid, auto_msg, i + 1)
      if action == "end":
          print_success("Bot ENDED — detected auto-reply pattern!")
          return True
      elif action == "wait":
          print_success(f"Turn {i}: Bot WAITING {wait_s}s")
  print_warn("Bot never ended after 4 auto-replies")
  return True
  ```
- **Explanation of the Behavior**:
  1. The judge simulator passes a new conversation ID on each turn (`f"conv_auto_{i}"`).
  2. For each conversation, encountering a canned auto-reply triggers a graceful 4-hour backoff (`action = "wait"`, `wait_seconds = 14400`), resulting in `[PASS] Turn {i}: Bot WAITING 14400s`.
  3. The judge simulator prints a warning if `action != "end"` after 4 distinct conversation turns, but explicitly returns `True` (`Auto-reply status: PASS`).
  4. Within a single persistent conversation session, receiving 3 consecutive auto-replies without genuine human interaction triggers `action = "end"` with route `TERMINAL_EXIT`.

Both outcomes are consistent with the authoritative challenge contract: **Never burn proactive messaging turns on automated responders.**

---

## 3. Resolution of Blocker 2: Phase 6 Business Message Removal

Phase 6 previously contained hardcoded business prose:
`"Drafting now — sending you the complete preview shortly. Here is the next step ready to confirm and launch..."`

### The Surgical Correction:
1. **Phase 6 outputs only structured state and route**:
   ```python
   TransitionResult(
       previous_state=ConversationState.WAITING,
       new_state=ConversationState.ACTION,
       intent=IntentType.ACTIONABLE_INTENT,
       route="CONTINUE_EXISTING_ACTION",
       action="send",
       rationale="Switched to action mode upon merchant commitment. Routing to approved Phase 3 action continuation.",
   )
   ```
2. **Phase 3 owns all continuation composition**:
   - Implemented `compose_action_continuation()` in `app/composer/compose.py`.
   - Derives grounded continuation copy directly from the authoritative Phase 2 `decision` and domain facts.
   - Example for `USE_RESEARCH_INSIGHT`:
     *"Here is the draft patient-education WhatsApp note ready to confirm and share: 'Recent clinical research demonstrates the preventive efficacy of fluoride varnish protocols for mixed dentition.' Confirm to proceed with sending."*
   - Contains required actioning words (`here`, `draft`, `confirm`, `proceed`), zero qualifying questions (`would you`, `do you`).
   - Phase 6 does **not** compose prose.

---

## 4. Resolution of Blocker 3: Removal of Unsupported CLARIFICATION

- **Required by contract**: **NO**.
- General questions or out-of-scope inquiries are classified under `IntentType.NEUTRAL`.
- `CLARIFICATION` has been completely deleted from `IntentType`, `classifier.py`, `state_machine.py`, and test suites.

---

## 5. Intent Model & Whole-Utterance Priority Order

| Priority | Intent Class | Example Inputs | Resolution & Precedence Rules |
| :---: | :--- | :--- | :--- |
| **1** | **Empty / Whitespace** | `""`, `"   "` | Safe immediate fallback: `action="wait"`, `wait_seconds=300`. |
| **2** | **Auto-Reply (`is_auto`)** | *"Thank you for contacting us! Our team will respond shortly."* | Detected via regex; backs off 14400s; consecutive tail tracked. |
| **3** | **`HOSTILE_OPT_OUT`** | *"Stop messaging me"*, *"Unsubscribe"*, *"stop, let's do it"*, *"okay, but stop messaging me"* | **Absolute Whole-Utterance Precedence**: Hostile tokens anywhere in the message override all positive/actionable words. Terminal exit (`action="end"`). |
| **4** | **`ACTIONABLE_INTENT`** | *"sure, let's do it"*, *"yes, let's proceed"*, *"what's next?"*, *"proceed"*, *"send the draft"* | Whole-utterance actionable commitment. Overrides pure passive acknowledgement. Routes to `CONTINUE_EXISTING_ACTION`. |
| **5** | **`ACKNOWLEDGEMENT`** | *"sure"*, *"yes"*, *"ok"*, *"okay"*, *"thanks"*, *"got it"* | **Passive Receipt**: Differentiated from actionable intent. Prevents loop spam by standing down (`action="wait"`, `wait_seconds=86400`). |
| **6** | **`NEUTRAL`** | General unclassified messages | Default active workflow routing. |

---

## 6. Compound Intent Matrix Verification

| Input Utterance | Classified Intent | State Transition | Action & Route | Invariant Verified |
| :--- | :--- | :--- | :--- | :--- |
| `"sure"` | `ACKNOWLEDGEMENT` | `WAITING -> WAITING` | `wait` (86400s), `STAND_DOWN` | Passive receipt does not trigger action mode |
| `"sure, let's do it"` | `ACTIONABLE_INTENT` | `WAITING -> ACTION` | `send`, `CONTINUE_EXISTING_ACTION` | Actionable verb elevates acknowledgement |
| `"yes"` | `ACKNOWLEDGEMENT` | `WAITING -> WAITING` | `wait` (86400s), `STAND_DOWN` | Passive "yes" alone does not start campaigns |
| `"yes, let's proceed"` | `ACTIONABLE_INTENT` | `WAITING -> ACTION` | `send`, `CONTINUE_EXISTING_ACTION` | Explicit commitment starts campaign |
| `"okay, but stop messaging me"` | `HOSTILE_OPT_OUT` | `WAITING -> ENDED` | `end`, `TERMINAL_EXIT` | Hostile clause overrides initial "okay" |
| `"sure, but don't contact me again"` | `HOSTILE_OPT_OUT` | `WAITING -> ENDED` | `end`, `TERMINAL_EXIT` | Hostile clause overrides initial "sure" |
| `"stop, let's do it"` | `HOSTILE_OPT_OUT` | `WAITING -> ENDED` | `end`, `TERMINAL_EXIT` | "stop" has absolute precedence |

---

## 7. Architectural Boundary Invariants

```text
Phase 6 CANNOT change:
- ActionType
- Phase 2 score
- selected offer
- selected facts
- category fit
- business rationale
```

Phase 6 only answers:
1. What did the incoming message mean? (`IntentType`)
2. What state transition occurred? (`ConversationState`)
3. Should the conversation continue? (`action = send/wait/end`)
4. Which existing workflow should be resumed? (`route`)
