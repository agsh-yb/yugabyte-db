from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Sequence

from .config import Config
from .db import DbExecutor
from .generator import generate_schema_and_data
from .llm import LlmClient
from .compare import compare_outcomes


def run_llm_cases(
    cfg: Config,
    cases: Optional[int] = None,
    seed: Optional[int] = None,
    topics: Optional[Sequence[str]] = None,
    queries_per_case: Optional[int] = None,
) -> int:
    rcases = cases if cases is not None else cfg.run.cases
    rseed = seed if seed is not None else cfg.run.seed
    qpc = queries_per_case if queries_per_case is not None else (cfg.llm.queries_per_case if cfg.llm else 1)

    if not cfg.llm:
        raise RuntimeError("LLM configuration is missing in config")

    artifacts_root = None
    if cfg.run.save_artifacts:
        ts = int(time.time())
        artifacts_root = Path(cfg.run.artifacts_dir) / f"llm_run_{ts}_seed_{rseed}"
        artifacts_root.mkdir(parents=True, exist_ok=True)

    pg = DbExecutor(cfg.postgres.dsn, application_name="ydiff_pg")
    yb = DbExecutor(cfg.yugabyte.dsn, application_name="ydiff_yb")
    llm = LlmClient(cfg.llm)

    failures = 0
    import random

    rng = random.Random(rseed)
    global_case_index = 0
    for case_idx in range(rcases):
        case_rng = random.Random(rng.randint(0, 2**32 - 1))
        schema = generate_schema_and_data(
            case_rng,
            cfg.run.max_tables,
            cfg.run.max_columns_per_table,
            cfg.run.max_rows_per_table,
            cfg.run.enable_float,
        )
        setup_sql = schema.ddl + ("\n" + schema.inserts if schema.inserts else "")
        # Ask LLM for queries
        llm_queries = llm.generate_sql_queries(
            schema_ddl=schema.ddl,
            table_names=schema.table_names,
            topics=topics,
            seed=rng.randint(0, 2**32 - 1),
            num_queries=qpc,
        )

        for q_idx, query_sql in enumerate(llm_queries[:qpc]):
            global_case_index += 1
            pg_out = pg.execute_batch(setup_sql + "\n" + query_sql, timeout_s=cfg.run.timeout_seconds)
            yb_out = yb.execute_batch(setup_sql + "\n" + query_sql, timeout_s=cfg.run.timeout_seconds)
            pgj = pg_out.to_jsonable()
            ybj = yb_out.to_jsonable()
            diff = compare_outcomes(pgj, ybj)
            if diff and artifacts_root:
                failures += 1
                case_dir = artifacts_root / f"case_{case_idx}_q_{q_idx}"
                case_dir.mkdir(parents=True, exist_ok=True)
                (case_dir / "schema.sql").write_text(setup_sql, encoding="utf-8")
                (case_dir / "query.sql").write_text(query_sql, encoding="utf-8")
                (case_dir / "pg_result.json").write_text(json.dumps(pgj, indent=2, sort_keys=True), encoding="utf-8")
                (case_dir / "yb_result.json").write_text(json.dumps(ybj, indent=2, sort_keys=True), encoding="utf-8")
                (case_dir / "diff.json").write_text(json.dumps(diff, indent=2, sort_keys=True), encoding="utf-8")
                (case_dir / "context.json").write_text(
                    json.dumps(
                        {
                            "seed": rseed,
                            "case_index": case_idx,
                            "query_index": q_idx,
                            "config": {"run": asdict(cfg.run), "llm": asdict(cfg.llm)},
                            "topics": list(topics) if topics else None,
                        },
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                # Save prompts as well
                # We cannot recover the exact prompt from the client, so recompose an approximate log
                (case_dir / "llm_used_model.txt").write_text(cfg.llm.model, encoding="utf-8")

    return failures
