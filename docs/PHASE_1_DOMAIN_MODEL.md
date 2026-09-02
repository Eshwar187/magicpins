# Phase 1 — Vera Domain Model & Grounded Fact System

## 1. Executive Summary

Phase 1 establishes the foundational internal domain representation, context versioning storage, and deterministic grounded fact extraction system for the Magicpin Vera message engine.

This layer sits directly between incoming raw challenge JSON payloads and later decision logic. It strictly enforces:
- **Zero Fabrication**: Vera can only reason about facts that are explicitly grounded in the supplied context.
- **Dataset-First Schemas**: Models reflect exact JSON paths in `dataset/categories/*.json`, `dataset/merchants_seed.json`, `dataset/customers_seed.json`, and `dataset/triggers_seed.json`.
- **Missing-Value Discipline**: `missing != 0`, `missing != false`, and `missing scope != []`. Missing and null values remain `None` and are never coerced to artificial defaults.
- **Policy vs Fact Separation**: Category rules (voices, forbidden taboos, allowed terms) are maintained as static vertical governance (`CategoryProfile`), completely separated from transient business facts (`Fact`).
- **Atomic Context Versioning**: The `ContextStore` handles out-of-order delivery, rejects stale versions, provides idempotent deduplication, and completely isolates context scopes.
- **Strict Determinism**: Zero reliance on non-deterministic hashing or arbitrary dict ordering. Fact lists and cryptographic fingerprints are 100% stable across Python processes.

---

## 2. Package Architecture

```
app/
├── __init__.py
└── domain/
    ├── __init__.py
    ├── models/
    │   ├── __init__.py
    │   ├── enums.py            # Scope, CustomerState, SubscriptionStatus, FactType
    │   ├── category.py         # CategoryProfile, VoiceProfile, PeerStats, DigestItem
    │   ├── merchant.py         # MerchantState, Identity, PerformanceSnapshot, MerchantOffer
    │   ├── customer.py         # CustomerStateModel, Relationship, Preferences, Consent
    │   └── trigger.py          # TriggerState with demonstrated payload accessors
    ├── context_store.py        # Thread-safe scoped storage with atomic version semantics
    └── facts/
        ├── __init__.py
        ├── fact.py             # Immutable Fact model with provenance and stable sort key
        ├── extractor.py        # Deterministic extract_facts() pure function
        ├── fingerprint.py      # Canonical JSON serializer and SHA-256 fingerprinting
        └── inventory.py        # Human-readable fact inventory debug formatter
```

---

## 3. Domain Model Specifications

### 3.1 `CategoryProfile` (`app/domain/models/category.py`)
Represents vertical reference configuration loaded from `dataset/categories/<slug>.json`:
- `slug`: String vertical identifier (`"dentists"`, `"salons"`, `"restaurants"`, `"gyms"`, `"pharmacies"`).
- `display_name`: Human-readable vertical label.
- `voice`: `VoiceProfile` containing `tone`, `register`, `code_mix`, `vocab_allowed`, `vocab_taboo`, `salutation_examples`, and `tone_examples`.
- `offer_catalog`: List of canonical `OfferTemplate` items (`id`, `title`, `value`, `audience`, `type`).
- `peer_stats`: `PeerStats` containing baseline city/segment metrics (`avg_rating`, `avg_review_count`, `avg_views_30d`, `avg_calls_30d`, `avg_directions_30d`, `avg_ctr`, `avg_photos`, `avg_post_freq_days`) plus vertical-specific fields (`retention_6mo_pct` [dentists], `retention_3mo_pct` [salons], `retention_30d_pct` [restaurants], `monthly_churn_pct` & `trial_to_paid_pct` [gyms], `delivery_share_pct` & `repeat_customer_pct` [pharmacies]).
- `digest`: List of `DigestItem` records (`id`, `kind`, `title`, `source`, `summary`, `actionable`, plus optional `trial_n`, `patient_segment`, `deadline_iso`, `credits`).
- `patient_content_library`, `seasonal_beats`, `trend_signals`, `regulatory_authorities`, `professional_journals`.
- Preserves unknown/forward-compatible fields via `extra="allow"`.

