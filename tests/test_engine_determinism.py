"""Tests verifying 100-run determinism of the decision engine."""

import json
from pathlib import Path
import pytest

from app.domain.facts.fingerprint import compute_canonical_fingerprint
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.decide import decide

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


def test_100_runs_decision_determinism():
    """Verify that 100 repeated decide() calls on identical context produce byte-for-byte identical decisions."""
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat = CategoryProfile.from_dict(json.load(f))
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        m = MerchantState.from_dict(json.load(f)["merchants"][0])
    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        trg = TriggerState.from_dict(json.load(f)["triggers"][2])  # trg_003_recall_due_priya
    with open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8") as f:
        cust = CustomerStateModel.from_dict(json.load(f)["customers"][0])

    # Run 0: reference decision
    base_decision = decide(cat, m, trg, cust)
    base_dict = base_decision.to_dict()
    base_fingerprint = compute_canonical_fingerprint(base_dict)

    # 100 repeated runs
    for i in range(100):
        d = decide(cat, m, trg, cust)
        d_dict = d.to_dict()
        assert d.action == base_decision.action
        assert d.score == base_decision.score
        assert d.next_step == base_decision.next_step
        assert len(d.evidence_facts) == len(base_decision.evidence_facts)
        assert compute_canonical_fingerprint(d_dict) == base_fingerprint
