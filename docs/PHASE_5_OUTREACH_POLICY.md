# Phase 5 — Outreach Governance & Exact Deduplication Policy

## 1. Executive Summary & Core Contract

Phase 2 answers: **WHAT should Vera do?**  
Phase 3 answers: **HOW should Vera express it?**  
Phase 5 answers: **CAN THIS ALREADY-COMPOSED OUTBOUND ACTION BE TRANSMITTED RIGHT NOW?**

Phase 5 serves exclusively as an **outreach governance transmission barrier** between Phase 3 message composition and Phase 4 API serialization:

```text
Phase 1: Normalized Authoritative Context (ContextStore)
              ↓
Phase 2: Deterministic Decision Engine (WHAT)
              ↓
Phase 3: Grounded Message Composer (HOW)
              ↓
Phase 5: Outreach Governance Barrier (EXACT DEDUP & CONSENT)
              ↓
Phase 4: Challenge API Response (/v1/tick)
```

### Critical Policy Grounding Statement
> **The challenge directly specifies `suppression_key`-based deduplication (`suppression_key: str # for dedup`, `challenge-brief.md` L125; `used by Redis dedup to prevent re-sends`, `engagement-design.md` L94). It does NOT specify decaying cooldowns or aggregate merchant/customer frequency caps. Therefore Phase 5 performs exact suppression-key deduplication without inferred expiration.**

> **Date, week, month, quarter, `30d`, and `6mo` tokens appearing inside suppression keys are treated strictly as unique event, cohort, or artifact identifiers, not governance cadence instructions.**

---

## 2. Target Phase 5 Decision Pipeline

For any composed message, transmission eligibility is evaluated strictly as:

```text
1. Phase 2 WAIT / END
    → SUPPRESS (reason_code = DECISION_WAIT_OR_END)

2. Invalid Phase 3 composition (empty body, missing CTA, empty suppression key)
    → SUPPRESS (reason_code = INVALID_COMPOSITION)

3. Customer-scoped outreach without valid customer consent
    → SUPPRESS (reason_code = CONSENT_RESTRICTED)

4. Previously transmitted identical (tenant_key, suppression_key)
    → SUPPRESS (reason_code = DUPLICATE_SUPPRESSED)

5. Otherwise
    → SEND (reason_code = ELIGIBLE)
```

No other business policy, scoring rule, or rate limit may influence transmission.

---

## 3. Suppression Reason Taxonomy

The suppression reason taxonomy contains only behaviorally reachable, evidence-backed reason codes:

1. **`ELIGIBLE`**:
   - Passed composition validation, customer consent checks, and has not been previously transmitted for this tenant. Permitted to transmit.
2. **`DUPLICATE_SUPPRESSED`**:
   - An outreach matching the exact composite identity `(tenant_key, suppression_key)` has already been recorded in history.
3. **`DECISION_WAIT_OR_END`**:
   - Phase 2 decision was `WAIT` or `END`. Suppressed fail-closed to honor intentional restraint.
4. **`CONSENT_RESTRICTED`**:
   - Customer context is missing, customer explicitly opted out (`reminder_opt_in == False`), or customer has empty consent scope.
5. **`INVALID_COMPOSITION`**:
   - Composed message has an empty body, missing CTA, or empty suppression key.
6. **`TENANT_MISMATCH`**:
   - Unrecognized or malformed tenant identifier.

All unsupported reason codes (`COOLDOWN_ACTIVE`, `MERCHANT_FREQUENCY_CAPPED`, `CUSTOMER_FREQUENCY_CAPPED`) have been removed.

---

## 4. Exact Deduplication & Tenant Semantics

### Deduplication Identity
Deduplication identity is defined strictly as the tuple:
$$\text{Deduplication Identity} = (\text{tenant\_key}, \text{suppression\_key})$$

Once an outreach matching `(tenant_key, suppression_key)` is transmitted and recorded in the in-memory history:
- Any subsequent attempt to transmit the identical pair is **SUPPRESSED** as `DUPLICATE_SUPPRESSED`.
- There is **no decaying cooldown window** and **no automatic expiration** (no 24h, 7d, 30d, or 90d reset).
- Different suppression keys for the same merchant or customer are completely independent and evaluate on their own merits without being blocked by previous messages.

### Tenant Isolation Semantics
1. **Merchant-scoped outreach** (`target_scope == "merchant"`):
   - `tenant_key = f"m:{merchant_id}"`
   - An outreach to Merchant 1 with key $K$ (`m:m_001`, $K$) does **not** suppress Merchant 2 with the same key (`m:m_002`, $K$).
2. **Customer-scoped outreach** (`target_scope == "customer"`):
   - `tenant_key = f"c:{merchant_id}:{customer_id}"`
   - An outreach to Customer 1 under Merchant 1 with key $K$ (`c:m_001:c_001`, $K$) does **not** suppress Customer 2 under Merchant 1 (`c:m_001:c_002`, $K$).
   - An outreach to Customer 1 under Merchant 1 does **not** suppress Customer 1 under Merchant 2 (`c:m_002:c_001`, $K$).

---

## 5. Consent & Architectural Restraint Boundaries

1. **Consent Boundary**:
   - Customer consent is strictly enforced fail-closed. Missing consent, explicit opt-out (`reminder_opt_in == False`), or empty consent scope immediately results in `SUPPRESS` (`CONSENT_RESTRICTED`).
   - Merchant-level outreach (e.g. research digests, performance dips, partner planning) is evaluated at merchant scope and is never blocked by customer consent.
2. **WAIT / END Invariant**:
   - If Phase 2 determines `ActionType.WAIT` or `ActionType.END`, Phase 5 returns `SUPPRESS` (`DECISION_WAIT_OR_END`).
   - Phase 5 **never transforms a WAIT or END into a SEND**.

---

## 6. Atomic Concurrency Model

- All check-and-record operations execute inside `OutreachStore._lock` (`threading.RLock`).
- **Race Condition Invariant**:
  - If 20 simultaneous threads evaluate the same `(tenant_key, suppression_key)` at timestamp $T$, exactly **1 thread** wins and returns `SEND`; the remaining **19 threads** encounter the recorded send and return `SUPPRESS` (`DUPLICATE_SUPPRESSED`).
  - Exactly 1 record is created in history.
  - Distinct suppression keys evaluated concurrently do not block each other.

---

## 7. Zero Wall-Clock Dependency

- All audit trace timestamps are recorded using the simulation timestamp provided in the tick request (`body.now`).
- Zero calls to `datetime.now()` or `time.time()`.
- Identical requests against identical history yield 100% bit-for-bit identical decisions.
