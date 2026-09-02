# Phase 2 — Vera Decision Intelligence Policy

## 1. Executive Summary & Decision Pipeline

Phase 2 establishes Vera's deterministic **Decision Intelligence Engine**.
The engine operates as a pure, reproducible transformation from grounded context into a single authoritative next action:

```text
Normalized Context (Category, Merchant, Trigger, Customer)
          ↓
Grounded Fact Extraction (extract_facts)
          ↓
Grounded Signal Derivation (extract_signals)
          ↓
Candidate Action Generation (generate_candidates)
          ↓
Strict Eligibility Filtering (evaluate_eligibility)
          ↓
Transparent Scoring & Deterministic Ranking (rank_and_select_winner)
          ↓
Authoritative Decision & Audit Trace (Decision, DecisionTrace)
```

### Core Invariants:
1. **Zero Text / Message Generation**: Determines strictly *what action to take and why*, not the final wording.
2. **Zero LLM or External I/O**: Completely local, deterministic, and fast (~1.8 ms end-to-end).
3. **No Naive Urgency**: Trigger urgency is only a 10-point factor out of 100. High urgency with weak evidence will lose to strongly grounded actions.
4. **No Fabricated Offers or Facts**: Category templates can never masquerade as merchant offers. Expired offers are strictly disqualified.
5. **Fail-Closed Consent**: Customer outreach requires explicit, positive opt-in and valid scopes. Missing or unrecorded consent results in `WAIT`.
6. **Context-Driven Seasonality & Contrarian Pivots**: Expected seasonal drops are reframed rather than alarmed; adverse dine-in events (e.g. Saturday IPL in restaurants) trigger delivery pivots if an active delivery offer exists.

---

## 2. Signal Taxonomy

Every signal is deterministically derived from grounded context attributes without causal guessing:

| Signal Type | Source Attributes | Derivation Rule | Semantic Meaning |
|---|---|---|---|
| `PERF_CALLS_DROP_SEVERE` | `performance.calls_pct` / trigger delta | calls_pct <= -0.40 | Inbound customer calls decreased by >=40% w/w |
| `PERF_CALLS_DROP_MODERATE` | `performance.calls_pct` / trigger delta | -0.40 < calls_pct <= -0.15 | Inbound customer calls dropped between 15% and 40% |
| `PERF_VIEWS_DROP_SEVERE` | `performance.views_pct` / trigger delta | views_pct <= -0.25 | Search/listing impressions dropped by >=25% |
| `PERF_SPIKE` | `trigger.payload.delta_pct` | delta_pct >= +0.20 | Significant positive surge on a key metric |
| `CTR_BELOW_PEER` | `performance.ctr`, `peer_stats.avg_ctr` | merchant.ctr < avg_ctr | Click-through rate lags metro category average |
| `CTR_ABOVE_PEER` | `performance.ctr`, `peer_stats.avg_ctr` | merchant.ctr >= avg_ctr | Click-through rate meets or exceeds peer benchmark |
| `IS_EXPECTED_SEASONAL` | `trigger.payload.is_expected_seasonal` | True in trigger payload | Performance dip matches historical category seasonal lull |
| `EVENT_TODAY` | `trigger.payload.match` | Match scheduled today | Major regional/city event occurring today |
| `EVENT_HOME_VIEWING_SHIFT`| `trigger.payload.is_weeknight` | `is_weeknight == False` (restaurants) | Weekend match shifts restaurant dine-in covers to home-viewing |
| `FESTIVAL_UPCOMING` | `trigger.payload.days_until` | days_until <= 21 | Upcoming festival creates seasonal demand spike |
| `HAS_ACTIVE_OFFER` | `merchant.offers` | Any offer with status == "active" | Merchant has at least one live promotional offer |
| `HAS_DELIVERY_OFFER` | `merchant.offers` | Active offer with delivery/bogo/takeaway keywords | Merchant has active offer suitable for delivery pivot |
| `UNVERIFIED_LISTING` | `identity.verified` | verified == False | Google Business Profile is unverified |
| `SUBSCRIPTION_EXPIRING` | `subscription.days_remaining` | days_remaining <= 14 | Plan expiring within two weeks |
| `SUBSCRIPTION_EXPIRED` | `subscription.status` | status == "expired" | Plan has expired |
| `HAS_HIGH_RISK_ADULT_COHORT` | `customer_aggregate.high_risk_adult_count` | count > 0 | Dentist has active high-risk caries adult roster |
| `HAS_CHRONIC_RX_COHORT` | `customer_aggregate.chronic_rx_count` | count > 0 | Pharmacy has patients on ongoing repeat medications |
| `RESEARCH_DIGEST_MATCHED` | `category.digest` | Trigger item matches digest item | Relevant peer-reviewed study available |
| `SUPPLY_ALERT_ACTIVE` | `trigger.payload.affected_batches`| Batches present | Manufacturer / regulatory batch sub-potency alert |
| `ACTIVE_PLANNING_ACTIVE` | `trigger.payload.intent_topic` | Intent topic present | Merchant actively requested packaging/pricing draft |
| `CURIOUS_CADENCE_DUE` | `trigger.kind` in cadence triggers | Window open | Scheduled curiosity check-in due |
| `CUSTOMER_CONSENT_VALID` | `customer.consent`, `preferences`| reminder_opt_in is True and scope non-empty | Customer authorized outbound reminders |
| `CUSTOMER_OPTED_OUT` | `customer.consent`, `preferences`| reminder_opt_in is False or scope is empty/None | Outbound communication not permitted |
| `CUSTOMER_RECALL_DUE` | `trigger.kind == "recall_due"` | Customer present | Routine cleaning / service window open |
| `CUSTOMER_REFILL_DUE` | `trigger.kind == "chronic_refill_due"`| Customer present | Medication stock runs out within days |
| `CUSTOMER_LAPSED` | `customer.state` | in ("lapsed_soft", "lapsed_hard") | Customer inactive beyond target cadence |
| `CUSTOMER_BRIDAL_WINDOW` | `preferences.wedding_date` | Date present | Bride in skin-prep or package planning window |

