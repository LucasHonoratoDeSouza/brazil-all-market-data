import os
from pathlib import Path

import pandas as pd


BASE_DATA_DIR = Path("data")
MINED_DIR = BASE_DATA_DIR / "mined"


def load_close_series(csv_path: Path) -> pd.Series | None:
    try:
        df = pd.read_csv(csv_path, header=[0, 1], index_col=0)
        if "Close" in df.columns.get_level_values(0):
            close = df["Close"].iloc[:, 0]
        else:
            close = df.iloc[:, 0]
    except Exception:
        try:
            df = pd.read_csv(csv_path)
            if "Date" not in df.columns:
                return None
            value_columns = [c for c in df.columns if c != "Date"]
            if not value_columns:
                return None
            close = df.set_index("Date")[value_columns[0]]
        except Exception:
            return None

    close = pd.to_numeric(close, errors="coerce").dropna()
    if close.empty:
        return None
    close.index = pd.to_datetime(close.index, errors="coerce")
    close = close[close.index.notna()].sort_index()
    close.name = csv_path.stem
    return close


def build_returns_table(csv_files: list[Path]) -> pd.DataFrame:
    series_list = []
    for csv_path in sorted(csv_files):
        close = load_close_series(csv_path)
        if close is None:
            continue
        series_list.append(close.pct_change())
    if not series_list:
        return pd.DataFrame()
    return pd.concat(series_list, axis=1, sort=False).sort_index()


def build_assets_summary(csv_files: list[Path], asset_type: str) -> pd.DataFrame:
    rows = []
    for csv_path in sorted(csv_files):
        close = load_close_series(csv_path)
        if close is None or len(close) < 2:
            continue
        start_price = close.iloc[0]
        end_price = close.iloc[-1]
        total_return = (end_price / start_price) - 1
        days = max((close.index[-1] - close.index[0]).days, 1)
        annualized_return = (1 + total_return) ** (365 / days) - 1
        daily_volatility = close.pct_change().dropna().std()
        annualized_volatility = daily_volatility * (252**0.5)
        rows.append(
            {
                "asset": csv_path.stem,
                "asset_type": asset_type,
                "start_date": close.index[0].date().isoformat(),
                "end_date": close.index[-1].date().isoformat(),
                "rows": len(close),
                "start_close": float(start_price),
                "end_close": float(end_price),
                "total_return": float(total_return),
                "annualized_return": float(annualized_return),
                "annualized_volatility": float(annualized_volatility),
            }
        )
    return pd.DataFrame(rows)


def main():
    MINED_DIR.mkdir(parents=True, exist_ok=True)

    equity_files = list((BASE_DATA_DIR / "equities" / "stocks").glob("*.csv")) + list(
        (BASE_DATA_DIR / "equities" / "indices").glob("*.csv")
    )
    currency_files = list((BASE_DATA_DIR / "currencies").glob("*.csv"))

    equities_returns = build_returns_table(equity_files)
    currencies_returns = build_returns_table(currency_files)

    if not equities_returns.empty:
        equities_returns.to_csv(MINED_DIR / "equities_daily_returns.csv")
        print(f"Saved {MINED_DIR / 'equities_daily_returns.csv'}")
    if not currencies_returns.empty:
        currencies_returns.to_csv(MINED_DIR / "currencies_daily_returns.csv")
        print(f"Saved {MINED_DIR / 'currencies_daily_returns.csv'}")

    summary = pd.concat(
        [
            build_assets_summary(equity_files, "equity"),
            build_assets_summary(currency_files, "currency"),
        ],
        ignore_index=True,
    )
    if not summary.empty:
        summary.sort_values(["asset_type", "asset"]).to_csv(
            MINED_DIR / "assets_summary.csv", index=False
        )
        print(f"Saved {MINED_DIR / 'assets_summary.csv'}")


if __name__ == "__main__":
    main()
