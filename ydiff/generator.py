from __future__ import annotations

import random
import string
from dataclasses import dataclass
from typing import List, Tuple


_IDENT_CHARS = string.ascii_lowercase


@dataclass
class SchemaSpec:
    ddl: str
    inserts: str
    table_names: List[str]


def _rand_ident(rng: random.Random, min_len: int = 5, max_len: int = 10) -> str:
    length = rng.randint(min_len, max_len)
    return "t_" + "".join(rng.choice(_IDENT_CHARS) for _ in range(length))


def _rand_col_ident(rng: random.Random) -> str:
    return "c_" + "".join(rng.choice(_IDENT_CHARS) for _ in range(rng.randint(3, 8)))


def generate_schema_and_data(
    rng: random.Random,
    max_tables: int,
    max_columns_per_table: int,
    max_rows_per_table: int,
    enable_float: bool,
) -> SchemaSpec:
    num_tables = rng.randint(1, max_tables)
    table_names: List[str] = []
    ddl_parts: List[str] = []
    insert_parts: List[str] = []
    for t in range(num_tables):
        table = _rand_ident(rng)
        table_names.append(table)
        num_cols = rng.randint(1, max_columns_per_table)
        cols: List[Tuple[str, str]] = []
        for _ in range(num_cols):
            col_name = _rand_col_ident(rng)
            col_type = rng.choice(
                [
                    "INT",
                    "BIGINT",
                    "BOOLEAN",
                    "TEXT",
                    "DATE",
                ]
                + (["DOUBLE PRECISION"] if enable_float else [])
            )
            cols.append((col_name, col_type))
        col_defs = ", ".join(f"{c} {t}" for c, t in cols)
        ddl_parts.append(f"CREATE TEMP TABLE {table} ({col_defs});")

        # Inserts
        num_rows = rng.randint(0, max_rows_per_table)
        if num_rows > 0:
            for _ in range(num_rows):
                values = []
                for _, tpe in cols:
                    if tpe in ("INT", "BIGINT"):
                        values.append(str(rng.randint(-1000, 1000)))
                    elif tpe == "BOOLEAN":
                        values.append("TRUE" if rng.random() < 0.5 else "FALSE")
                    elif tpe == "TEXT":
                        s = "".join(rng.choice(string.ascii_letters) for _ in range(rng.randint(0, 6)))
                        values.append("'" + s.replace("'", "''") + "'")
                    elif tpe == "DATE":
                        year = rng.randint(1990, 2022)
                        month = rng.randint(1, 12)
                        day = rng.randint(1, 28)
                        values.append(f"DATE '{year:04d}-{month:02d}-{day:02d}'")
                    elif tpe == "DOUBLE PRECISION":
                        values.append(str(rng.uniform(-1000, 1000)))
                    else:
                        values.append("NULL")
                insert_parts.append(
                    f"INSERT INTO {table} VALUES (" + ", ".join(values) + ");"
                )

    return SchemaSpec(ddl="\n".join(ddl_parts), inserts="\n".join(insert_parts), table_names=table_names)


def generate_query(rng: random.Random, tables: List[str]) -> str:
    # Simple shapes: SELECT projections, filters, joins, aggregates, set ops
    if not tables:
        return "SELECT 1;"

    shape = rng.choice(["select", "agg", "join", "setop", "subq", "window"])  # window not yet detailed
    t1 = rng.choice(tables)
    if shape == "select":
        limit = rng.choice(["", " LIMIT 10", " LIMIT 1", " LIMIT 100"])
        return f"SELECT * FROM {t1}{limit};"
    if shape == "agg":
        return f"SELECT COUNT(*) AS cnt FROM {t1};"
    if shape == "join" and len(tables) >= 2:
        t2 = rng.choice([t for t in tables if t != t1])
        return f"SELECT COUNT(*) FROM {t1} JOIN {t2} ON 1=1;"
    if shape == "setop" and len(tables) >= 2:
        t2 = rng.choice([t for t in tables if t != t1])
        return f"SELECT * FROM {t1} UNION ALL SELECT * FROM {t2};"
    if shape == "subq":
        return f"SELECT * FROM (SELECT * FROM {t1}) q LIMIT 5;"
    # Fallback
    return f"SELECT * FROM {t1} LIMIT 10;"
