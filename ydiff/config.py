import os
from dataclasses import dataclass
from typing import Optional

import yaml


@dataclass
class DbConfig:
    dsn: str


@dataclass
class RunConfig:
    cases: int = 200
    seed: int = 42
    case_offset: int = 0
    max_tables: int = 3
    max_columns_per_table: int = 6
    max_rows_per_table: int = 100
    enable_float: bool = False
    save_artifacts: bool = True
    artifacts_dir: str = "./artifacts"
    compare_plans: bool = False
    timeout_seconds: int = 30


@dataclass
class Config:
    postgres: DbConfig
    yugabyte: DbConfig
    run: RunConfig


def load_config(path: Optional[str]) -> Config:
    cfg = {}
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    # Allow env overrides
    pg_dsn = os.getenv("PG_DSN", cfg.get("postgres", {}).get("dsn"))
    yb_dsn = os.getenv("YB_DSN", cfg.get("yugabyte", {}).get("dsn"))
    run_cfg = cfg.get("run", {})

    if not pg_dsn:
        pg_dsn = "postgresql://postgres:postgres@localhost:5432/postgres"
    if not yb_dsn:
        # Yugabyte default superuser is usually yugabyte:yugabyte and db yugabyte
        yb_dsn = "postgresql://yugabyte:yugabyte@localhost:5433/yugabyte"

    run = RunConfig(
        cases=int(os.getenv("RUN_CASES", run_cfg.get("cases", 200))),
        seed=int(os.getenv("RUN_SEED", run_cfg.get("seed", 42))),
        case_offset=int(os.getenv("RUN_CASE_OFFSET", run_cfg.get("case_offset", 0))),
        max_tables=int(os.getenv("RUN_MAX_TABLES", run_cfg.get("max_tables", 3))),
        max_columns_per_table=int(os.getenv("RUN_MAX_COLS", run_cfg.get("max_columns_per_table", 6))),
        max_rows_per_table=int(os.getenv("RUN_MAX_ROWS", run_cfg.get("max_rows_per_table", 100))),
        enable_float=_to_bool(os.getenv("RUN_ENABLE_FLOAT", run_cfg.get("enable_float", False))),
        save_artifacts=_to_bool(os.getenv("RUN_SAVE_ARTIFACTS", run_cfg.get("save_artifacts", True))),
        artifacts_dir=os.getenv("RUN_ARTIFACTS_DIR", run_cfg.get("artifacts_dir", "./artifacts")),
        compare_plans=_to_bool(os.getenv("RUN_COMPARE_PLANS", run_cfg.get("compare_plans", False))),
        timeout_seconds=int(os.getenv("RUN_TIMEOUT_SECONDS", run_cfg.get("timeout_seconds", 30))),
    )

    return Config(postgres=DbConfig(dsn=pg_dsn), yugabyte=DbConfig(dsn=yb_dsn), run=run)


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}
