# PHASE 0 — MAGICPIN VERA CHALLENGE RECONNAISSANCE REPORT

**Project**: Magicpin AI Challenge — Build the Message Engine Behind Vera  
**Scope**: Repository Audit, Contract Reverse-Engineering, Dataset Analysis, Judge Deconstruction  
**Status**: Complete  
**Date**: September 2026  

---

## A. Repository Map

The repository is structured as a standalone competition evaluation bundle consisting of specification briefs, background architectural proposals, dataset seeds with a deterministic expansion generator, API request/response examples, canonical case study anchors, and an automated LLM judge simulator.

| File Path | Size / Lines | Core Purpose | Role in System |
|---|---|---|---|
| `magicpin-ai-challenge/challenge-brief.md` | 27,051 bytes / 545 lines | Master challenge specification | Defines the product problem, the 4-context composition framework, behavioral rules, compulsion levers, anti-patterns, and baseline evaluation rubric. |
| `magicpin-ai-challenge/challenge-testing-brief.md` | 22,875 bytes / 558 lines | Technical evaluation contract | Defines the 5 HTTP endpoints (`/healthz`, `/metadata`, `/context`, `/tick`, `/reply`), test lifecycle phases (Warmup, Test Window, Adaptive Injection, Replay, Scoring), and rate/latency limits. |
| `magicpin-ai-challenge/engagement-design.md` | 18,456 bytes / 326 lines | Architecture & data design draft | Explains why the 4-context model was conceived at magicpin, detailed dataclass signatures, recurring cron loops, and production pain points. |
| `magicpin-ai-challenge/engagement-research.md` | 13,343 bytes / 199 lines | Production codebase audit | Audits existing legacy agents (`VeraMerchantAgent`, `CustomerIncomingAgent`, `vera-mcp`, `merchant-support-mcp`, Redis caching, aryan client) to map existing vs net-new context. |
| `magicpin-ai-challenge/judge_simulator.py` | 35,828 bytes / 963 lines | Judge evaluation harness | Complete runnable test harness with multi-LLM provider support (OpenAI, Anthropic, Gemini, DeepSeek, Groq, Ollama, OpenRouter). Contains exact judge scoring prompts, scoring dimensions, penalties, and replay scenarios. |
| `magicpin-ai-challenge/examples/api-call-examples.md` | 19,974 bytes / 616 lines | Golden API interaction transcripts | Comprehensive HTTP request/response payloads for every test phase: warmup, tick, multi-turn replies (engaged, auto-reply, hostile, curveball), mid-test context updates, and failure modes. |
| `magicpin-ai-challenge/examples/case-studies.md` | 18,043 bytes / 339 lines | 10 Scored anchor case studies | 2 cases per vertical (10 total) showing 4-context inputs, ideal composed messages, compulsion levers used, dimension-by-dimension scores (44-50/50), and judge scoring patterns. |
| `magicpin-ai-challenge/dataset/generate_dataset.py` | 14,800 bytes / 313 lines | Dataset expansion script | Deterministic generator (`SEED = 20260426`) expanding 10 merchant seeds → 50 merchants, 15 customer seeds → 200 customers, and 25 trigger seeds → 100 triggers, plus generating 30 canonical test pairs (`test_pairs.json`). |
| `magicpin-ai-challenge/dataset/merchants_seed.json` | 15,139 bytes / 315 lines | 10 Representative merchant contexts | Hand-crafted base merchant profiles (2 per vertical) with detailed performance snapshots, active/expired offers, conversation history, customer aggregates, derived signals, and review themes. |
| `magicpin-ai-challenge/dataset/customers_seed.json` | 10,746 bytes / 141 lines | 15 Representative customer contexts | Customer profiles across merchants with relationship history (visits, services, LTV), lifecycle states, preferences, and explicit consent scopes. |
| `magicpin-ai-challenge/dataset/triggers_seed.json` | 11,734 bytes / 181 lines | 25 Representative trigger contexts | Triggers spanning external/internal sources, merchant/customer scopes, urgency levels 1-5, dedup suppression keys, and domain-specific payloads. |
| `magicpin-ai-challenge/dataset/categories/dentists.json` | 7,303 bytes / 130 lines | Dentists vertical context | Peer-clinical voice, taboos ("cure", "guaranteed"), service+price catalog, metro benchmarks, JIDA fluoride trial, DCI radiograph dose compliance, seasonal bruxism beats. |
| `magicpin-ai-challenge/dataset/categories/salons.json` | 6,959 bytes / 126 lines | Salons & Beauty vertical context | Warm-practical voice, taboos ("guaranteed glow", "miracle"), service+price catalog, Olaplex/keratin alternatives, wedding season beats, GBP "walk-in available" tag benchmark. |
| `magicpin-ai-challenge/dataset/categories/restaurants.json` | 6,740 bytes / 119 lines | Restaurants & Cafes vertical context | Warm-busy fellow operator voice, taboos ("viral guarantee"), covers/AOV metrics, IPL match day contrarian logic (Saturday home-watch vs weeknight dine-in), thali economics, GST takeaway packaging rules. |
| `magicpin-ai-challenge/dataset/categories/gyms.json` | 7,186 bytes / 126 lines | Gyms & Fitness vertical context | Energetic-disciplined coach voice, taboos ("shred in 7 days"), churn/trial metrics, April-June seasonal acquisition lull reframe, corporate PT demand, ICMR adolescent creatine bulletin. |
| `magicpin-ai-challenge/dataset/categories/pharmacies.json` | 7,529 bytes / 125 lines | Pharmacies vertical context | Trustworthy-precise neighbourhood pharmacist voice, taboos ("miracle cure"), chronic-Rx subscription retention, CDSCO voluntary batch recall on atorvastatin, Schedule H1 audit compliance, summer ORS demand. |

---

## B. Challenge Contract

