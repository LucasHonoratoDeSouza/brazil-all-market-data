#!/usr/bin/env python3
"""
Brazil All Market Data — Main pipeline entry point.

Executes all three stages in order:

  1. collect   — Download data from BCB/SGS and Yahoo Finance
  2. mine      — Derive daily-return matrices and summary statistics
  3. validate  — Check all CSVs and print a report

Usage:
    python main.py                  # run all stages
    python main.py --collect        # run only the collect stage
    python main.py --mine           # run only the mine stage
    python main.py --validate       # run only the validate stage
"""

import argparse
import sys
import time
from pathlib import Path

# Make sure scripts/ is importable regardless of working directory
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import scripts.collector as collector
import scripts.mine_local_data as miner
import scripts.validate_data as validator


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_collect() -> None:
    _section("Stage 1/3 — Collecting all market data")
    t0 = time.time()
    collector.main()
    print(f"\n  [collect] Done in {time.time() - t0:.0f}s")


def run_mine() -> None:
    _section("Stage 2/3 — Mining derived datasets")
    t0 = time.time()
    miner.main()
    print(f"\n  [mine] Done in {time.time() - t0:.0f}s")


def run_validate() -> None:
    _section("Stage 3/3 — Validating collected data")
    t0 = time.time()
    ok = validator.validate_csvs("data")
    print(f"\n  [validate] Done in {time.time() - t0:.0f}s")
    if not ok:
        print("  [validate] WARNING: some files have issues (see above)")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Brazil All Market Data — full pipeline"
    )
    parser.add_argument(
        "--collect",  action="store_true", help="Run only the collect stage"
    )
    parser.add_argument(
        "--mine",     action="store_true", help="Run only the mine stage"
    )
    parser.add_argument(
        "--validate", action="store_true", help="Run only the validate stage"
    )
    args = parser.parse_args()

    # If no flag given, run everything
    run_all = not (args.collect or args.mine or args.validate)

    wall_start = time.time()

    if run_all or args.collect:
        run_collect()
    if run_all or args.mine:
        run_mine()
    if run_all or args.validate:
        run_validate()

    print(f"\n{'=' * 60}")
    print(f"  Pipeline finished in {time.time() - wall_start:.0f}s")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