---

## 3. Action Taxonomy & Eligibility Matrix

| Action ID | Scope | Priority Tier | Required Evidence | Permitted Categories | Offer Reqd? | Consent Reqd? | Fallback |
|---|---|---|---|---|---|---|---|
| `ADDRESS_SUPPLY_ALERT` | merchant | Tier 1 (Critical) | Batch numbers, manufacturer, molecule | `pharmacies` | No | No | `WAIT` |
| `CUSTOMER_REFILL` | customer | Tier 2 (Customer Care) | Molecule list, stock runout date | `pharmacies` | No | **Yes** | `WAIT` |
| `CUSTOMER_RECALL` | customer | Tier 2 (Customer Care) | Available slots, due service | `dentists`, `salons` | No | **Yes** | `WAIT` |
| `CUSTOMER_FOLLOWUP` | customer | Tier 2 (Customer Care) | Wedding date or trial date | `salons`, `gyms` | No | **Yes** | `WAIT` |
| `CUSTOMER_WINBACK` | customer | Tier 2 (Customer Care) | Lapsed state, previous service/focus | `gyms`, `salons`, `restaurants` | No | **Yes** | `WAIT` |
| `PROMOTE_DELIVERY_OFFER` | merchant | Tier 3 (Urgent Rev) | Match/event details, active delivery offer | `restaurants` | **Yes** | No | `WAIT` |
| `CONTINUE_PLANNING` | merchant | Tier 3 (Urgent Rev) | Intent topic, merchant locality | All | No | No | `WAIT` |
| `ADDRESS_PERFORMANCE_DIP` | merchant | Tier 3 (Urgent Rev) | Delta % (calls/views), metric name | All | No | No | `WAIT` |
| `CAPITALIZE_PERF_SPIKE` | merchant | Tier 3 (Urgent Rev) | Delta % spike, metric name | All | No | No | `WAIT` |
| `RENEW_SUBSCRIPTION` | merchant | Tier 3 (Urgent Rev) | Days remaining / renewal amount | All | No | No | `WAIT` |
| `USE_RESEARCH_INSIGHT` | merchant | Tier 4 (Routine) | Matched digest study, trial N / source citation | `dentists`, `pharmacies`, `gyms` | No | No | `WAIT` |
| `REFRAME_SEASONAL_DIP` | merchant | Tier 4 (Routine) | Expected seasonal flag, dip delta | All | No | No | `WAIT` |
| `CURIOUS_ASK` | merchant | Tier 4 (Routine) | Merchant owner name, touchpoint cadence | All | No | No | `WAIT` |
| `RESOLVE_LISTING_ISSUE` | merchant | Tier 4 (Routine) | Unverified profile (`verified == False`) | All | No | No | `WAIT` |
| `ADDRESS_COMPETITOR_CHANGE`| merchant | Tier 4 (Routine) | Competitor name, distance km | All | No | No | `WAIT` |
| `RESPOND_TO_REVIEW_THEME`| merchant | Tier 4 (Routine) | Sentiment theme, occurrence count | All | No | No | `WAIT` |
| `CELEBRATE_MILESTONE` | merchant | Tier 4 (Routine) | Milestone value, metric | All | No | No | `WAIT` |
| `PREPARE_FESTIVAL_CAMPAIGN`| merchant | Tier 4 (Routine) | Festival name, days until | All | No | No | `WAIT` |
| `WAIT` | any | Tier 5 (Fallback) | None (always eligible) | All | No | No | N/A |
| `END` | any | Tier 5 (Fallback) | Terminal state indicator | All | No | No | N/A |

---

## 4. Candidate Eligibility Rules

Every candidate is strictly filtered before scoring:
1. **Scope Alignment**: If the triggering event is customer-scoped (`trigger.scope == "customer"`), merchant-facing actions are ineligible (and vice versa).
2. **Category Restriction**: If `allowed_categories` is set, `category.slug` must match.
3. **Consent Fail-Closed**: If `requires_customer_consent` is True:
   - If `customer` is None $\to$ Ineligible.
   - If `SignalType.CUSTOMER_OPTED_OUT` fired $\to$ Ineligible.
   - If `SignalType.CUSTOMER_CONSENT_VALID` is absent $\to$ Ineligible.
