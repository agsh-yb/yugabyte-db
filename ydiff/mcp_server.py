from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from .config import Config, load_config
from .db import DbExecutor
from .generator import generate_schema_and_data
from .llm import LlmClient
from .compare import compare_outcomes


def serve_mcp(config_path: Optional[str] = None) -> None:
    try:
        # FastMCP provides a terse API for MCP stdio servers
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "Missing mcp library. Install with `pip install mcp` to run the MCP server."
        ) from exc

    cfg = load_config(config_path)
    mcp = FastMCP("ydiff-mcp")

    pg = DbExecutor(cfg.postgres.dsn, application_name="ydiff_pg")
    yb = DbExecutor(cfg.yugabyte.dsn, application_name="ydiff_yb")
    llm = LlmClient(cfg.llm) if cfg.llm else None

    @mcp.tool()
    def new_case(max_tables: int | None = None, max_columns: int | None = None, max_rows: int | None = None) -> Dict[str, Any]:
        import random

        r = random.Random()
        schema = generate_schema_and_data(
            r,
            max_tables or cfg.run.max_tables,
            max_columns or cfg.run.max_columns_per_table,
            max_rows or cfg.run.max_rows_per_table,
            cfg.run.enable_float,
        )
        return {"ddl": schema.ddl, "inserts": schema.inserts, "tables": schema.table_names}

    @mcp.tool()
    def run_query(schema_sql: str, query_sql: str, timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
        to = timeout_seconds or cfg.run.timeout_seconds
        pg_out = pg.execute_batch(schema_sql + ("\n" + query_sql), timeout_s=to)
        yb_out = yb.execute_batch(schema_sql + ("\n" + query_sql), timeout_s=to)
        pgj = pg_out.to_jsonable()
        ybj = yb_out.to_jsonable()
        diff = compare_outcomes(pgj, ybj)
        return {"pg": pgj, "yb": ybj, "diff": diff}

    @mcp.tool()
    def generate_queries(schema_sql: str, table_names: List[str], topics: Optional[List[str]] = None, num_queries: int = 3, seed: Optional[int] = None) -> Dict[str, Any]:
        if not llm:
            raise RuntimeError("LLM is not configured")
        import random

        s = seed if seed is not None else random.randint(0, 2**32 - 1)
        stmts = llm.generate_sql_queries(schema_sql, table_names, topics, s, num_queries)
        return {"queries": stmts}

    # Run over stdio; MCP clients launch this process and speak stdio JSON-RPC
    mcp.run()
