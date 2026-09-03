# Phase 5 — Outreach Governance, Suppression & Frequency Control Policy

## 1. Executive Summary & Core Contract

Phase 2 answers: **WHAT should Vera do?**  
Phase 3 answers: **HOW should Vera express it?**  
Phase 5 answers: **SHOULD Vera actually send it right now?**

Phase 5 is an **outreach governance and transmission barrier**. It sits strictly between Phase 3 message composition and Phase 4 API serialization:

```text
Phase 1
Normalized Authoritative Context (ContextStore)
              ↓
Phase 2
Deterministic Decision (WHAT)
              ↓
Phase 3
Grounded Message Composition (HOW)
              ↓
Phase 5
Outreach Governance & Policy Barrier (SEND or SUPPRESS)
              ↓
Phase 4
Challenge API Response (/v1/tick)
```

### Critical Boundary Rule
> **Phase 5 may prevent transmission (SUPPRESS), but it may NOT alter, re-score, substitute, or reinterpret the Phase 2 Decision or Phase 3 ComposedMessage.**

---

## 2. Outreach Decision Contract

Phase 5 introduces a strongly typed, deterministic decision model:

```python
class OutreachDisposition(str, Enum):
    SEND = "SEND"
    SUPPRESS = "SUPPRESS"

class SuppressionReasonCode(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    DUPLICATE_SUPPRESSED = "DUPLICATE_SUPPRESSED"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    MERCHANT_FREQUENCY_CAPPED = "MERCHANT_FREQUENCY_CAPPED"
    CUSTOMER_FREQUENCY_CAPPED = "CUSTOMER_FREQUENCY_CAPPED"
    CONSENT_RESTRICTED = "CONSENT_RESTRICTED"
    DECISION_WAIT_OR_END = "DECISION_WAIT_OR_END"
    INVALID_COMPOSITION = "INVALID_COMPOSITION"
    TENANT_MISMATCH = "TENANT_MISMATCH"

class OutreachDecision(BaseModel):
    disposition: OutreachDisposition
    reason_code: SuppressionReasonCode
    reason: str
    suppression_key: str
    target_scope: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    simulated_at: str
    previous_outreach_id: Optional[str] = None
```

---

## 3. Suppression Reason Taxonomy

Every evaluation produces a deterministic machine-readable `reason_code` and human-readable `reason`:

1. **`ELIGIBLE`**:
   - Passed all deduplication, cooldown, frequency, consent, and composition gates. Permitted to transmit.
2. **`DECISION_WAIT_OR_END`**:
   - Phase 2 decision was `WAIT` or `END`. Suppressed fail-closed to honor intentional restraint.
3. **`CONSENT_RESTRICTED`**:
   - Customer is missing consent, has opted out (`reminder_opt_in == False`), or the requested outreach type is not present in `consent.scope`.
4. **`INVALID_COMPOSITION`**:
   - The composed message failed validation (missing suppression key, empty body on SEND, or malformed CTA).
5. **`DUPLICATE_SUPPRESSED`**:
   - An outreach with the exact same tenant-scoped suppression key was previously transmitted in the current simulation epoch.
6. **`COOLDOWN_ACTIVE`**:
   - The elapsed simulation time since the previous outreach matching this suppression key or trigger family is less than the configured cooldown window.
7. **`MERCHANT_FREQUENCY_CAPPED`**:
   - The merchant has already received the maximum permitted proactive messages within the rolling simulation window (default: 1 proactive message per 24 hours, or 4 per 7 days), unless overridden by an urgency-5 emergency safety alert.
8. **`CUSTOMER_FREQUENCY_CAPPED`**:
   - The customer has already received a message within the rolling customer cooldown window (default: 1 message per 7 days).
9. **`TENANT_MISMATCH`**:
   - Missing or mismatched tenant identifiers.

---

## 4. Suppression Key Semantics & Tenant Isolation

