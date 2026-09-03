"""End-to-end canonical regression tests passing all 10 scenarios through the live HTTP API."""

import json
from pathlib import Path
import pytest
from tests.client import TestClient

from app.main import app
from app.api.routes import get_service

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


@pytest.fixture
def api_client():
    service = get_service()
    service.clear()

    # Pre-populate all 5 categories
    client = TestClient(app)
    for p in (DATASET_DIR / "categories").glob("*.json"):
        with open(p, "r", encoding="utf-8") as f:
            cat_data = json.load(f)
            client.post("/v1/context", json={
                "scope": "category", "context_id": cat_data["slug"],
                "version": 1, "payload": cat_data
            })

    # Pre-populate merchants
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        for m in json.load(f)["merchants"]:
            client.post("/v1/context", json={
                "scope": "merchant", "context_id": m["merchant_id"],
                "version": 1, "payload": m
            })

    # Pre-populate customers
    with open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8") as f:
        for c in json.load(f)["customers"]:
            client.post("/v1/context", json={
                "scope": "customer", "context_id": c["customer_id"],
                "version": 1, "payload": c
            })

    # Pre-populate triggers
    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        for t in json.load(f)["triggers"]:
            client.post("/v1/context", json={
                "scope": "trigger", "context_id": t["id"],
                "version": 1, "payload": t
            })

    yield client
    service.clear()


@pytest.mark.parametrize("trg_id,expected_snippet,expected_cta,expected_send_as", [
    ("trg_001_research_digest_dentists", "Dr. Meera", "binary_yes_no", "vera"),
    ("trg_003_recall_due_priya", "Priya", "multi_choice_slot", "merchant_on_behalf"),
    ("trg_007_bridal_followup_kavya", "Kavya", "binary_yes_no", "merchant_on_behalf"),
    ("trg_008_curious_ask_studio11", "Studio11 Family Salon", "open_ended", "vera"),
    ("trg_010_ipl_match_delhi", "DC vs MI", "binary_yes_no", "vera"),
    ("trg_013_corporate_thali_planning", "Indiranagar", "binary_yes_no", "vera"),
    ("trg_014_seasonal_acquisition_dip_powerhouse", "views dropped 30%", "binary_yes_no", "vera"),
    ("trg_015_winback_rashmi", "Rashmi", "binary_yes_no", "merchant_on_behalf"),
    ("trg_018_supply_atorvastatin_recall", "atorvastatin", "binary_yes_no", "vera"),
    ("trg_019_chronic_refill_grandfather", "Mr. Sharma", "binary_confirm", "merchant_on_behalf"),
])
def test_end_to_end_canonical_case_via_http(api_client, trg_id, expected_snippet, expected_cta, expected_send_as):
    """Verify each canonical scenario passes through HTTP POST /v1/tick and matches expected semantics."""
    resp = api_client.post("/v1/tick", json={
        "now": "2026-04-26T10:35:00Z",
        "available_triggers": [trg_id]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "actions" in data
    assert len(data["actions"]) == 1

    action = data["actions"][0]
    assert action["trigger_id"] == trg_id
    assert action["send_as"] == expected_send_as
    assert action["cta"] == expected_cta
    assert expected_snippet in action["body"]
    assert len(action["rationale"]) > 0
    assert len(action["suppression_key"]) > 0
    assert len(action["conversation_id"]) > 0
