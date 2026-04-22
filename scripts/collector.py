#!/usr/bin/env python3
"""
Brazil All Market Data — Comprehensive data collector.

Data sources:
  - Banco Central do Brasil / SGS API  (via python-bcb)
  - Yahoo Finance                       (via yfinance)

Directories created under data/:
  macro/          BCB macro-economic indicators
  equities/
    stocks/       B3 equities (OHLCV)
    indices/      Brazilian + international indices
  fiis/           Brazilian real-estate funds (FIIs)
  etfs/           B3-listed ETFs
  currencies/     FX pairs + crypto
  commodities/    International commodity futures
  fixed_income/   Fixed-income indicators (BCB)
"""

import os
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from bcb import sgs

# ─── Directory layout ─────────────────────────────────────────────────────────

BASE_DIR = "data"
MACRO_DIR         = os.path.join(BASE_DIR, "macro")
STOCKS_DIR        = os.path.join(BASE_DIR, "equities", "stocks")
INDICES_DIR       = os.path.join(BASE_DIR, "equities", "indices")
FIIS_DIR          = os.path.join(BASE_DIR, "fiis")
ETFS_DIR          = os.path.join(BASE_DIR, "etfs")
CURRENCIES_DIR    = os.path.join(BASE_DIR, "currencies")
COMMODITIES_DIR   = os.path.join(BASE_DIR, "commodities")
FIXED_INCOME_DIR  = os.path.join(BASE_DIR, "fixed_income")

ALL_DIRS = [
    MACRO_DIR, STOCKS_DIR, INDICES_DIR,
    FIIS_DIR, ETFS_DIR,
    CURRENCIES_DIR, COMMODITIES_DIR, FIXED_INCOME_DIR,
]


def ensure_dirs():
    for d in ALL_DIRS:
        os.makedirs(d, exist_ok=True)


# ─── BCB / SGS series ─────────────────────────────────────────────────────────

# All BCB SGS series to collect.  Key = output filename (without .csv).
BCB_MACRO_SERIES = {
    # Juros
    "selic_daily":              11,    # Taxa SELIC diária
    "cdi_daily":                12,    # Taxa CDI diária
    "tjlp":                     256,   # TJLP (taxa juros longo prazo)
    # Câmbio (BCB PTAX)
    "exchange_rate_brl_usd":    10813, # USD/BRL (PTAX venda)
    # Inflação
    "ipca_monthly":             433,   # IPCA geral mensal
    "ipca_15":                  2289,  # IPCA-15 mensal
    "inpc_monthly":             188,   # INPC mensal
    "igp_m":                    189,   # IGP-M mensal
    "igp_di":                   190,   # IGP-DI mensal
    "incc_di":                  192,   # INCC-DI (construção civil)
    "ipc_fipe":                 193,   # IPC-FIPE mensal
    # Atividade econômica
    "gdp_yearly":               7,     # PIB anual (% variação real)
    "pib_mensal_valor":         4380,  # PIB mensal corrente (R$ milhões)
    "ibc_br":                   24364, # IBC-Br (proxy PIB mensal, BCB)
    # Setor externo
    "exportacoes_fob":          22707, # Exportações FOB (US$ mi)
    "importacoes_fob":          22708, # Importações FOB (US$ mi)
    "saldo_bc":                 22709, # Saldo balança comercial (US$ mi)
    "reservas_internacionais":  3546,  # Reservas internacionais (US$ bi)
    # Fiscal e monetário
    "divida_bruta_pib":         4168,  # Dívida bruta do governo (% PIB)
    "m1":                       1833,  # Base monetária M1 (R$ mi)
    # Mercado de trabalho
    "desemprego_pnad":          24369, # Taxa desemprego PNAD (%)
}

BCB_FIXED_INCOME_SERIES = {
    # Taxas de títulos públicos (NTN-B, LTN) – yields referências BCB
    "ltn_6m":                   10199, # LTN 6 meses (% a.a.)
    "ltn_1y":                   10197, # LTN 1 ano (% a.a.)
    "ltn_2y":                   10193, # LTN 2 anos
    "ntnb_ipca_5y":             11426, # NTN-B 5 anos (IPCA + spread)
    "ntnb_ipca_10y":            11427, # NTN-B 10 anos
    "ntnb_ipca_30y":            11428, # NTN-B 30 anos
    # Spread e crédito
    "spread_credito_pf":        20714, # Spread crédito pessoa física
    "spread_credito_pj":        20715, # Spread crédito pessoa jurídica
    "inadimplencia_pf":         21082, # Inadimplência PF (%)
    "inadimplencia_pj":         21083, # Inadimplência PJ (%)
}