### 1. High-Level Mission
Participants must build an autonomous messaging engine that powers **Vera** (magicpin's local commerce marketing assistant) communicating with merchants (and customers on behalf of merchants) over WhatsApp. The engine must accept structured contextual data across four dimensions and deterministically generate optimal outbounds and multi-turn responses.

### 2. Core Python Composition Signature
As defined in `challenge-brief.md:198-212` and `challenge-testing-brief.md:7.1`:
```python
def compose(
    category: dict,
    merchant: dict,
    trigger: dict,
    customer: dict | None = None
) -> dict:
    """
    Returns dict with keys:
        body: str              # WhatsApp message text
        cta: str               # "open_ended" | "binary_yes_no" | "multi_choice_slot" | "binary_confirm_cancel" | "none"
        send_as: str           # "vera" (merchant-facing) | "merchant_on_behalf" (customer-facing)
        suppression_key: str   # Deduplication / rate-limiting key
        rationale: str         # Clear reasoning explaining why this message was chosen
    """
```

### 3. Execution & Submission Formats
* **Standalone Execution**: A FastAPI / ASGI HTTP service implementing the 5 required endpoints deployed to a reachable HTTP/HTTPS URL (`challenge-testing-brief.md:31-35`).
* **Offline Deliverables**:
  1. `bot.py`: Standalone module exposing `compose(...)`.
  2. `submission.jsonl`: 30 pre-generated responses corresponding to the 30 canonical test pairs (`test_pairs.json`).
  3. `README.md`: Architectural decisions, tradeoffs, and context insights (max 1 page).
  4. Optional `conversation_handlers.py`: Exposing `respond(state, merchant_message) -> dict` for multi-turn conversations (`challenge-brief.md:293-302`).

### 4. Non-Negotiable Composition Rules (`challenge-brief.md:214-224`, `challenge-testing-brief.md:471-481`, `examples/api-call-examples.md:542-576`)
1. **Verifiable Fact Grounding**: Zero hallucination. Every statistic, metric, price, and citation must be derived directly from the provided contexts. Penalty: -2 per hallucinated fact.
2. **Single Primary CTA**: Exactly one clear call-to-action landing in the closing sentence. Binary choices (YES/STOP, Confirm/Cancel) or low-friction asks. No multi-choice decision fatigue (except designated slot selection in appointment/recall flows).
3. **No External URLs**: `examples/api-call-examples.md:567-571` states: "Hard fail for that action — Meta would reject. Penalty: -3 per URL." Messages must never include raw URLs.
4. **Appropriate Vertical Tone**: Follow `voice.tone` and `voice.vocab_allowed`. Never violate `voice.vocab_taboo`. Clinical/peer for doctors, fellow operator for restaurateurs, coach for gym owners.
5. **Language & Code-Mix Alignment**: Strictly honor `merchant.identity.languages` and `customer.identity.language_pref` (e.g. natural Hinglish code-mix for `"hi-en mix"`, respectful namaste for seniors).
6. **Anti-Repetition**: Never send identical message bodies within the same conversation. Penalty: -2 per repetition.
7. **No Internal Jargon**: Never expose internal system tags or schema names (`suppression_key`, `lapsed_soft`, `churn_pct`, etc.) to the recipient. Penalty: -1.

---

## C. Input Schemas

As documented in `challenge-testing-brief.md:176-263` and `dataset/generate_dataset.py`:

### 1. `CategoryContext` (`scope: "category"`)
```json
{
  "slug": "dentists",
  "display_name": "Dentists",
  "voice": {
    "tone": "peer_clinical",
    "register": "respectful_collegial",
    "code_mix": "hindi_english_natural",
    "vocab_allowed": ["fluoride varnish", "caries", "scaling"],
    "vocab_taboo": ["guaranteed", "100% safe", "completely cure"],
    "salutation_examples": ["Dr. {first_name}", "Doc"],
    "tone_examples": ["Worth a look — JIDA Oct 2026 p.14"]
  },
  "offer_catalog": [
    { "id": "den_001", "title": "Dental Cleaning @ ₹299", "value": "299", "audience": "new_user", "type": "service_at_price" }
  ],
  "peer_stats": {
    "scope": "metro_solo_practices_2026",
    "avg_rating": 4.4,
    "avg_review_count": 62,
    "avg_views_30d": 1820,
    "avg_calls_30d": 12,
    "avg_directions_30d": 38,
    "avg_ctr": 0.030,
    "avg_photos": 9,
    "avg_post_freq_days": 14,
    "retention_6mo_pct": 0.42
  },
  "digest": [
    {
      "id": "d_2026W17_jida_fluoride",
      "kind": "research" | "compliance" | "cde" | "trend" | "tech" | "seasonal" | "alert",
      "title": "3-month fluoride varnish recall...",
      "source": "JIDA Oct 2026, p.14",
      "trial_n": 2100,
      "patient_segment": "high_risk_adults",
      "summary": "...",
      "actionable": "..."
    }
  ],
  "patient_content_library": [
    { "id": "pc_oral_heart", "title": "...", "channel": "whatsapp", "length_seconds": 90, "body": "..." }
  ],
  "seasonal_beats": [
    { "month_range": "Nov-Feb", "note": "exam-stress bruxism spike..." }
  ],
  "trend_signals": [
    { "query": "clear aligners delhi", "delta_yoy": 0.62, "segment_age": "28-45", "skew": "female" }
  ],
  "regulatory_authorities": ["DCI", "IDA"],
  "professional_journals": ["JIDA"]
}
```

### 2. `MerchantContext` (`scope: "merchant"`)
```json
{
  "merchant_id": "m_001_drmeera_dentist_delhi",
  "category_slug": "dentists",
  "identity": {
    "name": "Dr. Meera's Dental Clinic",
    "city": "Delhi",
    "locality": "Lajpat Nagar",
    "place_id": "ChIJ_LAJPATNAGAR_DENTIST_001",
    "verified": true,
    "languages": ["en", "hi"],
    "owner_first_name": "Meera",
    "established_year": 2018
  },
  "subscription": {
    "status": "active" | "expired" | "trial",
    "plan": "Pro" | "Basic" | "Trial",
    "days_remaining": 82,
    "days_since_expiry": null,
    "renewed_at": "2026-02-04"
  },
  "performance": {
    "window_days": 30,
    "views": 2410,
    "calls": 18,
    "directions": 45,
    "ctr": 0.021,
    "leads": 9,
    "delta_7d": { "views_pct": 0.18, "calls_pct": -0.05, "ctr_pct": 0.02 }
  },
  "offers": [
    { "id": "o_meera_001", "title": "Dental Cleaning @ ₹299", "status": "active", "started": "2026-03-01" }
  ],
  "conversation_history": [
    { "ts": "2026-04-24T10:12:00Z", "from": "vera" | "merchant", "body": "...", "engagement": "merchant_replied" | "intent_action" | "merchant_no_reply" }
  ],
  "customer_aggregate": {
    "total_unique_ytd": 540,
    "lapsed_180d_plus": 78,
    "retention_6mo_pct": 0.38,
    "high_risk_adult_count": 124
  },
  "signals": ["stale_posts:22d", "ctr_below_peer_median", "high_risk_adult_cohort"],
  "review_themes": [
    { "theme": "wait_time", "sentiment": "neg" | "pos", "occurrences_30d": 3, "common_quote": "..." }
  ]
}
```

### 3. `CustomerContext` (`scope: "customer"`)
```json
{
  "customer_id": "c_001_priya_for_m001",
  "merchant_id": "m_001_drmeera_dentist_delhi",
  "identity": {
    "name": "Priya",
    "phone_redacted": "<phone>",
    "language_pref": "hi-en mix" | "english" | "hi" | "te-en mix" | "kn-en mix" | "ta-en mix",
    "age_band": "25-35",
    "senior_citizen": false
  },
  "relationship": {
    "first_visit": "2025-11-04",
    "last_visit": "2026-05-12",
    "visits_total": 4,
    "services_received": ["cleaning", "whitening"],
    "lifetime_value": 1696,
    "chronic_conditions": []
  },
  "state": "new" | "active" | "lapsed_soft" | "lapsed_hard" | "churned",
  "preferences": {
    "preferred_slots": "weekday_evening" | "saturday_morning" | "morning_delivery",
    "channel": "whatsapp" | "whatsapp_via_son",
    "reminder_opt_in": true,
    "preferred_stylist": "Priya"
  },
  "consent": {
    "opted_in_at": "2025-11-04",
    "scope": ["recall_reminders", "appointment_reminders"]
  }
}
```

### 4. `TriggerContext` (`scope: "trigger"`)
```json
{
  "id": "trg_001_research_digest_dentists",
  "scope": "merchant" | "customer",
  "kind": "research_digest" | "regulation_change" | "recall_due" | "perf_dip" | "perf_spike" | "renewal_due" | "festival_upcoming" | "wedding_package_followup" | "curious_ask_due" | "winback_eligible" | "ipl_match_today" | "review_theme_emerged" | "milestone_reached" | "active_planning_intent" | "seasonal_perf_dip" | "customer_lapsed_hard" | "trial_followup" | "supply_alert" | "chronic_refill_due" | "category_seasonal" | "gbp_unverified" | "cde_opportunity" | "competitor_opened" | "dormant_with_vera",
  "source": "external" | "internal",
  "merchant_id": "m_001_drmeera_dentist_delhi",
  "customer_id": null,
  "payload": { /* kind-specific payload fields */ },
  "urgency": 1 | 2 | 3 | 4 | 5,
  "suppression_key": "research:dentists:2026-W17",
  "expires_at": "2026-05-03T00:00:00Z"
}
```

---

## D. Output Schemas

### 1. Proactive Send Object (`POST /v1/tick` response item)
Defined in `challenge-testing-brief.md:85-104` and `examples/api-call-examples.md:212-234`:
```json
{
  "conversation_id": "conv_m_001_drmeera_research_W17",
  "merchant_id": "m_001_drmeera_dentist_delhi",
  "customer_id": null,
  "send_as": "vera",
  "trigger_id": "trg_001_research_digest_dentists",
  "template_name": "vera_research_digest_v1",
  "template_params": [
    "Dr. Meera",
    "JIDA Oct issue landed...",
    "Worth a look..."
  ],
  "body": "Dr. Meera, JIDA's Oct issue landed. One item relevant to your high-risk adult patients — 2,100-patient trial showed 3-month fluoride recall cuts caries recurrence 38% better than 6-month. Worth a look (2-min abstract). Want me to pull it + draft a patient-ed WhatsApp you can share? — JIDA Oct 2026 p.14",
  "cta": "open_ended",
  "suppression_key": "research:dentists:2026-W17",
  "rationale": "External research digest with merchant-relevant clinical anchor; merchant is a dentist with high-risk-adult patient cohort"
}
```

### 2. Multi-Turn Synchronous Reply (`POST /v1/reply` response)
Defined in `challenge-testing-brief.md:128-147` and `examples/api-call-examples.md:267-347`:
There are three valid action modes:

#### Mode 1: `action: "send"`
```json
{
  "action": "send",
  "body": "Sending the abstract now (PDF, 2 pages). Patient-ed draft below...\n\nWant me to schedule the post for tomorrow 10am?",
  "cta": "binary_yes_no",
  "rationale": "Honoring both asks in one turn; binary yes/no CTA to lower friction."
}
```

#### Mode 2: `action: "wait"`
```json
{
  "action": "wait",
  "wait_seconds": 14400,
  "rationale": "Detected merchant auto-reply (canned phrasing). Backing off 4 hours."
}
```

#### Mode 3: `action: "end"`
```json
{
  "action": "end",
  "rationale": "Merchant explicitly opted out. Closing conversation and suppressing trigger."
}
```

---

## E. Category Behavior Matrix

Synthesized directly from `dataset/categories/*.json`:

| Category | Voice & Salutation | Taboo Vocabulary | Offer Patterns | Primary Signals & Benchmarks | Key Seasonal Beats & Opportunities | Prohibited / Failure Patterns |
|---|---|---|---|---|---|---|
| **Dentists** | `peer_clinical`, respectful & collegial. Salutation: "Dr. {first_name}" or "Doc". Clinical terms allowed: fluoride varnish, caries, RCT, CAD/CAM. | "guaranteed", "100% safe", "completely cure", "miracle", "best in city", unverified "FDA-approved". | Service+price: "Dental Cleaning @ ₹299", "Teeth Whitening @ ₹1,499", "Annual Family Plan @ ₹4,999". | Peer CTR: 0.030. Avg calls: 12. Retention (6mo): 42%. Signals: high-risk adult cohort, stale posts. | Nov-Feb (exam-stress bruxism +30%), Oct-Dec (wedding whitening peak 2x), Apr-Jun (school holiday pediatric +50%). | Retail promotional hype, ungrounded medical claims, generic discount percentages ("20% off"). |
| **Salons** | `warm_practical`, approachable expert. Salutation: "Hi {first_name}" or "{salon_name} team". Terms: balayage, keratin, hair spa. | "guaranteed glow", "permanent results", "instant transformation", "miracle", "best in city". | Service+price: "Haircut @ ₹99", "Hair Spa @ ₹499", "Bridal Trial @ ₹999", "Mani+Pedi @ ₹599". | Peer CTR: 0.040. Avg calls: 28. Retention (3mo): 55%. Signals: GBP "walk-in available" boosts calls +23%. | Oct-Dec (primary wedding peak 4x), Apr-May (mini-bridal window 15% + summer haircare), Jul-Aug (monsoon anti-frizz). | Over-promising lasting changes, using discount styles instead of service+price, ignoring stylist preferences. |
| **Restaurants** | `warm_busy_practical`, fellow operator. Salutation: "Hi {chef_or_owner_first_name}". Terms: footfall, covers, AOV, RPC, table turnover. | "best food in city", "guaranteed packed house", "miracle marketing", "viral guarantee". | High volume / combos: "Buy 1 Pizza Get 1 Free (Tue-Thu)", "Weekday Lunch Thali @ ₹149", "Match-night Combo @ ₹399". | Peer CTR: 0.025. Avg views: 4800. Avg calls: 38. Retention (30d): 18%. Signals: dine-in vs delivery split. | Mar-Apr (IPL: Saturdays home delivery -12% covers; weeknights dine-in +18%), Oct-Nov (Diwali feasts), Dec (Christmas/NY 3x). | Promoting dine-in offers on Saturday IPL matches; pushing generic % off rather than meal deals/combos. |
| **Gyms** | `energetic_disciplined`, coach to member. Salutation: "Hi {first_name}", "Coach". Terms: PR, 1RM, EMOM, AMRAP, split, BMR, VO2max, HIIT. | "guaranteed weight loss", "shred in 7 days", "miracle transformation", "fastest results". | Low barrier trial: "3 FREE Trial Classes", "First Month @ ₹499", "2x/week PT @ ₹3,499", "Couple Plan @ ₹999/mo". | Peer CTR: 0.045. Monthly churn: 8%. Trial-to-paid: 32%. Signals: off-peak morning (6-8am) capacity at 60%. | Jan (resolution surge 4x), Apr-Jun (seasonal acquisition lull -25% to -35% — pivot to retention), Aug-Oct (pre-wedding). | Guilt-tripping lapsed members, promising rapid transformations, failing to acknowledge seasonal acquisition dips. |
| **Pharmacies** | `trustworthy_precise`, neighbourhood pharmacist. Salutation: "Hi {pharmacist_name}". Terms: OTC, Schedule H1, generic, molecule, MRP. | "miracle cure", "guaranteed result", "100% safe", ungrounded "doctor recommended". | Chronic care & delivery: "Free Home Delivery > ₹499", "Senior Citizen 15% OFF", "Diabetic Care Combo @ ₹999". | Peer CTR: 0.038. Repeat customer: 62%. Delivery share: 35%. WhatsApp chronic refill retention: 88% vs 27% walk-in. | Apr-Jun (summer ORS/sunscreen +40%, cough/cold -60%), Jul-Aug (monsoon anti-fungal), Oct-Nov (post-festival sugar spike). | Speculative medical claims, ignoring Schedule H1 compliance warnings, alarming customers during batch recalls. |

---

## F. Merchant Data Model

Extracted from `dataset/merchants_seed.json` and `dataset/generate_dataset.py:118-165`:

### 1. Core Field Classification
* **Identity**: `merchant_id`, `name`, `city`, `locality`, `place_id`, `verified` (bool), `languages` (e.g. `["en", "hi"]`, `["en", "hi", "mr"]`), `owner_first_name`, `established_year`.
* **Subscription**: `status` (`active`, `expired`, `trial`), `plan` (`Pro`, `Basic`, `Trial`), `days_remaining` (int), `days_since_expiry` (int or null), `renewed_at`.
* **Performance (30-day window + 7-day delta)**:
  * `views`, `calls`, `directions`, `ctr` (float), `leads`.
  * `delta_7d`: `views_pct`, `calls_pct`, `ctr_pct`.
* **Offers**: Array of `{ id, title, status: "active"|"expired", started, ended }`.
* **Conversation History**: Array of `{ ts, from: "vera"|"merchant", body, engagement: "merchant_replied"|"intent_action"|"intent_question"|"intent_planning"|"merchant_no_reply" }`.
* **Customer Aggregate**: Aggregated metrics: `total_unique_ytd`, `lapsed_180d_plus`, `retention_6mo_pct`, `high_risk_adult_count`, `chronic_rx_count`, `total_active_members`, `repeat_customer_pct`, etc.
* **Derived Signals**: Array of string flags, e.g.:
  * `"stale_posts:22d"`, `"ctr_below_peer_median"`, `"high_risk_adult_cohort"`, `"engaged_in_last_48h"`.
  * `"renewal_due_soon:12d"`, `"perf_dip_severe"`, `"unverified_gbp"`, `"winback_eligible"`.
* **Review Themes**: Array of `{ theme, sentiment: "pos"|"neg", occurrences_30d: int, common_quote: str }`.

### 2. Generator Expansion Mechanism (`generate_dataset.py:118-165`)
* Deterministically expands the 10 seed merchants (2 per vertical) to 50 merchants (10 per vertical).
* Generates 8 synthetic merchants per category using `NAME_BANKS` and `LOCALITIES`.
* Generates randomized but realistic performance metrics:
  * `views`: 400 to 6,000.
  * `calls`: 2 to `views // 80`.
  * `ctr`: uniform 0.015 to 0.060.
  * `subscription`: weighted 70% active, 20% expired, 10% trial.
  * `languages`: English and Hindi, plus regional language based on city (Mumbai: `mr`, Chennai: `ta`, Hyderabad: `te`, Bangalore: `kn`).
* Synthetic merchants start with empty offers, conversation history, and review themes, but have full identity, subscription, and performance snapshot.

---

## G. Customer Data Model

Extracted from `dataset/customers_seed.json` and `dataset/generate_dataset.py:167-201`:

### 1. Field Structure
* **Identity**: `customer_id`, `merchant_id`, `name`, `phone_redacted` (`"<phone>"`), `language_pref` (`"hi-en mix"`, `"english"`, `"hi"`, `"te-en mix"`, etc.), `age_band` (`"25-35"`, `"child_under_12"`, `"65-75"`), `senior_citizen` (bool).
* **Relationship**: `first_visit`, `last_visit`, `visits_total`, `services_received` (list of strings), `lifetime_value` (numeric ₹), `chronic_conditions` (e.g. `["diabetes_t2", "hypertension"]`), `favourite_dish`.
* **Lifecycle State**: `"new"` | `"active"` | `"lapsed_soft"` (3-6 mo) | `"lapsed_hard"` (6 mo+) | `"churned"` (12 mo+).
* **Preferences**: `preferred_slots` (`"weekday_evening"`, `"saturday_morning"`, `"morning_delivery"`), `channel` (`"whatsapp"`, `"whatsapp_via_son"`), `reminder_opt_in` (bool), `preferred_stylist`, `training_focus`, `wedding_date`.
* **Consent**: `opted_in_at` (ISO date or null), `scope` (list of permitted topics, e.g. `["recall_reminders", "appointment_reminders"]`, `["promotional_offers"]`).

### 2. Mandatory Restrictions & Outreach Gates
* **Consent Gate**: If `consent.scope` is empty or does not include the topic (or `reminder_opt_in == false`), outreach must be **SUPPRESSED**.
* **Identity/Relationship Personalization**:
  * If `customer.identity.senior_citizen == true`, use respectful salutation ("Namaste", "Sharma ji") and highlight senior discounts.
  * If `customer.preferences.channel == "whatsapp_via_son"`, address the message appropriately for the caregiver.
  * Offer slot options matching `customer.preferences.preferred_slots`.
  * Code-mix matching `customer.identity.language_pref`.

---

## H. Trigger Taxonomy

Synthesized across `dataset/triggers_seed.json`, `dataset/generate_dataset.py:204-245`, and `engagement-design.md:191-203`:

| Trigger Kind | Source & Scope | Required Payload Facts | Action / Message Archetype | Default Urgency | Deduplication Suppression Key Pattern |
|---|---|---|---|---|---|
| `research_digest` | External / Merchant | `category`, `top_item_id` | Announce new clinical/scientific trial findings; offer 2-min abstract + ready WhatsApp patient post. | 2 | `research:{category}:{year}-W{week}` |
| `regulation_change` | External / Merchant | `category`, `top_item_id`, `deadline_iso` | Urgently alert merchant to compliance audit/rule change with action checklist before deadline. | 4 | `compliance:{authority}_{topic}:{year}` |
| `recall_due` | Internal / Customer | `service_due`, `last_service_date`, `due_date`, `available_slots` | Reach out on behalf of merchant offering specific calendar slots + service+price offer. | 3 | `recall:{customer_id}:{window}` |
| `perf_dip` | Internal / Merchant | `metric`, `delta_pct`, `window`, `vs_baseline` | Alert to severe drop in calls/views; diagnose issue and propose corrective action. | 4 | `perf_dip:{merchant_id}:{metric}:{period}` |
| `renewal_due` | Internal / Merchant | `days_remaining`, `plan`, `renewal_amount` | Remind of pending subscription expiration; highlight active benefits at risk. | 4 | `renewal:{merchant_id}:{quarter}` |
| `festival_upcoming` | External / Merchant | `festival`, `date`, `days_until`, `category_relevance` | Guide merchant to prepare festival-specific campaigns, gift boxes, or special hours. | 1 | `festival:{festival}:{year}:{merchant_id}` |
| `wedding_package_followup` | Internal / Customer | `wedding_date`, `trial_completed`, `days_to_wedding`, `next_step_window_open` | Follow up on trial with concrete skin-prep package and block preferred slot. | 2 | `bridal_followup:{customer_id}` |
| `curious_ask_due` | Internal / Merchant | `ask_template`, `last_ask_at` | Low-friction question ("what service was most asked for this week?") offering reciprocity (draft post). | 1 | `curious_ask:{merchant_id}:{week}` |
| `winback_eligible` | Internal / Merchant | `days_since_expiry`, `perf_dip_pct`, `lapsed_customers_added_since_expiry` | Re-engage expired subscriber by quantifying business loss post-expiry. | 2 | `winback:{merchant_id}` |
| `ipl_match_today` | External / Merchant | `match`, `venue`, `city`, `match_time_iso`, `is_weeknight` | Contextual advice: if Saturday, push home-delivery BOGO; if weeknight, push match-night combo. | 3 | `ipl:{merchant_id}:{date}` |
| `review_theme_emerged` | Internal / Merchant | `theme`, `occurrences_30d`, `trend`, `common_quote` | Alert to rising negative review trend (e.g. delivery delays, wait times) or celebrate positive trend. | 3 | `review_theme:{merchant_id}:{theme}:{week}` |
| `milestone_reached` | Internal / Merchant | `metric`, `value_now`, `milestone_value`, `is_imminent` | Congratulate on approaching milestone (e.g. 150 reviews) and suggest push to cross it. | 1 | `milestone:{merchant_id}:{milestone}` |
| `active_planning_intent` | Internal / Merchant | `intent_topic`, `merchant_last_message` | Honor merchant's planning request immediately; draft concrete package, tiers, and outreach copy. | 4 | `planning:{merchant_id}:{topic}:{week}` |
| `seasonal_perf_dip` | Internal / Merchant | `metric`, `delta_pct`, `window`, `is_expected_seasonal`, `season_note` | Pre-empt anxiety: explain normal seasonal lull (e.g. gym April dip), pause ad spend, focus retention. | 1 | `seasonal_dip:{merchant_id}:{quarter}` |
| `customer_lapsed_hard` | Internal / Customer | `days_since_last_visit`, `previous_focus`, `previous_membership_months` | No-shame winback message introducing new tailored class/slot matching previous goal. | 3 | `winback:{customer_id}` |
| `trial_followup` | Internal / Customer | `trial_date`, `next_session_options` | Follow up on trial class/service with concrete next slot option. | 2 | `trial_followup:{customer_id}` |
| `supply_alert` | External / Merchant | `alert_id`, `molecule`, `affected_batches`, `manufacturer` | High-urgency alert to pull affected batches; auto-filter repeat customers for proactive notice. | 5 | `alert:{molecule}:{year_month}` |
| `chronic_refill_due` | Internal / Customer | `molecule_list`, `last_refill`, `stock_runs_out_iso`, `delivery_address_saved` | Respectful reminder that medicine is running out; show items, discount, total, saved delivery. | 3 | `refill:{customer_id}:{year_month}` |
| `category_seasonal` | External / Merchant | `season`, `trends`, `shelf_action_recommended` | Practical merchandising advice for season (e.g. move ORS/sunscreen to front counter). | 2 | `season:{season}:{merchant_id}:{year}` |
| `gbp_unverified` | Internal / Merchant | `verified`, `verification_path`, `estimated_uplift_pct` | Action prompt to complete Google profile verification to unlock 30% visibility uplift. | 3 | `unverified:{merchant_id}` |
| `cde_opportunity` | External / Merchant | `digest_item_id`, `credits`, `fee` | Alert doctor to upcoming accredited webinar/workshop relevant to practice development. | 1 | `cde:{category}:{date}` |
| `competitor_opened` | External / Merchant | `competitor_name`, `distance_km`, `their_offer`, `opened_date` | Notify of competitor opening nearby; recommend counter-positioning on Google listing. | 2 | `competitor:{merchant_id}:{competitor_slug}` |
| `perf_spike` | Internal / Merchant | `metric`, `delta_pct`, `window`, `likely_driver` | Celebrate metric jump (+15% calls) and attribute to recent post/action. | 1 | `perf_spike:{merchant_id}:{metric}:{week}` |
| `dormant_with_vera` | Internal / Merchant | `days_since_last_merchant_message`, `last_topic` | Re-engage inactive merchant with fresh value hook after 14-30 days of silence. | 2 | `dormant:{merchant_id}:{days}d` |

---

## I. API Contract & Testing Interface

Detailed in `challenge-testing-brief.md:31-174` and `examples/api-call-examples.md`:

### 1. Endpoint Specifications

#### `GET /v1/healthz`
* **Purpose**: Liveness probe polled every 60s.
* **Latency Budget**: 2 seconds.
* **Response (200)**:
  ```json
  {
    "status": "ok",
    "uptime_seconds": 124,
    "contexts_loaded": { "category": 5, "merchant": 50, "customer": 200, "trigger": 0 }
  }
  ```
* **Failure Rule**: 3 consecutive non-200 responses disqualifies the bot (`challenge-testing-brief.md:475`).

#### `GET /v1/metadata`
* **Purpose**: Identifies bot version, team name, model, approach.
* **Latency Budget**: 2 seconds.
* **Response (200)**:
  ```json
  {
    "team_name": "Team Name",
    "team_members": ["Alice", "Bob"],
    "model": "deterministic-vera-engine-v1",
    "approach": "hierarchical deterministic rule engine + grounded contextual synthesis",
    "contact_email": "engineer@example.com",
    "version": "1.0.0",
    "submitted_at": "2026-04-26T08:00:00Z"
  }
  ```

#### `POST /v1/context`
* **Purpose**: Ingests new or updated context across all 4 scopes.
* **Latency Budget**: 5 seconds (payload cap 500 KB).
* **Request Schema**:
  ```json
  {
    "scope": "category" | "merchant" | "customer" | "trigger",
    "context_id": "dentists",
    "version": 1,
    "payload": { ... },
    "delivered_at": "2026-04-26T09:45:00Z"
  }
  ```
* **Status & Semantics**:
  * **200 OK**: Stored successfully. Returns `{"accepted": true, "ack_id": "ack_dentists_v1", "stored_at": "..."}`.
  * **409 Conflict**: Re-post of equal or lower version. Returns `{"accepted": false, "reason": "stale_version", "current_version": 1}`.
  * **400 Bad Request**: Malformed scope or missing mandatory payload fields.

#### `POST /v1/tick`
* **Purpose**: Periodic wake-up (every 5 simulated minutes). Bot decides proactive outbound sends.
* **Latency Budget**: 10–15 seconds (hard judge timeout 30s). Cap: 20 actions per tick.
* **Request Schema**:
  ```json
  {
    "now": "2026-04-26T10:35:00Z",
    "available_triggers": ["trg_001_research_digest_dentists", "trg_003_recall_due_priya"]
  }
  ```
* **Response (200)**:
  ```json
  {
    "actions": [
      {
        "conversation_id": "conv_m_001_drmeera_research_W17",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": null,
        "send_as": "vera",
        "trigger_id": "trg_001_research_digest_dentists",
        "template_name": "vera_research_digest_v1",
        "template_params": ["Dr. Meera", "...", "..."],
        "body": "...",
        "cta": "open_ended",
        "suppression_key": "research:dentists:2026-W17",
        "rationale": "..."
      }
    ]
  }
  ```
* **Empty Actions**: `{"actions": []}` is valid and rewarded when outreach is not justified.

#### `POST /v1/reply`
* **Purpose**: Synchronous handling of merchant or customer replies.
* **Latency Budget**: 10–15 seconds (hard judge timeout 30s).
* **Request Schema**:
  ```json
  {
    "conversation_id": "conv_m_001_drmeera_research_W17",
    "merchant_id": "m_001_drmeera_dentist_delhi",
    "customer_id": null,
    "from_role": "merchant" | "customer",
    "message": "Yes please send the abstract",
    "received_at": "2026-04-26T10:42:00Z",
    "turn_number": 2
  }
  ```
* **Response (200)**:
  * `action: "send"` with `body`, `cta`, `rationale`.
  * `action: "wait"` with `wait_seconds`, `rationale`.
  * `action: "end"` with `rationale`.

---

## J. Judge Behavior & Evaluation Mechanisms

Directly reverse-engineered from `judge_simulator.py`:

### 1. Judge Lifecycle Phases
1. **Warmup (`_warmup`)**: Calls `/healthz` and `/metadata`. Pushes 5 categories and top 5 merchants. Verifies responses.
2. **Phase 2 Test Window (`_phase2_short` / `_full`)**:
   * Pushes triggers.
   * Calls `/tick` with batches of active trigger IDs.
   * Inspects returned actions and routes them to the LLM scoring engine.
3. **Phase 4 Replay Scenarios**:
   * **Auto-reply Hell (`_auto_reply`)**: Sends identical canned text 4 times: `"Thank you for contacting us! Our team will respond shortly."`
     * Pass: Bot returns `action: "end"` or `action: "wait"`.
     * Fail: Bot continues sending promotional chatter across all 4 turns.
   * **Intent Transition (`_intent`)**: Merchant says: `"Ok lets do it. Whats next?"`
     * Pass: Action mode body contains action words (`"done"`, `"sending"`, `"draft"`, `"here"`, `"confirm"`, `"proceed"`, `"next"`) and **ZERO** qualifying words (`"would you"`, `"do you"`, `"can you tell"`, `"what if"`, `"how about"`).
     * Fail: Bot asks another qualifying question instead of taking action.
   * **Hostile / Opt-out (`_hostile`)**: Merchant says: `"Stop messaging me. This is useless spam."`
     * Pass: Bot returns `action: "end"` immediately OR sends a polite single-line apology (`"sorry"`, `"apolog"`, `"won't"`).
     * Fail: Bot ignores hostility or argues.

### 2. The LLM Scoring Prompt (`judge_simulator.py:443-492`)
The simulator feeds the LLM judge:
* **Context Provided to Bot**: Category slug, tone, taboos; Merchant identity (name, owner, locality, languages), performance metrics, active signals, active offers; Trigger kind, payload, urgency; Customer identity (if present).
* **Bot's Message**: Body text, character length, CTA, Send As identity.
* **Scoring Instructions**: Score each dimension 0 to 10 strictly.
* **Penalties**:
  * Fabricating data not in context: **-2**.
  * Exposing internal jargon to merchant: **-1**.
  * URL in body (`examples/api-call-examples.md:570`): **-3**.
  * Repetition: **-2**.

---

## K. Case Study Insights (10 Scored Anchors)

Analyzing all 10 anchors from `examples/case-studies.md`:

| Case | Domain & Scope | Trigger & Context | Winning Strategy | Why It Scored High | Fragility / Common Weakness |
|---|---|---|---|---|---|
| **CS 1** (50/50) | Dentists / Merchant | `research_digest`: JIDA Oct fluoride paper. | Clinical anchor, exact trial N (2,100), 38% caries cut, page citation, low-friction draft offer. | Concrete numbers, exact source citation, peer-clinical tone, matches merchant's high-risk patient cohort. | Omitting the page citation (caps score at 7) or using consumer marketing language. |
| **CS 2** (49/50) | Dentists / Customer | `recall_due`: Priya 6-month cleaning. | Send as `merchant_on_behalf`, exact catalog price (₹299), 2 weekday evening slots matching preference, dental emoji. | Respects patient's language mix, exact dates/slots, no overclaims. | Multi-choice CTA (1 for Wed, 2 for Thu) lost 1 point on compulsion; rescued by open fallback. |
| **CS 3** (47/50) | Salons / Customer | `wedding_package_followup`: Kavya bridal trial. | Exact days to wedding (196), 30-day skin-prep package, specific slot (Sat 4pm), ₹2,499 price. | Continuity with past trial, urgency framing without panic, owner first name used. | Lost points if the package price is not in catalog; must stay grounded in actual offers. |
| **CS 4** (44/50) | Salons / Merchant | `curious_ask_due`: weekly demand check. | Low-stakes question ("what service was most asked for?"), upfront reciprocity (will turn into GBP post). | Effort externalization (5 min), respects merchant time, fellow-operator tone. | Lacked concrete guessing of the service; generic ask scored 8 on specificity. |
| **CS 5** (50/50) | Restaurants / Merchant | `ipl_match_today`: Saturday match at Arun Jaitley. | Contrarian intelligence: Saturday matches cause -12% dine-in covers; advise skipping dine-in promo and pushing delivery BOGO. | **Value beyond trigger**: Correctly interprets Saturday vs weeknight IPL dynamics; prevents merchant from a costly mistake. | Naively offering a match-night dine-in discount when data says covers drop on Saturdays. |
| **CS 6** (49/50) | Restaurants / Merchant | `active_planning_intent`: Suresh corporate thali. | Immediate complete drafted menu: tiered pricing (10@₹125, 25@₹115, 50+@₹105), named nearby office parks. | Zero back-and-forth; delivers ready artifact; operator language. | Assuming office park names if not in context risks a fabrication penalty. |
| **CS 7** (48/50) | Gyms / Merchant | `seasonal_perf_dip`: April-June 30% drop. | Pre-empt anxiety: explain metro April lull (-25% to -35%), advise pausing ad spend and running retention challenge. | Reframe problem as opportunity; references exact member count (245) and specific drop. | Vague savings advice ("save for Sept-Oct") scored 8 on compulsion; needed exact savings figures. |
| **CS 8** (50/50) | Gyms / Customer | `customer_lapsed_hard`: Rashmi 57d lapse. | Warm coach tone, "no judgment", ties new HIIT class to her weight loss goal, free trial next Tue. | Dual objection killer: "no judgment" + "no commitment, no auto-charge". Single binary YES CTA. | Guilt-tripping or pushing aggressive long-term memberships immediately. |
| **CS 9** (50/50) | Pharmacies / Merchant | `supply_alert`: Atorvastatin voluntary batch recall. | Urgent compliance notice, exact batch numbers, bounded risk ("sub-potency, no safety risk"), affected count (22). | Pulls count from customer aggregate; provides ready workflow (note + replacement). | Panicking the merchant or failing to compute the affected patient subset. |
| **CS 10** (49/50) | Pharmacies / Customer | `chronic_refill_due`: Mr. Sharma medicines. | Respectful Namaste, exact molecule names, 15% senior discount calculated (₹1,420, ₹240 saved), free home delivery. | Honored channel (`whatsapp_via_son`), full precision on molecules, clear savings. | Missing molecule names or failing to apply senior citizen discount. |

---

## L. Five-Dimensional Scoring Strategy

Based on `challenge-brief.md:308-318` and `judge_simulator.py:445-492`:

### 1. Specificity (Weight: 10/50)
* **10/10**: Anchored on multiple verifiable facts directly from context: exact numbers (percentages, prices, participant counts), specific calendar dates/times, exact source citations (publication name, issue, page number), or specific batch numbers.
* **5/10**: Vague assertions ("recently", "many customers", "good discount"), generic pricing ("flat 10% off"), ungrounded claims.
* **0/10**: Total abstraction with zero numbers, dates, or verifiable references.

### 2. Category Fit (Weight: 10/50)
* **10/10**: Flawless alignment with `voice.tone` and `voice.register`. Employs domain terms (`voice.vocab_allowed`) naturally. Strictly obeys `voice.vocab_taboo`. Clinical/peer for dentists, fellow operator for restaurants, coach for gyms, pharmacist for chemists.
* **5/10**: Generic retail marketing voice applied to professional domains (e.g. "Amazing dental cleaning offer!").
* **0/10**: Blatant taboo violations ("guaranteed 100% cure", "permanent transformation", "shred in 7 days").

### 3. Merchant Fit (Weight: 10/50)
* **10/10**: Personalized to this specific merchant: greets owner by first name (`identity.owner_first_name`), references their actual active catalog offers (`merchant.offers`), honors locality and language code-mix, and leverages their actual performance/aggregate stats without hallucination.
* **5/10**: Generic "Hi merchant", fails to use available owner name, overlooks existing active catalog offers.
* **0/10**: Attributes offers or performance metrics that belong to a different business or completely fabricates numbers.

### 4. Decision Quality / Trigger Relevance (Weight: 10/50)
* **10/10**: Crystal-clear "why now". Directly addresses the trigger event using the trigger payload data. Demonstrates operator judgment (e.g. contrarian Saturday IPL logic or seasonal dip reframe).
* **5/10**: Generic profile nudge that mentions the trigger in passing without altering the core proposal.
* **0/10**: Complete disconnect between trigger payload and proposed action.

### 5. Engagement Compulsion (Weight: 10/50)
* **10/10**: Powerful psychological compulsion: externalizes effort ("I've drafted it — just say go in 10 min"), applies loss aversion, social proof, or respectful curiosity. Ends with a single, frictionless binary CTA (YES/STOP, Confirm/Cancel) placed in the final sentence.
* **5/10**: Open-ended question requiring high merchant mental effort; buried call-to-action in middle of body.
* **0/10**: Multiple conflicting CTAs, aggressive sales pressure, or dead-end message with no response path.

---

## M. Suppression Requirements

Outreach suppression is an essential quality gate. Sending irrelevant or unauthorized messages severely penalizes the bot.

### 1. Mandatory Suppression Conditions
1. **Consent Missing or Revoked**: If customer `consent.opted_in_at` is null, `reminder_opt_in == false`, or trigger topic is outside `consent.scope`, the send **must be suppressed**.
2. **Duplicate Triggers / Active Dedup Key**: If a message with the same `suppression_key` was already dispatched and has not expired, suppress.
3. **Expired Triggers**: If `now > trigger.expires_at`, suppress immediately.
4. **Active Merchant Hostility / Opt-Out**: If merchant conversation history reflects `"Not interested. Stop messaging"`, suppress all marketing outreach for that merchant.
5. **Auto-Reply Loop**: If the merchant replies with an automated assistant message (e.g. "Thank you for contacting..."), suppress further immediate sends and enter a backoff state (`action: "wait"` or `action: "end"`).
6. **No Actionable Context**: If the trigger requires active catalog offers but `merchant.offers` is empty (and no standard category default applies), suppress rather than inventing an offer.
7. **Rate Limiting**: Maximum 1 proactive action per `(merchant_id, conversation_id)` per tick. Cap of 20 total actions per tick.

---

## N. State-Management Requirements

The bot must maintain state across sequential HTTP requests without data corruption (`challenge-testing-brief.md:27-28, 50-54`).

### 1. Context Store Semantics (`/v1/context`)
* **Atomic Version Replacement**: When `POST /v1/context` is received for an existing `(scope, context_id)`, if `new_version > current_version`, the stored context is replaced atomically.
* **Idempotency**: If `new_version <= current_version`, reject with HTTP 409 Conflict (`stale_version`) or treat as idempotent no-op.
* **Cross-Tick Persistence**: Memory must persist for the entire test duration (~60 simulated minutes).

### 2. Conversation State Semantics (`/v1/reply`)
* Must track conversation turns by `conversation_id`:
  * Turn counter (`turn_number`).
  * Message history (`from_role`, `message`, `ts`).
  * Detected merchant posture: `qualifying`, `committed_to_action`, `hostile`, `auto_reply_detected`.
  * Consecutive auto-reply count (to escalate from warning → wait → end).
* Graceful termination: Once a conversation transitions to `end`, no subsequent turns should occur on that `conversation_id`.

---

## O. Determinism Requirements

The challenge explicitly requires: **“Must be deterministic given the same inputs”** (`challenge-brief.md:277`).

### 1. Sources of Nondeterminism to Eliminate
* Random dictionary iteration order or set ordering.
* Unseeded random selections or template samplers.
* Floating-point discrepancies in candidate scoring.
* LLM temperature > 0 (or relying on LLMs for deterministic selection logic).
* Wall-clock system timestamps (`datetime.utcnow()`) during message composition; must use `now` passed in `/v1/tick` or payload `delivered_at`.

### 2. Deterministic Guarantee Contract
Given identical:
`(category_slug, category_version) + (merchant_id, merchant_version) + (trigger_id, trigger_version) + (customer_id, customer_version) + conversation_history`
The engine must produce the **exact same message body, CTA, send_as, suppression_key, and rationale**.

---

## P. Failure-Mode Catalogue

Synthesized list of fatal traps that ruin score or cause disqualification:

| Failure Mode | Trigger Scenario | Consequence | Prevention Mechanism |
|---|---|---|---|
| **Hallucinated Citations** | Research trigger where paper is missing page/volume. | Score capped at 5/10; -2 penalty. | Strict fallback to exact context string; never extrapolate beyond digest record. |
| **URL Emission** | Including a link in WhatsApp body (`https://...`). | Meta rejection simulation; -3 penalty. | Regex sanitizer stripping/blocking all URLs in message body. |
| **Auto-Reply Loop** | WhatsApp Business auto-responder loops 4 turns. | Disqualification / zero score on replay test. | Exact string matching + regex pattern detection on canned responses ("Thank you for contacting", "automated assistant") triggering immediate backoff. |
| **Stuck in Qualifying Mode** | Merchant says "Yes let's do it". | Fatal failure on `intent_transition` replay scenario. | Intent detector intercepting commitment keywords and strictly executing action without questions. |
| **Taboo Vocabulary Leaks** | Emitting "guaranteed" or "100% cure" for a dentist. | Category fit drops to 0/10. | Category-specific taboo filter rejecting or rewriting forbidden words before dispatch. |
| **Stale Context Persistence** | Version 2 of merchant performance arrives mid-test, but bot uses Version 1. | Adaptation bonus lost; scored as stale composition. | Dynamic pointer resolution: tick and compose always fetch latest version from context store. |
| **Multiple Conflicting CTAs** | "Reply 1 for X, 2 for Y, or call Z". | Engagement compulsion penalized. | Single CTA enforcement: choose binary action or single-slot commit. |
| **Internal Jargon Bleed** | Outputting "lapsed_soft" or "suppression_key". | -1 penalty per message. | Output schema validation ensuring internal keys never appear in `body`. |
| **Timeout on `/v1/tick`** | Processing exceeds 30s timeout. | -1 penalty per timeout; tick actions dropped. | Microsecond deterministic composition engine (<5ms per action); no heavy synchronous LLM bottlenecks. |

---

## Q. Proposed Architecture (High-Level Design)

A lightweight, purely deterministic, zero-dependency/minimal-dependency architecture (FastAPI + Pydantic + pure Python standard library):

```
┌────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Web Layer                             │
│       GET /v1/healthz  |  GET /v1/metadata  |  POST /v1/context        │
│       POST /v1/tick    |  POST /v1/reply                               │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        In-Memory Context Store                         │
│  - Categories [slug -> (version, payload)]                             │
│  - Merchants  [id   -> (version, payload)]                             │
│  - Customers  [id   -> (version, payload)]                             │
│  - Triggers   [id   -> (version, payload)]                             │
│  - Conversations [conv_id -> state & history]                          │
│  - Active Suppressions [suppression_key -> expiry]                     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     Deterministic Vera Engine                          │
│                                                                        │
│  ┌──────────────────────┐               ┌───────────────────────────┐  │
│  │   Suppression Gate   │               │   Intent & Role Router    │  │
│  │  - Consent check     │               │  - Auto-reply classifier  │  │
│  │  - Expiry check      │               │  - Hostile classifier     │  │
│  │  - Dedup check       │               │  - Commitment classifier  │  │
│  └──────────┬───────────┘               └─────────────┬─────────────┘  │
│             │                                         │                │
│             ▼                                         ▼                │
│  ┌──────────────────────┐               ┌───────────────────────────┐  │
│  │   Signal Extractor   │               │    Grounded Fact Binder   │  │
│  │  - Perf metrics      │               │  - Exact context tokens   │  │
│  │  - Category voice    │               │  - Catalog prices/offers  │  │
│  │  - Customer prefs    │               │  - Real dates & slots     │  │
│  └──────────┬───────────┘               └─────────────┬─────────────┘  │
│             │                                         │                │
│             └───────────────────┬─────────────────────┘                │
│                                 │                                      │
│                                 ▼                                      │
│                 ┌───────────────────────────────┐                      │
│                 │   Deterministic Rule Matrix   │                      │
│                 │   (Category x Trigger Kind)   │                      │
│                 └───────────────┬───────────────┘                      │
│                                 │                                      │
│                                 ▼                                      │
│                 ┌───────────────────────────────┐                      │
│                 │   Output Validator & Filter   │                      │
│                 │  - Taboo scanner              │                      │
│                 │  - URL blocker                │                      │
│                 │  - CTA formatter              │                      │
│                 └───────────────────────────────┘                      │
└────────────────────────────────────────────────────────────────────────┘
```

### Components
1. **ContextStore**: Thread-safe in-memory key-version store tracking contexts and idempotency.
2. **SuppressionEngine**: Evaluates consent, dedup keys, expiration, and merchant opt-out status.
3. **ConversationStateManager**: Tracks turn history, detects auto-replies and merchant intent shifts.
4. **FactBinder**: Extracts and verifies real figures (prices, dates, names, research citations) without invention.
5. **CategoryComposerMatrix**: Rule-based template synthesizers organized by vertical (`dentists`, `salons`, `restaurants`, `gyms`, `pharmacies`) and trigger kind.
6. **SafetyValidator**: Enforces URL stripping, taboo word elimination, character checks, and CTA positioning.

---

## R. Proposed Decision Pipeline

```
1. INGESTION & VALIDATION
   ├── Validate context schema & version
   └── Idempotently store or reject stale version

2. TICK TRIGGER SELECTION (/v1/tick)
   ├── Filter available_triggers against active stored triggers
   ├── Filter out expired triggers (now > expires_at)
   └── Filter out suppressed triggers (active suppression_key in store)

3. CONTEXT RESOLUTION
   ├── Resolve Target Merchant (payload.merchant_id)
   ├── Resolve Category Context (merchant.category_slug)
   └── Resolve Customer Context (if trigger.scope == 'customer')

4. ELIGIBILITY & GATING
   ├── Verify customer consent scope (if customer scope)
   ├── Check merchant conversation history for opt-out/hostility
   └── Rank eligible triggers by urgency (1 to 5)

5. FACT BINDING & GROUNDING
   ├── Extract verified facts from Trigger payload
   ├── Extract verified stats from Merchant performance snapshot
   ├── Match active offer from Merchant catalog (or Category catalog default)
   └── Resolve recipient salutation & language preference

6. SYNTHESIS & COMPOSITION
   ├── Dispatch to (Category x Trigger Kind) synthesizer
   ├── Construct body with exact grounded facts & citations
   ├── Attach single primary CTA in concluding sentence
   ├── Determine send_as ('vera' vs 'merchant_on_behalf')
   └── Formulate clear rationale matching decision logic

7. SAFETY & QUALITY AUDIT
   ├── Verify ZERO URLs in body
   ├── Verify ZERO taboo words in body
   ├── Verify ZERO internal jargon leaks
   └── Confirm body length and readability

8. STATE PERSISTENCE & DISPATCH
   ├── Record suppression key with expiration
   ├── Initialize conversation_id in store
   └── Return actions payload
```

---

## S. Open Questions & Ambiguities

1. **URL Policy Ambiguity**:
   * `challenge-brief.md:219` states: *"URLs — allowed when they add clear value to the merchant."*
   * But `examples/api-call-examples.md:567-571` states: *"Example F.4 — URL in body: { "body": "Read more: https://magicpin.com/blog" } -> Hard fail for that action — Meta would reject. Penalty: -3 per URL."*
   * **Resolution for implementation**: Follow the strict rule. **Never emit URLs** in the message body.

2. **`decision_quality` vs `trigger_relevance` in Scorer Schema**:
   * `challenge-brief.md:311-317` names the 4th dimension **"Trigger relevance"**.
   * `judge_simulator.py:487, 555` uses **`decision_quality`** while falling back to `trigger_relevance`:
     `data.get("decision_quality", data.get("trigger_relevance", 5))`.
   * **Resolution for implementation**: Both terms refer to the same underlying dimension: connecting *why now* to the specific trigger payload and executing a smart business decision.

3. **Multi-turn Continuation Scope**:
   * While the test window primarily evaluates 1st-turn proactive sends from `/v1/tick`, the top 10 replay scenarios specifically test up to 5 turns of conversation flow on auto-reply, intent transition, and hostile messages.
   * **Resolution for implementation**: The `/v1/reply` endpoint must be fully intelligent and stateful from day 1, handling intent handoffs and auto-replies robustly.
