from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .config import LlmConfig


class LlmClient:
    def __init__(self, cfg: LlmConfig) -> None:
        self.cfg = cfg
        provider = (cfg.provider or "openai").lower()
        if provider not in {"openai", "openai_compat"}:
            raise ValueError(f"Unsupported LLM provider: {cfg.provider}")
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "openai package is required for LLM generation. Install with `pip install openai`"
            ) from exc

        api_key = os.getenv(cfg.api_key_env or "OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"Missing API key in environment variable {cfg.api_key_env or 'OPENAI_API_KEY'}"
            )
        if cfg.base_url:
            self.client = OpenAI(api_key=api_key, base_url=cfg.base_url)
        else:
            self.client = OpenAI(api_key=api_key)

    def generate_sql_queries(
        self,
        schema_ddl: str,
        table_names: Sequence[str],
        topics: Optional[Sequence[str]],
        seed: int,
        num_queries: int,
    ) -> List[str]:
        sys_prompt = self.cfg.system_prompt or _DEFAULT_SYSTEM_PROMPT
        user_prompt = _build_user_prompt(schema_ddl, table_names, topics, num_queries, seed)
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_output_tokens,
            top_p=self.cfg.top_p,
            n=1,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = resp.choices[0].message.content or ""
        return _extract_sql_statements(text)


def _build_user_prompt(
    schema_ddl: str,
    table_names: Sequence[str],
    topics: Optional[Sequence[str]],
    num_queries: int,
    seed: int,
) -> str:
    topics_line = (
        "Focus topics: " + ", ".join(t.strip() for t in topics if t.strip())
        if topics
        else ""
    )
    return (
        f"We are testing SQL compatibility. Seed={seed}. {topics_line}\n"
        f"Schema (already created as TEMP tables):\n{schema_ddl}\n\n"
        f"Please produce exactly {num_queries} SQL queries that will run against the above TEMP tables.\n"
        "- Use only the given tables and columns.\n"
        "- Avoid non-deterministic functions unless necessary.\n"
        "- Prefer SELECTs, but small DML is acceptable (INSERT/UPDATE/DELETE) on TEMP tables.\n"
        "- Include a variety of shapes (joins, aggregates, subqueries, set ops, window functions if suitable).\n"
        "- Do not include explanations. Output SQL only, inside a single fenced code block.\n"
        "- Separate statements with semicolons.\n"
    )


_SQL_BLOCK_RE = re.compile(r"```(?:sql)?\n([\s\S]*?)\n```", re.IGNORECASE)


def _extract_sql_statements(text: str) -> List[str]:
    m = _SQL_BLOCK_RE.search(text)
    payload = m.group(1) if m else text
    # Split on semicolons, keep non-empty
    parts = [p.strip() for p in payload.split(";")]
    stmts = [p + ";" for p in parts if p.strip()]
    return stmts


_DEFAULT_SYSTEM_PROMPT = (
    "You are a careful SQL generator for cross-database differential testing. "
    "You only output executable SQL statements compatible with PostgreSQL dialect."
)
