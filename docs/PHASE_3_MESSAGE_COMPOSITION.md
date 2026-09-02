# Phase 3 — Vera Grounded Message Composition

## 1. Architecture

Phase 3 implements Vera's deterministic, grounded **Message Composer**.
Its contract is strictly downstream of Phase 2:
> **Phase 2 decides WHAT Vera should do. Phase 3 decides HOW to express that decision.**

```text
Decision (from Phase 2 decide())
          ↓
Enforce Decision Authority (never re-score, never change action)
          ↓
Select Deterministic Template (app/composer/templates.py)
          ↓
Extract Grounded Components (app/composer/renderer.py)
          ↓
Render Message Body, Single CTA, Send-As, Suppression Key
          ↓
Strict Validation Pipeline (app/composer/validators.py)
          ↓
ComposedMessage (app/composer/message.py)
```

```text
app/composer/
├── __init__.py          # Package exports (compose, ComposedMessage)
├── message.py           # Typed ComposedMessage model with dictionary serialization
├── templates.py         # 18 deterministic category-aware template definitions
├── renderer.py          # Fact-to-template component renderer & key builder
├── validators.py        # Strict validators (URLs, taboos, privacy, CTAs, offers)
└── compose.py           # Master orchestration entrypoint
```

---

## 2. Input & Output Contract

### Function Signature:
```python
def compose(
    decision: Decision,
    category: Union[CategoryProfile, Dict[str, Any]],
    merchant: Union[MerchantState, Dict[str, Any]],
    trigger: Union[TriggerState, Dict[str, Any]],
    customer: Optional[Union[CustomerStateModel, Dict[str, Any]]] = None,
    state: Optional[Dict[str, Any]] = None,
) -> ComposedMessage:
```

### Output Model (`ComposedMessage`):
```json
{
  "action": "send" | "wait" | "end",
  "action_type": "use_research_insight",
  "target_scope": "merchant" | "customer",
  "send_as": "vera" | "merchant_on_behalf",
  "body": "The rendered grounded text message...",
  "message": "Alias for body",
  "cta": "binary_yes_no" | "multi_choice_slot" | "binary_confirm" | "open_ended" | "none",
  "suppression_key": "research:dentists:d_2026W17_jida_fluoride",
  "rationale": "Internal audit explanation citing grounded evidence count",
  "conversation_id": "conv_m_001_drmeera_research_digest",
  "merchant_id": "m_001_drmeera_dentist_delhi",
  "customer_id": null,
  "trigger_id": "trg_001_research_digest_dentists",
  "template_name": "vera_research_digest_v1",
  "template_params": ["Dr. Meera", "JIDA", "..."]
}
```

---

## 3. Template Architecture & Action Mapping

Every action maps to a deterministic template with explicit parameter slots:

| ActionType | Template Name | Target Scope | Send-As | Primary CTA |
|---|---|---|---|---|
| `USE_RESEARCH_INSIGHT` | `vera_research_digest_v1` | merchant | `vera` | `binary_yes_no` |
| `CUSTOMER_RECALL` | `customer_recall_reminder_v1` | customer | `merchant_on_behalf`| `multi_choice_slot` |
| `CUSTOMER_FOLLOWUP` | `customer_service_followup_v1` | customer | `merchant_on_behalf`| `binary_yes_no` |
| `CURIOUS_ASK` | `vera_curious_ask_v1` | merchant | `vera` | `open_ended` |
| `PROMOTE_DELIVERY_OFFER`| `vera_contrarian_delivery_promo_v1`| merchant | `vera` | `binary_yes_no` |
| `CONTINUE_PLANNING` | `vera_continue_planning_v1` | merchant | `vera` | `binary_yes_no` |
| `REFRAME_SEASONAL_DIP` | `vera_reframe_seasonal_dip_v1` | merchant | `vera` | `binary_yes_no` |
| `CUSTOMER_WINBACK` | `customer_winback_reengagement_v1`| customer | `merchant_on_behalf`| `binary_yes_no` |
| `ADDRESS_SUPPLY_ALERT` | `vera_supply_recall_alert_v1` | merchant | `vera` | `binary_yes_no` |
| `CUSTOMER_REFILL` | `customer_chronic_refill_v1` | customer | `merchant_on_behalf`| `binary_confirm` |
| `ADDRESS_PERFORMANCE_DIP`| `vera_remediate_performance_dip_v1`| merchant | `vera` | `binary_yes_no` |
| `CAPITALIZE_PERF_SPIKE`| `vera_capitalize_perf_spike_v1` | merchant | `vera` | `binary_yes_no` |
| `RENEW_SUBSCRIPTION` | `vera_subscription_renewal_v1` | merchant | `vera` | `binary_yes_no` |
| `RESOLVE_LISTING_ISSUE`| `vera_resolve_listing_v1` | merchant | `vera` | `binary_yes_no` |
| `ADDRESS_COMPETITOR_CHANGE`| `vera_competitor_opened_v1` | merchant | `vera` | `binary_yes_no` |
| `RESPOND_TO_REVIEW_THEME`| `vera_review_theme_response_v1` | merchant | `vera` | `binary_yes_no` |
| `CELEBRATE_MILESTONE` | `vera_celebrate_milestone_v1` | merchant | `vera` | `binary_yes_no` |
| `PREPARE_FESTIVAL_CAMPAIGN`| `vera_festival_campaign_v1` | merchant | `vera` | `binary_yes_no` |
| `WAIT` | `noop_wait_v1` | any | `vera` | `none` |
| `END` | `noop_end_v1` | any | `vera` | `none` |

