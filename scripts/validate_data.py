#!/usr/bin/env python3
"""
Brazil All Market Data — Data validation script.

Walks the entire data/ tree, validates every CSV and prints a summary
with row counts grouped by category.
"""

import os
import sys

import pandas as pd


def validate_csvs(directory: str = "data") -> bool:
    """Validate all CSVs under *directory*. Returns True if all pass."""
    counts: dict[str, dict] = {}   # category -> {ok, warn, err}
    all_ok = True

    print(f"Validating CSVs in '{directory}'...\n")
    for root, _dirs, files in sorted(os.walk(directory)):
        csv_files = sorted(f for f in files if f.endswith(".csv"))
        if not csv_files:
            continue
        category = os.path.relpath(root, directory)
        counts[category] = {"ok": 0, "warn": 0, "err": 0}
        print(f"  [{category}]")
        for fname in csv_files:
            filepath = os.path.join(root, fname)
            try:
                df = pd.read_csv(filepath)
                if df.empty:
                    print(f"    [WARNING] {fname} — empty")
                    counts[category]["warn"] += 1
                    all_ok = False
                else:
                    print(f"    [OK]      {fname} — {len(df):,} rows")
                    counts[category]["ok"] += 1
            except Exception as exc:
                print(f"    [ERROR]   {fname} — {exc}")
                counts[category]["err"] += 1
                all_ok = False
        print()

    # Summary table
    print("─" * 50)
    print(f"{'Category':<35} {'OK':>5} {'WARN':>5} {'ERR':>5}")
    print("─" * 50)
    total_ok = total_warn = total_err = 0
    for cat, c in sorted(counts.items()):
        print(f"{cat:<35} {c['ok']:>5} {c['warn']:>5} {c['err']:>5}")
        total_ok += c["ok"]
        total_warn += c["warn"]
        total_err += c["err"]
    print("─" * 50)
    print(f"{'TOTAL':<35} {total_ok:>5} {total_warn:>5} {total_err:>5}")
    print("─" * 50)
    return all_ok


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else "data"
    ok = validate_csvs(directory)
    sys.exit(0 if ok else 1)