def _fetch_bcb(code: int, name: str, target_dir: str, start_date: str = "2000-01-01") -> None:
    """Download one BCB/SGS series and save as CSV."""
    print(f"  BCB [{code}] {name}...")
    try:
        df = sgs.get(code, start=start_date)
        df.to_csv(os.path.join(target_dir, f"{name}.csv"))
        print(f"    -> saved ({len(df)} rows)")
    except Exception as e:
        err = str(e)
        if "10 anos" in err or "period" in err.lower():
            # API 10-year limit: fetch in chunks
            print(f"    10-year limit hit, chunking...")
            all_chunks = []
            cur = datetime.strptime(start_date, "%Y-%m-%d")
            end_limit = datetime.now()
            while cur < end_limit:
                chunk_end = min(cur + timedelta(days=365 * 10 - 1), end_limit)
                try:
                    chunk = sgs.get(code, start=cur, end=chunk_end)
                    if not chunk.empty:
                        all_chunks.append(chunk)
                except Exception as ce:
                    print(f"    chunk error: {ce}")
                cur = chunk_end + timedelta(days=1)
                time.sleep(0.5)
            if all_chunks:
                final = pd.concat(all_chunks)
                final = final[~final.index.duplicated(keep="first")]
                final.to_csv(os.path.join(target_dir, f"{name}.csv"))
                print(f"    -> saved chunked ({len(final)} rows)")
            else:
                print(f"    no data retrieved")
        else:
            print(f"    error: {e}")


def fetch_macro_data():
    print("\n[1/8] Fetching macro indicators from BCB/SGS...")
    ensure_dirs()
    for name, code in BCB_MACRO_SERIES.items():
        _fetch_bcb(code, name, MACRO_DIR)


def fetch_fixed_income_data():
    print("\n[2/8] Fetching fixed-income indicators from BCB/SGS...")
    for name, code in BCB_FIXED_INCOME_SERIES.items():
        _fetch_bcb(code, name, FIXED_INCOME_DIR)


# ─── Yahoo Finance helper ─────────────────────────────────────────────────────

def _yf_download(ticker: str, name: str, target_dir: str, start: str = "2000-01-01") -> None:
    """Download one Yahoo Finance ticker and save as CSV."""
    print(f"  yfinance [{ticker}] {name}...")
    try:
        df = yf.download(ticker, start=start, progress=False, auto_adjust=False)
        if not df.empty:
            df.to_csv(os.path.join(target_dir, f"{name}.csv"))
            print(f"    -> saved ({len(df)} rows)")
        else:
            print(f"    no data returned")
    except Exception as e:
        print(f"    error: {e}")


# ─── Currencies & Crypto ─────────────────────────────────────────────────────

CURRENCIES = {
    # Fiat BRL pairs
    "usd_brl":  "USDBRL=X",
    "eur_brl":  "EURBRL=X",
    "gbp_brl":  "GBPBRL=X",   # Libra esterlina
    "jpy_brl":  "JPYBRL=X",   # Iene japonês
    "cny_brl":  "CNYBRL=X",   # Yuan chinês
    "chf_brl":  "CHFBRL=X",   # Franco suíço
    "aud_brl":  "AUDBRL=X",   # Dólar australiano
    "cad_brl":  "CADBRL=X",   # Dólar canadense
    "mxn_brl":  "MXNBRL=X",   # Peso mexicano
    "ars_brl":  "ARSBRL=X",   # Peso argentino
    # Cross rates useful for Brazil macro
    "eur_usd":  "EURUSD=X",
    "dxy":      "DX-Y.NYB",   # Índice dólar (DXY)
    # Crypto
    "btc_usd":  "BTC-USD",
    "btc_brl":  "BTC-BRL",
    "eth_usd":  "ETH-USD",
    "eth_brl":  "ETH-BRL",
    "bnb_usd":  "BNB-USD",
    "sol_usd":  "SOL-USD",
    "xrp_usd":  "XRP-USD",
}


def fetch_currency_data():
    print("\n[3/8] Fetching currency & crypto data from yfinance...")
    for name, ticker in CURRENCIES.items():
        _yf_download(ticker, name, CURRENCIES_DIR)