4. **Offer Ownership & Validity**: If `requires_active_merchant_offer` is True:
   - Must have an active merchant offer (`supporting_offer.status == "active"`).
   - Category catalog templates (`category.offer_catalog`) **never** qualify as merchant offers.
   - For `PROMOTE_DELIVERY_OFFER`, `SignalType.HAS_DELIVERY_OFFER` must be present.
5. **Seasonal Preemption**: If `SignalType.IS_EXPECTED_SEASONAL` is present, `ADDRESS_PERFORMANCE_DIP` is strictly ineligible. Expected seasonal drops must be reframed (`REFRAME_SEASONAL_DIP`), not alarmed.
6. **Evidence Requirement**: Non-fallback actions must be supported by grounded facts (`len(evidence_facts) > 0`).

---

## 5. Scoring Formula & Rationale

Total candidate score is computed transparently out of 100:

$$\text{Total Score} = \text{Trigger Relevance} (0-40) + \text{Evidence Strength} (0-25) + \text{Category Fit} (0-15) + \text{Actionability} (0-10) + \text{Urgency Normalized} (0-10)$$

### Component Weights Rationale:
- **Trigger Relevance (0 - 40)**: Answers "Why Now?". Directly addressing the triggering event is the primary requirement of the judge.
- **Evidence Strength (0 - 25)**: Rewarded proportionally to grounded fact count ($5 \text{ pts} \times N \text{ facts}$, capped at 25). Prevents speculative decisions.
- **Category Fit (0 - 15)**: 15 points for vertical-specialized actions (e.g. `dentists` + `USE_RESEARCH_INSIGHT`, `pharmacies` + `ADDRESS_SUPPLY_ALERT`), 10 points for standard actions.
- **Actionability Bonus (0 - 10)**: 5 points for ready-to-run active offers, 5 points for concrete next steps.
- **Urgency Normalized (0 - 10)**: Scales trigger urgency (1-5 $\to$ 2-10). Acts as an engineering tie-breaker, **never** dominating evidence or fit.

---

## 6. Deterministic Tie-Breaking

When candidates are eligible and scored:
1. `is_eligible`: True before False.
2. `total_score`: Higher score wins.
3. `priority_tier`: Tier 1 (Critical Safety) > Tier 2 (Customer Care) > Tier 3 (Urgent Merchant Revenue) > Tier 4 (Routine Engagement) > Tier 5 (Fallback).
4. `trigger.urgency`: Higher urgency wins.
5. `len(evidence_facts)`: More grounded evidence wins.
6. `action_type.value`: Alphabetical sort as final immutable tie-breaker.

---

## 7. Contrarian & Contextual Reasoning

### Case Study 5 Generalized Pattern:
- Naive heuristic: Saturday IPL match $\to$ "Offer dine-in discount for match night".
- Grounded reality: Category intelligence indicates weekend IPL matches shift covers -12% away from dine-in to home-viewing.
- Engine policy: When `SignalType.EVENT_HOME_VIEWING_SHIFT` fires in `restaurants`:
  - Dine-in promotions are suppressed.
  - `PROMOTE_DELIVERY_OFFER` receives a +5 relevance boost and category fit maximum (15 pts).
  - If no active delivery offer exists, it fails closed $\to$ `WAIT` rather than fabricating an offer.

---

## 8. Test Verification & Regression Matrix

All 57 unit, integration, and regression tests pass (1.32s runtime):
- **10 Canonical Case Studies**: 100% Pass.
- **Perturbed Variants**: 100% Pass (different merchant IDs, cities, dates, and metrics produce correct decisions without overfitting).
- **Adversarial Edge Cases**:
  - Test A (Expired Offer) $\to$ Offer promotion disqualified.
  - Test B (Catalog Hallucination) $\to$ Category template cannot be promoted.
  - Test C (Seasonal Dip) $\to$ Expected drop triggers reframe, not alarmist dip.
  - Test D & E (Consent Fails Closed) $\to$ Opt-out or missing consent results in `WAIT`.
  - Test F & G (Context Freshness) $\to$ Newer version V2 always overrides V1.
  - Test H (Weak Evidence + High Urgency) $\to$ Standing down (`WAIT`) beats blind action.
  - Test K (Contrarian without Delivery Offer) $\to$ Fails closed.
- **100-Run Determinism**: 100 identical runs produce bit-for-bit identical `Decision`, dictionary, and SHA-256 fingerprint.

---

## 9. Latency Benchmark

Measured on Python 3.14 (100 iterations):
- **Signal Extraction**: 0.015 ms / call
- **Candidate Generation**: 0.094 ms / call
- **Candidate Scoring & Ranking**: 0.034 ms / call
- **Complete `decide()` Orchestration**: **1.859 ms / call**
