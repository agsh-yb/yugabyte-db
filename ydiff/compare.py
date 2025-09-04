from __future__ import annotations

from typing import Any, Dict, Optional

from .normalize import normalize_rows, normalize_error


def compare_outcomes(pg: Dict[str, Any], yb: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Returns diff dict if mismatch, else None
    pg_ok = pg.get("ok")
    yb_ok = yb.get("ok")
    if pg_ok != yb_ok:
        return {
            "kind": "status",
            "pg_ok": pg_ok,
            "yb_ok": yb_ok,
            "pg_error": normalize_error(pg.get("error")),
            "yb_error": normalize_error(yb.get("error")),
        }

    if not pg_ok and not yb_ok:
        # Both errored. Compare normalized error classes/messages broadly.
        if normalize_error(pg.get("error")) != normalize_error(yb.get("error")):
            return {
                "kind": "error",
                "pg_error": normalize_error(pg.get("error")),
                "yb_error": normalize_error(yb.get("error")),
            }
        return None

    # Both ok, compare rows (order-independent)
    pgr = normalize_rows(pg.get("rows"))
    ybr = normalize_rows(yb.get("rows"))
    if pgr != ybr:
        return {
            "kind": "rows",
            "pg_rows": pgr,
            "yb_rows": ybr,
        }

    # Optionally compare rowcount if no rows
    if pgr is None and ybr is None:
        if pg.get("rowcount") != yb.get("rowcount"):
            return {
                "kind": "rowcount",
                "pg_rowcount": pg.get("rowcount"),
                "yb_rowcount": yb.get("rowcount"),
            }

    return None
