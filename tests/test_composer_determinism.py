"""Tests verifying 100-run bit-for-bit determinism of the Vera message composer."""

import json
from pathlib import Path
import pytest

from app.domain.facts.fingerprint import compute_canonical_fingerprint
from app.domain.models.category import CategoryProfile
from app.domain.models.customer import CustomerStateModel
from app.domain.models.merchant import MerchantState
from app.domain.models.trigger import TriggerState
from app.engine.decide import decide
from app.composer.compose import compose

DATASET_DIR = Path(__file__).parent.parent / "magicpin-ai-challenge" / "dataset"


def test_100_runs_composer_determinism():
    """Verify that 100 repeated compose() calls produce identical serialized message dictionaries."""
    with open(DATASET_DIR / "categories" / "dentists.json", "r", encoding="utf-8") as f:
        cat = CategoryProfile.from_dict(json.load(f))
    with open(DATASET_DIR / "merchants_seed.json", "r", encoding="utf-8") as f:
        m = MerchantState.from_dict(json.load(f)["merchants"][0])
    with open(DATASET_DIR / "triggers_seed.json", "r", encoding="utf-8") as f:
        trg = TriggerState.from_dict(json.load(f)["triggers"][0])

    decision = decide(cat, m, trg)

    # Reference run
    base_msg = compose(decision, cat, m, trg)
    base_dict = base_msg.to_dict()
    base_fp = compute_canonical_fingerprint(base_dict)

    # 100 repeated iterations
    for _ in range(100):
        msg = compose(decision, cat, m, trg)
        d = msg.to_dict()
        assert d == base_dict
        assert compute_canonical_fingerprint(d) == base_fp
