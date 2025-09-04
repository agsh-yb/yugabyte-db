from __future__ import annotations

import decimal
from typing import Any, Dict, List, Optional


def normalize_rows(rows: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if rows is None:
        return None
    normalized: List[Dict[str, Any]] = []
    for r in rows:
        normalized.append({k: _normalize_cell(v) for k, v in r.items()})
    # Order-independent comparison by sorting row dicts deterministically
    # Convert dicts to tuples for sorting
    def key_fn(d: Dict[str, Any]):
        return tuple(sorted((k, _sort_key(v)) for k, v in d.items()))

    normalized.sort(key=key_fn)
    return normalized


def _normalize_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, float):
        # Round floats to reduce tiny differences
        return round(value, 6)
    # psycopg3 returns Python types for dates, bools, ints, floats
    return value


def normalize_error(err: Optional[str]) -> Optional[str]:
    if err is None:
        return None
    # Reduce noise: lowercased type and strip dynamic parts like OIDs/positions
    lowered = err.lower()
    # Truncate long messages
    return lowered[:500]


def _sort_key(v: Any):
    if v is None:
        return (0, "")
    if isinstance(v, bool):
        return (1, str(v))
    if isinstance(v, (int, float)):
        return (2, float(v))
    return (3, str(v))
