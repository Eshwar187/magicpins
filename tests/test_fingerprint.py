"""Tests for canonical serialization and SHA-256 fingerprinting."""

import pytest
from app.domain.facts.fingerprint import canonical_json_dumps, compute_canonical_fingerprint


def test_dictionary_key_ordering_independence():
    """Verify that different dictionary key insertion orders produce identical canonical JSON and fingerprint."""
    dict_a = {"z": 1, "a": 2, "m": {"nested_b": 20, "nested_a": 10}}
    dict_b = {"a": 2, "m": {"nested_a": 10, "nested_b": 20}, "z": 1}

    canon_a = canonical_json_dumps(dict_a)
    canon_b = canonical_json_dumps(dict_b)

    assert canon_a == canon_b
    assert compute_canonical_fingerprint(dict_a) == compute_canonical_fingerprint(dict_b)


def test_float_numeric_fidelity_preserved():
    """Verify that high-precision floats are NOT arbitrarily rounded (Correction 2)."""
    val1 = {"metric": 0.1234564}
    val2 = {"metric": 0.1234565}

    fp1 = compute_canonical_fingerprint(val1)
    fp2 = compute_canonical_fingerprint(val2)

    assert fp1 != fp2, "Different float values must produce different fingerprints"


def test_boolean_vs_integer_distinction():
    """Verify that True is distinguished from 1, and False from 0."""
    obj_bool = {"active": True, "count": 0}
    obj_int = {"active": 1, "count": False}

    canon_bool = canonical_json_dumps(obj_bool)
    canon_int = canonical_json_dumps(obj_int)

    assert canon_bool != canon_int
    assert compute_canonical_fingerprint(obj_bool) != compute_canonical_fingerprint(obj_int)


def test_null_representation_determinism():
    """Verify that None/null serializes cleanly and consistently."""
    data = {"phone": None, "scope": []}
    canon = canonical_json_dumps(data)
    assert canon == '{"phone":null,"scope":[]}'
