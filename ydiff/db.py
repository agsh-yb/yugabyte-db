from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class QueryOutcome:
    ok: bool
    error: Optional[str]
    rows: Optional[List[Dict[str, Any]]]
    rowcount: Optional[int]
    columns: Optional[List[str]]

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error,
            "rows": self.rows,
            "rowcount": self.rowcount,
            "columns": self.columns,
        }


class DbExecutor:
    def __init__(self, dsn: str, application_name: str) -> None:
        self.dsn = dsn
        self.application_name = application_name

    @retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=4), stop=stop_after_attempt(5))
    def connect(self):
        return psycopg.connect(self.dsn, application_name=self.application_name)

    def execute_batch(self, statements: str, timeout_s: int) -> QueryOutcome:
        try:
            with self.connect() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    # Disable autocommit to isolate schema/data
                    conn.execute("BEGIN")
                    try:
                        cur.execute(SQL("SET statement_timeout = %s"), (timeout_s * 1000,))
                    except Exception:
                        pass
                    for stmt in _split_sql(statements):
                        if not stmt.strip():
                            continue
                        cur.execute(stmt)
                    try:
                        rows = None
                        columns = None
                        rowcount = cur.rowcount
                        if cur.description:
                            columns = [d.name for d in cur.description]
                            rows = [dict(r) for r in cur.fetchall()]
                        conn.execute("ROLLBACK")
                        return QueryOutcome(True, None, rows, rowcount, columns)
                    except Exception:
                        # If no result set or fetch fails, still rollback and treat as ok
                        conn.execute("ROLLBACK")
                        return QueryOutcome(True, None, None, cur.rowcount, None)
        except Exception as e:
            return QueryOutcome(False, _short_error(e), None, None, None)

    def run_query(self, query: str, timeout_s: int) -> QueryOutcome:
        try:
            with self.connect() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    try:
                        cur.execute(SQL("SET statement_timeout = %s"), (timeout_s * 1000,))
                    except Exception:
                        pass
                    try:
                        cur.execute(query)
                        rows = None
                        columns = None
                        rowcount = cur.rowcount
                        if cur.description:
                            columns = [d.name for d in cur.description]
                            rows = [dict(r) for r in cur.fetchall()]
                        return QueryOutcome(True, None, rows, rowcount, columns)
                    except Exception as e:
                        return QueryOutcome(False, _short_error(e), None, None, None)
        except Exception as e:
            return QueryOutcome(False, _short_error(e), None, None, None)


def _short_error(e: Exception) -> str:
    try:
        return json.dumps({"type": type(e).__name__, "msg": str(e)})
    except Exception:
        return f"{type(e).__name__}:{e}"


def _split_sql(sql: str) -> list[str]:
    """
    Very simple statement splitter: split by semicolons not in quotes.
    Good enough for our generated SQL.
    """
    parts: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    prev = ""
    for ch in sql:
        if ch == "'" and not in_double and prev != "\\":
            in_single = not in_single
        elif ch == '"' and not in_single and prev != "\\":
            in_double = not in_double
        if ch == ";" and not in_single and not in_double:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        prev = ch
    rest = "".join(buf).strip()
    if rest:
        parts.append(rest)
    return parts
