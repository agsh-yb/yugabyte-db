from __future__ import annotations

import sys
from pathlib import Path

import click

from .config import load_config
from .reducer import simple_reducer
from .runner import run_cases


@click.group()
def cli():
    pass


@cli.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default="config.yaml")
@click.option("--cases", type=int, default=None, help="Override number of cases")
@click.option("--seed", type=int, default=None, help="Override RNG seed")
@click.option("--case-offset", type=int, default=0, help="Start case index")
def run(config_path: str, cases: int | None, seed: int | None, case_offset: int):
    cfg = load_config(config_path if config_path and Path(config_path).exists() else None)
    failures = run_cases(cfg, cases=cases, seed=seed, case_offset=case_offset)
    click.echo(f"Completed with {failures} mismatches.")
    sys.exit(1 if failures else 0)


@cli.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default="config.yaml")
@click.option("--input", "input_sql", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--seed", type=int, default=0, help="Seed for deterministic reduction order")
def reduce(config_path: str, input_sql: str, seed: int):
    _ = load_config(config_path if config_path and Path(config_path).exists() else None)

    def test_fn(sql: str) -> bool:
        # Placeholder: user should implement calling the harness on the fixed schema+query
        # For now, always return False (no mismatch) to avoid loops
        return False

    original = Path(input_sql).read_text(encoding="utf-8")
    reduced = simple_reducer(original, rng_seed=seed, test_fn=test_fn)
    Path("reduced.sql").write_text(reduced, encoding="utf-8")
    click.echo("Wrote reduced.sql")


def main():
    cli(prog_name="ydiff")


if __name__ == "__main__":
    main()
