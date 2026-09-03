# Vera AI Engine — Autonomous Merchant Engagement System

> **Challenge Submission**: Magicpin AI Challenge  
> **Team**: Team Antigravity  
> **Model Identifier**: `deterministic-engine-v1`  
> **Architecture**: Grounded Deterministic Decision Engine + Category-Aware Outreach & Conversational Protocol

---

## 1. Overview

Vera is an autonomous, deterministic AI merchant engagement engine designed for local commerce verticals (Dentists, Salons, Restaurants, Gyms, Pharmacies).

Vera answers three core operational questions with strict architectural separation of concerns:
1. **WHAT should Vera do?** — **Phase 2 Decision Engine** evaluates normalized domain signals against category rules to select the single best action candidate.
2. **HOW should Vera say it?** — **Phase 3 Grounded Composer** renders concise, professional, tone-aligned messages with zero hallucinated facts, prices, dates, or URLs.
3. **SHOULD Vera transmit it now?** — **Phase 5 Outreach Governance** enforces exact duplicate suppression and customer consent compliance.
4. **HOW does Vera converse?** — **Phase 6 & 7 Reply Intelligence** classifies merchant/customer intent with absolute hostile precedence, prevents acknowledgement loops, handles auto-replies gracefully, and executes Phase 3 continuation workflows without emitting ungrounded prose.

---

## 2. High-Level Architecture

```text
               Inbound Context / Triggers / Inbound Replies
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│ Phase 1: Normalized Domain Model & Context Store                  │
│ Typed Pydantic schemas, thread-safe versioning, tenant isolation  │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│ Phase 2: Deterministic Decision Engine                            │
│ Signal extraction → Candidate generation → Multi-criteria scoring │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│ Phase 3: Grounded Message Composer                                │
│ Category voice governance, strictly verified fact interpolation  │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│ Phase 5: Outreach Governance & Suppression                        │
│ (tenant_key, suppression_key) exact deduplication & consent check │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│ Phase 6 & 7: Conversational State Machine & Reply Protocol        │
│ Intent classification, loop defense, auto-reply backoff, standdown│
└─────────────────────────────────┬─────────────────────────────────┘
                                  │
                                  ▼
                     HTTP 200 JSON Response
```

---

## 3. Quickstart & Installation

### Prerequisites
- Python 3.10+ (Tested on Python 3.11 and Python 3.14)
- Git

### Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 4. Running Locally

Start the production FastAPI server on `0.0.0.0:8080`:

```bash
uvicorn bot:app --host 0.0.0.0 --port 8080
```
Or directly:
```bash
python bot.py
```

The server binds to port 8080 and exposes all required `/v1/*` challenge endpoints.

---

## 5. Running the Test Suite

Run the complete test suite (265 unit, integration, isolation, and adversarial tests):

```bash
pytest -q
```
*Expected output*: `265 passed in ~5s`

---

## 6. Running the Official Judge Simulator

With the server running on `http://localhost:8080`:

```bash
python magicpin-ai-challenge/judge_simulator.py
```

### Supported Scenarios:
- **Warmup**: Health checks, metadata verification, category/merchant context pushes.
- **Auto-Reply Hell**: Verifies 14400s WAIT backoff on canned automated replies.
- **Intent Transition**: Verifies transition to ACTION mode and grounded continuation on merchant commitment.
- **Hostile Handling**: Verifies immediate graceful exit and state closure on opt-out.

*Expected output*: `ALL PASSED (100%)`

---

## 7. API Specification

### `GET /v1/healthz`
Liveness probe returning server status, uptime, and context counts.
- **Status**: 200 OK
- **Response**: `{"status": "ok", "uptime_seconds": 120, "contexts_loaded": {"category": 5, "merchant": 10, ...}}`

### `GET /v1/metadata`
Challenge metadata describing the team, model, and architecture approach.
- **Status**: 200 OK
- **Response**: `{"team_name": "Team Antigravity", "model": "deterministic-engine-v1", "version": "1.0.0", ...}`

### `POST /v1/context`
Push scoped context payloads (`category`, `merchant`, `customer`, `trigger`).
- **Status**: 200 OK
- **Response**: `{"accepted": true, "ack_id": "ack_...", "stored_at": "..."}`

### `POST /v1/tick`
Proactive engine simulation tick evaluating available triggers.
- **Payload**: `{"now": "2026-04-26T10:30:00Z", "available_triggers": ["trg_001_research_digest_dentists"]}`
- **Response**:
```json
{
  "actions": [
    {
      "conversation_id": "conv_m_001_drmeera_dentist_delhi_research_digest",
      "merchant_id": "m_001_drmeera_dentist_delhi",
      "customer_id": null,
      "send_as": "vera",
      "trigger_id": "trg_001_research_digest_dentists",
      "template_name": "vera_research_digest_v1",
      "template_params": ["Dr. Meera", "JIDA Oct 2026", ...],
      "body": "Dr. Meera, JIDA Oct 2026's recent publication landed...",
      "cta": "binary_yes_no",
      "suppression_key": "research:dentists:d_2026W17_jida_fluoride",
      "rationale": "Composed use_research_insight for merchant scope..."
    }
  ]
}
```

### `POST /v1/reply`
Synchronous reply processing for inbound merchant or customer turns.
- **Payload**: `{"conversation_id": "conv_123", "merchant_id": "m_001_...", "from_role": "merchant", "message": "Ok lets do it. Whats next?", "received_at": "2026-04-26T10:35:00Z", "turn_number": 1}`
- **Response**:
```json
{
  "action": "send",
  "body": "Here is the campaign proposal ready to confirm and finalize. Confirm when ready to proceed with the next step.",
  "cta": "binary_confirm",
  "wait_seconds": null,
  "rationale": "Switched to action mode upon merchant commitment. Routing to approved Phase 3 action continuation."
}
```

---

## 8. Core Design Principles

1. **Deterministic & Reproducible**: Identical inputs always produce identical business decisions and messages. Zero uncontrolled random or wall-clock jitter.
2. **Anti-Hallucination & Fact Grounding**: Every number, percentage, date, and customer name in outbound messages is strictly bound to input context facts.
3. **Transmission Governance**: Outreach deduplication is strictly bound to `(tenant_key, suppression_key)`. Customer outreach requires active consent.
4. **Conversational Safety**:
   - Hostile opt-outs terminate immediately (`action="end"`).
   - Pure acknowledgements (`"ok"`, `"thanks"`) stand down safely without annoying re-pitches.
   - Missing merchant identity safely stands down fail-closed (`action="wait"`, `body=None`, `cta="none"`).
5. **Multi-Tenant Isolation**: State, suppressions, and context are isolated by tenant and conversation namespace.

---

## 9. Containerized Deployment

To build and run using Docker:

```bash
docker build -t vera-ai-engine .
docker run -p 8080:8080 vera-ai-engine
```