# ─── Equity indices ───────────────────────────────────────────────────────────

INDICES = {
    # Brasil
    "ibovespa":   "^BVSP",
    "ifix":       "IFIX.SA",
    "small_caps": "SMLL.SA",
    # ETF proxies for B3 indices not directly on yfinance
    "ibovespa_etf": "BOVA11.SA",  # proxy IBOV via ETF
    "ibx100_etf":   "BRAX11.SA",  # IBrX-100 proxy
    "small_etf":    "SMAL11.SA",  # small caps proxy
    "divid_etf":    "DIVO11.SA",  # dividends index proxy
    # América
    "sp500":      "^GSPC",
    "nasdaq":     "^IXIC",
    "dow_jones":  "^DJI",
    "russell2000": "^RUT",
    # Europa
    "ftse100":    "^FTSE",
    "dax":        "^GDAXI",
    "cac40":      "^FCHI",
    "eurostoxx50": "^STOXX50E",
    # Ásia
    "nikkei225":  "^N225",
    "shanghai":   "000001.SS",
    "hang_seng":  "^HSI",
    # Volatilidade
    "vix":        "^VIX",
    # Renda fixa EUA
    "tnx_10y":    "^TNX",   # Treasury yield 10 anos
}


def fetch_equity_indices():
    print("\n[4/8] Fetching equity indices...")
    for name, ticker in INDICES.items():
        _yf_download(ticker, name, INDICES_DIR)


# ─── B3 stocks ────────────────────────────────────────────────────────────────

TOP_STOCKS = [
    # ── Energia / Petróleo ──
    "PETR4.SA", "PETR3.SA", "PRIO3.SA", "CSAN3.SA", "VBBR3.SA", "RRRP3.SA",
    "RECV3.SA", "3RCO3.SA",
    # ── Mineração / Siderurgia ──
    "VALE3.SA", "GGBR4.SA", "CSNA3.SA", "USIM5.SA", "BRAP4.SA", "FESA4.SA",
    # ── Financeiro / Bancos ──
    "ITUB4.SA", "BBDC4.SA", "BBAS3.SA", "ITSA4.SA", "BPAC11.SA", "SANB11.SA",
    "BRSR6.SA", "BMGB4.SA", "ABCB4.SA",
    # ── Consumo / Varejo ──
    "ABEV3.SA", "LREN3.SA", "MGLU3.SA", "VVAR3.SA", "NTCO3.SA", "SOMA3.SA",
    "ALPA4.SA", "MDIA3.SA", "PCAR3.SA", "ASAI3.SA", "CRFB3.SA",
    # ── Serviços / Telecom ──
    "VIVT3.SA", "TIMS3.SA", "OIBR3.SA",
    # ── Construção civil / FIIs de tijolo ──
    "CYRE3.SA", "MRVE3.SA", "DIRR3.SA", "EVEN3.SA", "TEND3.SA",
    # ── Elétrico / Utilities ──
    "EGIE3.SA", "EQTL3.SA", "TAEE11.SA", "CPFE3.SA", "ENBR3.SA",
    "ELET3.SA", "ELET6.SA", "CMIG4.SA", "CPLE6.SA", "SBSP3.SA",
    # ── Transporte / Logística ──
    "RAIL3.SA", "CCRO3.SA", "AZUL4.SA", "GOLL4.SA", "EMBR3.SA",
    # ── Papel / Celulose / Agro ──
    "SUZB3.SA", "KLBN11.SA", "DTEX3.SA", "SLCE3.SA", "AGRO3.SA", "SMTO3.SA",
    # ── Saúde / Farma ──
    "RDOR3.SA", "HAPV3.SA", "RADL3.SA", "HYPE3.SA", "FLRY3.SA", "DASA3.SA",
    # ── Tecnologia ──
    "TOTS3.SA", "LWSA3.SA", "INTB3.SA",
    # ── Frigoríficos / Proteínas ──
    "JBSS3.SA", "MRFG3.SA", "BEEF3.SA", "BRFS3.SA",
    # ── Outros ──
    "WEGE3.SA", "B3SA3.SA", "RENT3.SA", "BBDC3.SA", "UGPA3.SA",
    "YDUQ3.SA", "COGN3.SA", "ENEV3.SA", "TRPL4.SA", "PETZ3.SA",
]


