"""Tests verifying 100% determinism of normalization, fact extraction, and fingerprinting."""

import json
from pathlib import Path
import pytest

from app.domain.facts.extractor import extract_facts
from app.domain.facts.fingerprint import compute_canonical_fingerprint
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


def test_repeated_extraction_is_strictly_deterministic():
    """Verify that repeated fact extraction produces identical facts, IDs, and orderings."""
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat = CategoryProfile.from_dict(json.load(f))
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        m = MerchantState.from_dict(json.load(f)["merchants"][0])
    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        trg = TriggerState.from_dict(json.load(f)["triggers"][0])
    with open(DATASET_DIR / "customers_seed.json", "r", encoding="utf-8") as f:
        cust = CustomerStateModel.from_dict(json.load(f)["customers"][0])

    base_facts = extract_facts(cat, m, trg, cust)
    base_fingerprint = compute_canonical_fingerprint([f.fact_id for f in base_facts])

    # Execute 50 times in a loop
    for _ in range(50):
        run_facts = extract_facts(cat, m, trg, cust)
        assert len(run_facts) == len(base_facts)
        for f_base, f_run in zip(base_facts, run_facts):
            assert f_base.fact_id == f_run.fact_id
            assert f_base.name == f_run.name
            assert f_base.value == f_run.value
            assert f_base.source_path == f_run.source_path

        run_fingerprint = compute_canonical_fingerprint([f.fact_id for f in run_facts])
        assert run_fingerprint == base_fingerprint