### 3.2 `MerchantState` (`app/domain/models/merchant.py`)
Represents merchant state loaded from `dataset/merchants_seed.json`:
- `merchant_id`: Unique identifier (e.g. `"m_001_drmeera_dentist_delhi"`).
- `category_slug`: Associated vertical.
- `identity`: `MerchantIdentity` (`name`, `city`, `locality`, `place_id`, `verified` [bool], `languages` [list[str]], `owner_first_name` [str|None], `established_year` [int|None]).
- `subscription`: `Subscription` (`status`: `"active"`|`"expired"`|`"trial"`, `plan`: str, `days_remaining`: int|None, `days_since_expiry`: int|None, `renewed_at`: str|None).
- `performance`: `PerformanceSnapshot` (`window_days`: int, `views`: int|None, `calls`: int|None, `directions`: int|None, `ctr`: float|None, `leads`: int|None, `delta_7d`: `Delta7d`|None).
  - `Delta7d`: `views_pct`: float|None, `calls_pct`: float|None, `ctr_pct`: float|None.
  - **Fidelity Guarantee**: Missing performance metrics remain `None`. They are never converted to 0.
- `offers`: List of `MerchantOffer` (`id`, `title`, `status`, `started`, `ended`).
- `conversation_history`: List of `ConversationTurn` (`ts`, `from_role`, `body`, `engagement`).
- `customer_aggregate`: Dict of customer cohort metrics (`total_unique_ytd`, `lapsed_180d_plus`, `high_risk_adult_count`, etc.).
- `signals`: Derived signal strings.
- `review_themes`: List of `ReviewTheme` (`theme`, `sentiment`, `occurrences_30d`, `common_quote`).

### 3.3 `CustomerStateModel` (`app/domain/models/customer.py`)
Represents customer state loaded from `dataset/customers_seed.json`:
- `customer_id`: Unique customer identifier (e.g. `"c_001_priya_for_m001"`).
- `merchant_id`: Associated merchant.
- `identity`: `CustomerIdentity` (`name`, `phone_redacted` [str|None], `language_pref`, `age_band` [str|None], `senior_citizen` [bool|None]).
- `relationship`: `Relationship` (`first_visit`, `last_visit`, `visits_total` [int|None], `services_received` [list[str]], `lifetime_value` [float|None], `chronic_conditions` [list[str]], `favourite_dish` [str|None]).
- `state`: Lifecycle state string (`"new"`, `"active"`, `"lapsed_soft"`, `"lapsed_hard"`, `"churned"`).
- `preferences`: `CustomerPreferences` (`channel`, `preferred_slots`, `reminder_opt_in` [bool|None], `delivery_address`, `preferred_stylist`, `training_focus`, `wedding_date`, etc.).
- `consent`: `Consent` (`opted_in_at` [str|None], `scope` [list[str]|None]).
  - **Fidelity Guarantee**: `scope=None` (unrecorded/missing), `scope=[]` (opted out / empty), and `scope=["recall_reminders"]` (explicit permitted topics) are strictly distinguished.

### 3.4 `TriggerState` (`app/domain/models/trigger.py`)
Represents incoming triggers from `dataset/triggers_seed.json`:
- `id`, `scope` (`"merchant"` | `"customer"`), `kind`, `source` (`"external"` | `"internal"`), `merchant_id`, `customer_id` (str|None).
- `payload`: Exact raw dictionary preserved 100% intact.
- `urgency`: Priority integer (1 to 5).
- `suppression_key`: Deduplication / suppression string.
- `expires_at`: ISO timestamp string or None.
- **Demonstrated Accessors**: Strongly typed helper properties for fields actually present in seed data: `metric`, `delta_pct`, `window`, `top_item_id`, `service_due`, `available_slots`, `days_remaining`, `plan`, `match`, `venue`, `affected_batches`, `molecule`.