def fetch_top_stocks():
    print("\n[5/8] Fetching B3 stocks data...")
    for ticker in TOP_STOCKS:
        _yf_download(ticker, ticker, STOCKS_DIR)


# ─── FIIs (Fundos Imobiliários) ───────────────────────────────────────────────

FIIS = [
    # ── Logística ──
    "HGLG11.SA", "XPLG11.SA", "BRCO11.SA", "LGCP11.SA", "GLOG11.SA",
    # ── Lajes corporativas ──
    "KNRI11.SA", "BRCR11.SA", "RBRP11.SA", "PVBI11.SA", "TGAR11.SA",
    "ALZR11.SA", "RECT11.SA",
    # ── Shoppings ──
    "XPML11.SA", "VISC11.SA", "HSML11.SA", "MALL11.SA", "HGBS11.SA",
    # ── Recebíveis (CRI) ──
    "MXRF11.SA", "BCFF11.SA", "HFOF11.SA", "VRTA11.SA", "RBRF11.SA",
    "HGCR11.SA", "CSHG11.SA", "VGIP11.SA", "VGHF11.SA",
    # ── Agro ──
    "RURA11.SA", "GGRC11.SA",
    # ── Hotelaria ──
    "XPHT11.SA", "HGPO11.SA",
    # ── Outros ──
    "BBPO11.SA", "HGFF11.SA", "OUJP11.SA", "RZTR11.SA",
]


def fetch_fiis():
    print("\n[6/8] Fetching FIIs data...")
    for ticker in FIIS:
        name = ticker.replace(".SA", "").lower()
        _yf_download(ticker, name, FIIS_DIR)


# ─── ETFs listados na B3 ─────────────────────────────────────────────────────

ETFS = {
    # Brasil
    "bova11":  "BOVA11.SA",   # Ibovespa
    "smal11":  "SMAL11.SA",   # Small Caps
    "divo11":  "DIVO11.SA",   # Dividendos
    "brax11":  "BRAX11.SA",   # IBrX-100
    "matb11":  "MATB11.SA",   # Materiais básicos
    "isus11":  "ISUS11.SA",   # ISE (sustentabilidade)
    # Internacional
    "ivvb11":  "IVVB11.SA",   # S&P 500 (BRL, sem hedge)
    "spxi11":  "SPXI11.SA",   # S&P 500 (BRL, com hedge)
    "nasd11":  "NASD11.SA",   # Nasdaq 100
    "eurp11":  "EURP11.SA",   # Ações europeias
    "gold11":  "GOLD11.SA",   # Ouro (BRL)
    "hash11":  "HASH11.SA",   # Criptoativos
}


def fetch_etfs():
    print("\n[7/8] Fetching B3 ETFs data...")
    for name, ticker in ETFS.items():
        _yf_download(ticker, name, ETFS_DIR)


# ─── Commodities (futuros internacionais) ────────────────────────────────────

COMMODITIES = {
    # Energia
    "brent":    "BZ=F",    # Petróleo Brent (USD/barril)
    "wti":      "CL=F",    # Petróleo WTI (USD/barril)
    "nat_gas":  "NG=F",    # Gás natural
    # Metais
    "gold":     "GC=F",    # Ouro (USD/oz)
    "silver":   "SI=F",    # Prata
    "copper":   "HG=F",    # Cobre (USD/lb)
    "aluminum": "ALI=F",   # Alumínio
    # Agrícolas (relevantes para o Brasil)
    "soybeans": "ZS=F",    # Soja (USD/bushel)
    "corn":     "ZC=F",    # Milho
    "wheat":    "ZW=F",    # Trigo
    "coffee":   "KC=F",    # Café arábica (ICE)
    "sugar":    "SB=F",    # Açúcar bruto #11
    "cotton":   "CT=F",    # Algodão
    "orange":   "OJ=F",    # Suco de laranja congelado
}


def fetch_commodities():
    print("\n[8/8] Fetching commodities data...")
    for name, ticker in COMMODITIES.items():
        _yf_download(ticker, name, COMMODITIES_DIR)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ensure_dirs()
    fetch_macro_data()
    fetch_fixed_income_data()
    fetch_currency_data()
    fetch_equity_indices()
    fetch_top_stocks()
    fetch_fiis()
    fetch_etfs()
    fetch_commodities()
    print("\n[collector] All data collection complete.")


if __name__ == "__main__":
    main()
