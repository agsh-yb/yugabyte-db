from __future__ import annotations

import json
import os
import random
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Tuple

from .compare import compare_outcomes
from .config import Config
from .db import DbExecutor
from .generator import generate_schema_and_data, generate_query


def run_cases(cfg: Config, cases: int | None = None, seed: int | None = None, case_offset: int = 0) -> int:
    rcases = cases if cases is not None else cfg.run.cases
    rseed = seed if seed is not None else cfg.run.seed
    rng = random.Random(rseed)

    artifacts_root = None
    if cfg.run.save_artifacts:
        ts = int(time.time())
        artifacts_root = Path(cfg.run.artifacts_dir) / f"run_{ts}_seed_{rseed}"
        artifacts_root.mkdir(parents=True, exist_ok=True)

    pg = DbExecutor(cfg.postgres.dsn, application_name="ydiff_pg")
    yb = DbExecutor(cfg.yugabyte.dsn, application_name="ydiff_yb")

    failures = 0
    for i in range(case_offset, case_offset + rcases):
        case_rng = random.Random(rng.randint(0, 2**32 - 1))
        schema = generate_schema_and_data(
            case_rng,
            cfg.run.max_tables,
            cfg.run.max_columns_per_table,
            cfg.run.max_rows_per_table,
            cfg.run.enable_float,
        )
        setup_sql = schema.ddl + ("\n" + schema.inserts if schema.inserts else "")
        query_sql = generate_query(case_rng, schema.table_names)
        # Execute setup+query as one batch inside a tx to avoid cross-case leaks.
        pg_out = pg.execute_batch(setup_sql + "\n" + query_sql, timeout_s=cfg.run.timeout_seconds)
        yb_out = yb.execute_batch(setup_sql + "\n" + query_sql, timeout_s=cfg.run.timeout_seconds)
        pgj = pg_out.to_jsonable()
        ybj = yb_out.to_jsonable()
        diff = compare_outcomes(pgj, ybj)
        if diff:
            failures += 1
            if artifacts_root:
                case_dir = artifacts_root / f"case_{i}"
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
                            "case_index": i,
                            "config": {
                                "run": asdict(cfg.run),
                            },
                        },
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
    return failures