---

## 4. Grounded Fact System & Provenance

### 4.1 Fact Model
```python
@dataclass(frozen=True)
class Fact:
    fact_id: str             # SHA-256 digest of (source_scope, source_context_id, source_path, fact_type, canonical_value)
    fact_type: str           # FactType taxonomy value
    name: str                # Logical path, e.g. "merchant.performance.calls"
    value: Any               # Exact grounded value
    source_scope: str        # "merchant" | "category" | "trigger" | "customer"
    source_context_id: str   # Unique context ID
    source_version: int      # Context version at extraction time
    source_path: str         # Exact path within raw payload, e.g. "performance.calls"
    timestamp: str | None    # Source context timestamp if present
```

### 4.2 Fact Taxonomy (`FactType`)
- `IDENTITY`: Merchant business name, languages, verification status.
- `LOCATION`: Merchant city, locality.
- `METRIC`: Verified performance metrics (views, calls, CTR, directions, leads).
- `METRIC_CHANGE`: 7-day performance percentage deltas.
- `OFFER`: Catalog offers created by merchant.
- `SUBSCRIPTION`: Plan name, status, days remaining / since expiry.
- `CUSTOMER_COHORT`: Aggregated customer counts (high risk adults, lapsed >180d, etc.).
- `CUSTOMER_IDENTITY`: Customer name, phone, language preference, age band.
- `CUSTOMER_RELATIONSHIP`: Visits total, lifetime value, last visit date.
- `CUSTOMER_STATE`: Customer lifecycle state.
- `CUSTOMER_PREFERENCE`: Preferred booking slots, preferred channel.
- `CUSTOMER_CONSENT`: Outreach opt-in timestamp, permitted consent scope.
- `TRIGGER_METADATA`: Trigger kind, urgency level, suppression key.
- `TRIGGER_PAYLOAD`: Specific trigger event parameters (delta %, match details, batch numbers).
- `PEER_BENCHMARK`: Vertical benchmark averages from peer stats.
- `RESEARCH_EVIDENCE`: Matched clinical digest item (trial sample size, publication citation, findings).
- `REVIEW_THEME`: Clustered sentiment themes from reviews.

### 4.3 Deterministic Ordering
Facts implement `__lt__` using a stable, 5-element tuple:
```python
sort_key = (
    self.source_scope,
    self.source_context_id,
    self.source_path,
    self.fact_type,
    canonical_json_dumps(self.value),
)
```
No fact ordering ever depends on dict insertion order, set hashing, or memory addresses.

---

## 5. ContextStore Semantics

The `ContextStore` provides thread-safe, atomic versioning over stored context envelopes:

| Ingestion Event | Condition | Store Action | Result Status | HTTP Mapping |
|---|---|---|---|---|
| **New Record** | `(scope, id)` not in store | Inserts envelope | `STORED` | 200 OK |
| **Newer Version** | `version > current_version` | Atomically replaces envelope | `STORED` | 200 OK |
| **Identical Version** | `version == current_version` AND `payload == current_payload` | No-op (idempotent duplicate) | `IDEMPOTENT_NOOP` | 200 OK |
| **Version Conflict** | `version == current_version` AND `payload != current_payload` | Rejects mutation | `STALE_VERSION` | 409 Conflict |
| **Stale Version** | `version < current_version` | Rejects mutation | `STALE_VERSION` | 409 Conflict |

### Scope Isolation
Storage keys are tuples of `(scope, context_id)`. Identical IDs in different scopes (e.g. a merchant with ID `x` and a trigger with ID `x`) reside in isolated namespaces and cannot collide.

---

## 6. Canonical Fingerprinting & Numeric Fidelity

