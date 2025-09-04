"""
ydiff: Minimal differential testing harness for YugabyteDB (YSQL) vs PostgreSQL.

This package provides:
- Configuration loading from YAML and environment variables
- Database executors for PostgreSQL and YSQL
- A seeded SQL generator producing schemas, data, and diverse queries
- Normalization and comparison to minimize false positives
- A runner orchestrating multiple cases and writing artifacts
- A simple reducer to shrink failing queries given fixed schema/data
"""

__all__ = [
    "cli",
]
