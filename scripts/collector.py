import os
import pandas as pd
import yfinance as yf
from bcb import sgs
from datetime import datetime, timedelta
import time

# Configure directories
BASE_DIR = "data"
MACRO_DIR = os.path.join(BASE_DIR, "macro")
EQUITIES_DIR = os.path.join(BASE_DIR, "equities")
STOCKS_DIR = os.path.join(EQUITIES_DIR, "stocks")
INDICES_DIR = os.path.join(EQUITIES_DIR, "indices")
CURRENCIES_DIR = os.path.join(BASE_DIR, "currencies")

def ensure_dirs():
    for d in [MACRO_DIR, STOCKS_DIR, INDICES_DIR, CURRENCIES_DIR]:
        os.makedirs(d, exist_ok=True)

def fetch_bcb_series(code, name, start_date="2000-01-01"):
    print(f"Fetching {name} (code {code}) from BCB...")
    try:
        df = sgs.get(code, start=start_date)
        df.to_csv(os.path.join(MACRO_DIR, f"{name}.csv"))
        print(f"Saved {name}.csv")
    except Exception as e:
        if "10 anos" in str(e):
            print(f"10-year limit hit for {name}. Fetching in chunks...")
            all_data = []
            current_start = datetime.strptime(start_date, "%Y-%m-%d")
            end_limit = datetime.now()

            while current_start < end_limit:
                current_end = current_start + timedelta(days=365*10 - 1)
                if current_end > end_limit:
                    current_end = end_limit

                print(f"  Chunk: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}")
                try:
                    chunk = sgs.get(code, start=current_start, end=current_end)
                    if not chunk.empty:
                        all_data.append(chunk)
                except Exception as chunk_e:
                    print(f"  Error in chunk: {chunk_e}")

                current_start = current_end + timedelta(days=1)
                time.sleep(0.5)

            if all_data:
                final_df = pd.concat(all_data)
                final_df = final_df[~final_df.index.duplicated(keep='first')]
                final_df.to_csv(os.path.join(MACRO_DIR, f"{name}.csv"))
                print(f"Saved {name}.csv (chunked)")
        else:
            print(f"Error fetching {name}: {e}")

def fetch_macro_data():
    ensure_dirs()
    codes = {
        "selic_daily": 11,
        "ipca_monthly": 433,
        "cdi_daily": 12,
        "gdp_yearly": 7,
        "exchange_rate_brl_usd": 10813,
        "igp_m": 189,
        "pib_mensal_valor": 4380
    }
    for name, code in codes.items():
        fetch_bcb_series(code, name)

def fetch_currency_data():
    print("Fetching currency data from yfinance...")
    tickers = {
        "usd_brl": "USDBRL=X",
        "eur_brl": "EURBRL=X",
        "btc_usd": "BTC-USD"
    }
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, start="2000-01-01")
            if not df.empty:
                df.to_csv(os.path.join(CURRENCIES_DIR, f"{name}.csv"))
                print(f"Saved {name}.csv")
        except Exception as e:
            print(f"Error fetching {name}: {e}")

def fetch_equity_indices():
    print("Fetching equity indices...")
    indices = {
        "ibovespa": "^BVSP",
        "ifix": "IFIX.SA"
    }
    for name, ticker in indices.items():
        try:
            df = yf.download(ticker, start="2000-01-01")
            if not df.empty:
                df.to_csv(os.path.join(INDICES_DIR, f"{name}.csv"))
                print(f"Saved {name}.csv")
        except Exception as e:
            print(f"Error fetching {name}: {e}")

def fetch_top_stocks():
    print("Fetching top stocks data...")
    stocks = [
        "PETR4.SA", "PETR3.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "ABEV3.SA",
        "B3SA3.SA", "WEGE3.SA", "ITSA4.SA", "JBSS3.SA", "BBAS3.SA", "RENT3.SA",
        "LREN3.SA", "MGLU3.SA", "GGBR4.SA", "CSAN3.SA", "EQTL3.SA", "RADL3.SA",
        "VIVT3.SA", "RAIL3.SA", "SUZB3.SA", "HAPV3.SA", "RDOR3.SA", "PRIO3.SA",
        "EGIE3.SA", "CPLE6.SA", "TRPL4.SA"
    ]
    for ticker in stocks:
        try:
            df = yf.download(ticker, start="2000-01-01")
            if not df.empty:
                df.to_csv(os.path.join(STOCKS_DIR, f"{ticker}.csv"))
                print(f"Saved {ticker}.csv")
            else:
                print(f"No data for {ticker}")
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

def main():
    ensure_dirs()
    fetch_macro_data()
    fetch_currency_data()
    fetch_equity_indices()
    fetch_top_stocks()
    print("Data collection complete.")

if __name__ == "__main__":
    main()
