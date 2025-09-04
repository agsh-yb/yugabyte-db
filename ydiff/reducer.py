from __future__ import annotations

import random
from typing import Callable


def simple_reducer(
    original_sql: str,
    rng_seed: int,
    test_fn: Callable[[str], bool],
    max_iters: int = 200,
) -> str:
    """
    Very simple delta-like reducer: attempts to remove lines and shrink tokens while the test_fn still reproduces the mismatch.
    test_fn(sql) -> True if mismatch persists.
    """
    rng = random.Random(rng_seed)
    current = original_sql
    lines = [l for l in current.split("\n") if l.strip()]

    # Line deletion pass
    improved = True
    while improved and len(lines) > 1 and max_iters > 0:
        improved = False
        idx = rng.randrange(0, len(lines))
        candidate = "\n".join(lines[:idx] + lines[idx + 1 :])
        if test_fn(candidate):
            lines = [l for l in candidate.split("\n") if l.strip()]
            improved = True
        max_iters -= 1

    # Token shrink pass: try reducing LIMIT values or replacing expressions with constants
    if max_iters <= 0:
        return "\n".join(lines)

    tokens = "\n".join(lines)
    for limit in [" LIMIT 100", " LIMIT 10", " LIMIT 5", " LIMIT 1", ""]:
        cand = _replace_limit(tokens, limit)
        if cand != tokens and test_fn(cand):
            tokens = cand
        max_iters -= 1
        if max_iters <= 0:
            break

    return tokens


def _replace_limit(sql: str, limit_clause: str) -> str:
    import re

    return re.sub(r"\s+limit\s+\d+", limit_clause, sql, flags=re.IGNORECASE)
