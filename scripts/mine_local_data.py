#!/usr/bin/env python3
"""
Brazil All Market Data — Local data mining pipeline.

Reads all collected CSVs and produces derived datasets under data/mined/:
  equities_daily_returns.csv    Daily % returns for stocks + indices
  fiis_daily_returns.csv        Daily % returns for FIIs
  etfs_daily_returns.csv        Daily % returns for ETFs
  currencies_daily_returns.csv  Daily % returns for FX / crypto
  commodities_daily_returns.csv Daily % returns for commodities
  assets_summary.csv            Per-asset statistics (return, volatility, etc.)
"""

from pathlib import Path

import pandas as pd

BASE_DATA_DIR = Path("data")
MINED_DIR = BASE_DATA_DIR / "mined"

# Directories with market-price CSVs to process
PRICE_DIRS = {
    "equity":    [
        BASE_DATA_DIR / "equities" / "stocks",
        BASE_DATA_DIR / "equities" / "indices",
    ],
    "fii":       [BASE_DATA_DIR / "fiis"],
    "etf":       [BASE_DATA_DIR / "etfs"],
    "currency":  [BASE_DATA_DIR / "currencies"],
    "commodity": [BASE_DATA_DIR / "commodities"],
}


def load_close_series(csv_path: Path) -> "pd.Series | None":
    """Load the Close price column from a CSV (handles yfinance multi-header format)."""
    try:
        df = pd.read_csv(csv_path, header=[0, 1], index_col=0)
        if "Close" in df.columns.get_level_values(0):
            close = df["Close"].iloc[:, 0]
        else:
            close = df.iloc[:, 0]
    except Exception:
        try:
            df = pd.read_csv(csv_path)
            date_col = next(
                (c for c in df.columns if c.lower() in ("date", "data")), None
            )
            if date_col is None:
                return None
            value_cols = [c for c in df.columns if c != date_col]
            if not value_cols:
                return None
            close = df.set_index(date_col)[value_cols[0]]
        except Exception:
            return None

    close = pd.to_numeric(close, errors="coerce").dropna()
    if close.empty:
        return None
    close.index = pd.to_datetime(close.index, errors="coerce")
    close = close[close.index.notna()].sort_index()
    close.name = csv_path.stem
    return close


def collect_csv_files(dirs: "list[Path]") -> "list[Path]":
    files = []
    for d in dirs:
        if d.exists():
            files.extend(sorted(d.glob("*.csv")))
    return files


def build_returns_table(csv_files: "list[Path]") -> pd.DataFrame:
    series_list = []
    for csv_path in csv_files:
        close = load_close_series(csv_path)
        if close is None:
            continue
        series_list.append(close.pct_change())
    if not series_list:
        return pd.DataFrame()
    return pd.concat(series_list, axis=1, sort=False).sort_index()


def build_assets_summary(csv_files: "list[Path]", asset_type: str) -> pd.DataFrame:
    rows = []
    for csv_path in csv_files:
        close = load_close_series(csv_path)
        if close is None or len(close) < 2:
            continue
        start_price = float(close.iloc[0])
        end_price = float(close.iloc[-1])
        total_return = (end_price / start_price) - 1
        days = max((close.index[-1] - close.index[0]).days, 1)
        annualized_return = (1 + total_return) ** (365 / days) - 1
        daily_vol = float(close.pct_change().dropna().std())
        annualized_vol = daily_vol * (252 ** 0.5)
        rows.append(
            {
                "asset": csv_path.stem,
                "asset_type": asset_type,
                "start_date": close.index[0].date().isoformat(),
                "end_date": close.index[-1].date().isoformat(),
                "rows": len(close),
                "start_close": start_price,
                "end_close": end_price,
                "total_return": total_return,
                "annualized_return": annualized_return,
                "annualized_volatility": annualized_vol,
            }
        )
    return pd.DataFrame(rows)


def main():
    MINED_DIR.mkdir(parents=True, exist_ok=True)

    output_names = {
        "equity":    "equities_daily_returns",
        "fii":       "fiis_daily_returns",
        "etf":       "etfs_daily_returns",
        "currency":  "currencies_daily_returns",
        "commodity": "commodities_daily_returns",
    }

    summary_frames = []

    for asset_type, dirs in PRICE_DIRS.items():
        files = collect_csv_files(dirs)
        if not files:
            continue

        returns = build_returns_table(files)
        out_name = output_names[asset_type]
        if not returns.empty:
            out_path = MINED_DIR / f"{out_name}.csv"
            returns.to_csv(out_path)
            print(f"Saved {out_path}")

        summary_frames.append(build_assets_summary(files, asset_type))

    if summary_frames:
        summary = pd.concat(summary_frames, ignore_index=True)
        summary = summary.sort_values(["asset_type", "asset"])
        out_path = MINED_DIR / "assets_summary.csv"
        summary.to_csv(out_path, index=False)
        print(f"Saved {out_path}")

    print("[mine_local_data] Done.")


if __name__ == "__main__":
    main()