The fingerprinting utility (`compute_canonical_fingerprint`) enforces strict canonicalization:
1. **Key Sorting**: Dictionaries recursively sort keys alphabetically.
2. **Numeric Fidelity**: Floats preserve their exact shortest round-trip decimal representation (`0.1234564 != 0.1234565`). No arbitrary precision truncation is applied.
3. **Boolean vs Integer**: Booleans (`True`/`False`) serialize as JSON booleans (`true`/`false`), distinguished from integers (`1`/`0`).
4. **Unicode Stability**: Serialized with `ensure_ascii=False` so UTF-8 characters are preserved without escape variance.
5. **Null Stability**: Missing/None attributes serialize as JSON `null`.
6. **SHA-256**: Hexadecimal digest of canonical UTF-8 bytes.

---

## 7. Golden Fixtures & Acceptance Test Results

All 4 golden fixtures were verified with 100% behavioral fidelity:

### Fixture 1: Dr. Meera Dental Clinic (`m_001_drmeera_dentist_delhi`)
- **Inputs**: `dentists.json`, `m_001`, `trg_001_research_digest_dentists`.
- **Verified Facts**:
  - `merchant.name` = `"Dr. Meera's Dental Clinic"`
  - `merchant.owner_first_name` = `"Meera"`
  - `merchant.locality` = `"Lajpat Nagar"`
  - `merchant.performance.ctr` = `0.021`
  - `merchant.performance.delta_7d.views_pct` = `0.18`
  - `merchant.customer_aggregate.high_risk_adult_count` = `124`
  - `category.digest.matched` = Trial N `2100`, source `"JIDA Oct 2026, p.14"`

### Fixture 2: Priya Dental Recall Customer (`c_001_priya_for_m001`)
- **Inputs**: `dentists.json`, `m_001`, `trg_003_recall_due_priya`, `c_001`.
- **Verified Facts**:
  - `customer.name` = `"Priya"`
  - `customer.language_pref` = `"hi-en mix"`
  - `customer.state` = `"lapsed_soft"`
  - `customer.visits_total` = `4`
  - `customer.preferred_slots` = `"weekday_evening"`
  - `customer.reminder_opt_in` = `True`
  - `customer.consent.scope` = `["recall_reminders", "appointment_reminders"]`
  - `trigger.payload.available_slots` = `2` slots

### Fixture 3: Bharat Dental Care (Severe Dip, Unverified, Missing Offers)
- **Inputs**: `dentists.json`, `m_002_bharat_dentist_mumbai`, `trg_004_perf_dip_bharat`.
- **Verified Facts**:
  - `merchant.verified` = `False`
  - `merchant.subscription.days_remaining` = `12`
  - `merchant.performance.calls` = `4`
  - `merchant.performance.delta_7d.calls_pct` = `-0.50`
  - Offers: Exactly `0` active offers extracted. Zero fabricated claims.

### Fixture 4: Anonymous Walk-in Customer (Missing & Unknown Values)
- **Inputs**: `pharmacies.json`, `m_010_sunrisepharm_pharmacy_lucknow`, `trg_021_unverified_gbp_sunrise`, `c_015_anonymous_for_m010`.
- **Verified Facts**:
  - `customer.name` = `"(walk-in, no profile)"`
  - `customer.phone_redacted` = skipped (raw null)
  - `customer.reminder_opt_in` = `False` (explicit boolean false)
  - `customer.consent.scope` = `[]` (explicit empty list)
  - `customer.consent.opted_in_at` = skipped (raw null)

---

## 8. Benchmark & Performance Profile

Benchmarked across 100 iterations on Python 3.14.0 (Windows):
- **Category + Merchant + Customer + Trigger Normalization**: **0.089 ms / call**
- **Fact Extraction & Provenance Generation**: **1.727 ms / call**
- **Total Combined Latency**: **1.816 ms / call**

This performance provides ample headroom within the 30-second per-call judge timeout.