### Suppression Key Scopes
In magicpin, suppression keys have three scopes:
1. **Merchant-scoped**: `curious_ask:{merchant_id}:{window}`, `perf_dip:{merchant_id}:{metric}:{window}`, `planning:{merchant_id}:{initiative}:{window}`.
2. **Customer-scoped**: `recall:{customer_id}:{cadence}`, `bridal_followup:{customer_id}`, `winback:{customer_id}`, `refill:{customer_id}:{month}`.
3. **Category-scoped**: `research:{category}:{cadence}`, `compliance:{vertical}:{year}`, `cde:{category}:{date}`.

### Cross-Tenant Deduplication Isolation
To prevent accidental cross-tenant suppression:
- Deduplication is tracked by composite key: `(tenant_id, suppression_key)`.
  - For merchant-targeted outreach, `tenant_id` is `merchant_id`.
  - For customer-targeted outreach, `tenant_id` is `(merchant_id, customer_id)`.
- **Guarantee**: Even if two merchants share a category-level suppression key (e.g. `research:dentists:2026-W17`), sending to Merchant A records `(m_001, research:dentists:2026-W17)`, leaving Merchant B (`m_002`) completely eligible.

---

## 5. Cooldown & Frequency Policy

### Cooldown Windows (in Simulation Seconds)
Based on challenge requirements and domain cadence:
- **Same Suppression Key Cooldown**:
  - Weekly digests / planning (`2026-Wxx`): **168 hours (7 days = 604,800s)**.
  - Monthly / refills (`2026-xx`): **720 hours (30 days = 2,592,000s)**.
  - Event / daily offers (`2026-MM-DD`): **24 hours (86,400s)**.
  - General default for exact suppression key: **168 hours (7 days)**.
- **Merchant Frequency Cap**:
  - Maximum **1 proactive message per 24 hours (86,400s)** per merchant.
  - Maximum **4 proactive messages per 7 days (604,800s)** per merchant.
  - *Emergency Exemption*: Urgency-5 safety alerts (e.g. manufacturer drug recalls) bypass non-safety frequency caps.
- **Customer Frequency Cap**:
  - Maximum **1 message per 7 days (604,800s)** per customer to prevent consumer churn and unsubscribe rates.

---

## 6. Simulation Time & Determinism

1. **Zero Wall-Clock Dependency**:
   - All time differences ($\Delta t = \text{now} - \text{previous\_sent\_at}$) are calculated using the ISO 8601 simulation timestamp passed in `body.now`.
   - Zero calls to `datetime.now()` or `time.time()`.
2. **Backwards Time Handling**:
   - If simulation time moves backwards ($\Delta t < 0$), the policy treats the prior outreach as occurring in the future and fails safe by suppressing duplicate outreach.
3. **Determinism Guarantee**:
   - Identical `(Decision, ComposedMessage, History, now)` inputs produce 100% bit-for-bit identical `OutreachDecision`.

---

## 7. Atomic Concurrency Model

- The `OutreachStore` executes the check-and-record operation atomically within a re-entrant lock (`threading.RLock`).
- **Invariant**: If Thread A and Thread B simultaneously evaluate the same suppression key for the same merchant at timestamp $T$, exactly one thread records the outreach and returns `SEND`; the second thread immediately encounters `COOLDOWN_ACTIVE` / `DUPLICATE_SUPPRESSED` and returns `SUPPRESS`.

---

## 8. Preserving WAIT and END

- If Phase 2 outputs `ActionType.WAIT`, Phase 5 returns `OutreachDisposition.SUPPRESS` with `reason_code=DECISION_WAIT_OR_END`.
- If Phase 2 outputs `ActionType.END`, Phase 5 returns `OutreachDisposition.SUPPRESS` with `reason_code=DECISION_WAIT_OR_END`.
- The internal decision remains preserved for auditing; `/v1/tick` emits `{"actions": []}`.
