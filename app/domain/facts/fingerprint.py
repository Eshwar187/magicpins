"""Deterministic canonical serialization and cryptographic fingerprinting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any
from pydantic import BaseModel


def to_canonical_primitive(obj: Any) -> Any:
    """Recursively convert domain objects to JSON-serializable primitives."""
    if isinstance(obj, BaseModel):
        return to_canonical_primitive(obj.model_dump())
    if is_dataclass(obj) and not isinstance(obj, type):
        return to_canonical_primitive(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): to_canonical_primitive(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_canonical_primitive(v) for v in obj]
    if isinstance(obj, set):
        # Sort sets for deterministic ordering since sets are inherently unordered
        return sorted([to_canonical_primitive(v) for v in obj], key=lambda x: str(x))
    return obj


def canonical_json_dumps(obj: Any) -> str:
    """Serializes an object to deterministic, canonical JSON.
    
    Guarantees:
    - Dictionary keys are sorted at all levels.
    - Preserves exact numeric values without arbitrary float precision rounding.
    - Preserves list order.
    - Distinguishes booleans (true/false) from integers (1/0).
    - Preserves Unicode without ASCII escaping.
    - Compact separators without whitespace discrepancy.
    """
    primitive = to_canonical_primitive(obj)
    return json.dumps(
        primitive,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def compute_canonical_fingerprint(obj: Any) -> str:
    """Computes a stable SHA-256 fingerprint over the canonical JSON representation."""
    canonical_str = canonical_json_dumps(obj)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