---

## 4. Category-Specific Guidelines

- **Dentists**: Clinical, peer-to-peer register ("Dr. Meera"). Technical terminology welcomed ("caries", "fluoride recall"); legal taboos strictly barred ("guaranteed", "100% safe", "cure").
- **Salons**: Warm, practical, relationship-driven voice ("Lakshmi from Studio11 Kapra here 💍"). Wedding dates, trial continuity, and explicit slot preferences honored.
- **Restaurants**: Operator-to-operator vocabulary ("covers", "match-night", "delivery radius"). Contrarian weekend IPL insight (-12% covers) leveraged with active delivery offers.
- **Gyms**: Coaching, motivational, no-shame framing ("happens to most members, zero judgment"). Expected seasonal drops reframed to retention over ad spend.
- **Pharmacies**: Trustworthy, precise, regulatory compliance. Exact batch numbers, sub-potency distinction without panic, and exact medication molecule lists.

---

## 5. Grounding & Prohibited Claims Rules

1. **Strict Provenance**: Every number (e.g. `2,100`, `38%`, `22 of 240`, `245`, `-12%`) originates from the input facts, merchant customer aggregate, or trigger payload.
2. **Zero Fabricated Offers**: Only active offers belonging to the merchant (`supporting_offer.status == "active"`) can be cited. Category catalog templates (`category.offer_catalog`) are never cited as active merchant offers.
3. **Strict Taboo Prohibition**: The validator mechanically scans for vertical taboo words (`category.voice.vocab_taboo`) and rejects compositions containing them.

---

## 6. URL & Privacy Policies

1. **Strict No-URL Policy**: In compliance with Meta WhatsApp Business rules and challenge penalty rubric (-3 per URL), raw URLs (`http://`, `https://`, `www.`, shorteners) are completely barred from message bodies. `validate_no_urls()` enforces this mechanically.
2. **Customer & Merchant Privacy**: Internal database identifiers (`c_001...`, `m_001...`, `trg_001...`) are strictly prohibited from appearing in user-facing message text. `validate_customer_privacy()` enforces this.

---

## 7. CTA & Send-As Policy

- **One Primary CTA**: Every actionable message has exactly one low-friction ask (`binary_yes_no`, `multi_choice_slot`, `binary_confirm`, `open_ended`). Competing multi-asks are barred.
- **Send-As Alignment**:
  - `target_scope == "customer"` $\to$ `send_as = "merchant_on_behalf"` (sent from merchant's WhatsApp number).
  - `target_scope == "merchant"` $\to$ `send_as = "vera"` (sent from Vera's assistant identity).

---

## 8. WAIT & END Semantics

When Phase 2 emits `WAIT` or `END`:
- `action`: `"wait"` or `"end"`
- `body`: `""` (empty string; zero outbound spam)
- `cta`: `"none"`
- `suppression_key`: `"wait:{trigger_id}"` or `"end:{trigger_id}"`
- `rationale`: Reflects Phase 2 policy reason (e.g. "Standing down based on Phase 2 safety/consent policy").

---

## 9. Determinism Guarantees

The composer is 100% pure and deterministic:
- Zero `random` calls.
- Zero `datetime.now()` calls.
- Zero network I/O or LLM completions.
- Verified across 100 consecutive runs in `test_100_runs_composer_determinism`: serialized dictionaries and SHA-256 fingerprints are bit-for-bit identical.

---

## 10. Test Results Summary

All 88 tests in the repository pass:
- Canonical Case Study Compositions: 10/10 PASS
- Factual Grounding Tests: 4/4 PASS
- Adversarial Composer Tests: 8/8 PASS
- 100-Run Determinism Benchmark: PASS
- Full Suite Runtime: 1.43s
