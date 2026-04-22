#!/usr/bin/env python3
"""
Brazil All Market Data — Comprehensive data collector.

Focus: maximum Brazilian market data coverage.

Data sources:
  - Banco Central do Brasil / SGS API  (via python-bcb)
  - Yahoo Finance                       (via yfinance)

Directories created under data/:
  macro/            BCB macro-economic indicators
  fixed_income/     BCB fixed-income yields, credit, savings
  ptax/             BCB PTAX official exchange rates (all currencies)
  equities/
    stocks/         B3 equities — ~130 tickers (OHLCV)
    indices/        B3 indices + key international references
  fiis/             Brazilian real-estate funds — ~75 tickers
  etfs/             B3-listed ETFs — ~30 tickers (equity, fixed-income, ESG)
  bdrs/             Brazilian Depositary Receipts — ~40 tickers
  currencies/       BRL FX pairs + main crypto (via yfinance)
  commodities/      Commodity futures relevant to Brazil
"""

import os
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from bcb import sgs

# ─── Directory layout ─────────────────────────────────────────────────────────

BASE_DIR          = "data"
MACRO_DIR         = os.path.join(BASE_DIR, "macro")
FIXED_INCOME_DIR  = os.path.join(BASE_DIR, "fixed_income")
PTAX_DIR          = os.path.join(BASE_DIR, "ptax")
STOCKS_DIR        = os.path.join(BASE_DIR, "equities", "stocks")
INDICES_DIR       = os.path.join(BASE_DIR, "equities", "indices")
FIIS_DIR          = os.path.join(BASE_DIR, "fiis")
ETFS_DIR          = os.path.join(BASE_DIR, "etfs")
BDRS_DIR          = os.path.join(BASE_DIR, "bdrs")
CURRENCIES_DIR    = os.path.join(BASE_DIR, "currencies")
COMMODITIES_DIR   = os.path.join(BASE_DIR, "commodities")

ALL_DIRS = [
    MACRO_DIR, FIXED_INCOME_DIR, PTAX_DIR,
    STOCKS_DIR, INDICES_DIR,
    FIIS_DIR, ETFS_DIR, BDRS_DIR,
    CURRENCIES_DIR, COMMODITIES_DIR,
]


def ensure_dirs():
    for d in ALL_DIRS:
        os.makedirs(d, exist_ok=True)


# ─── BCB / SGS helpers ────────────────────────────────────────────────────────

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


# ─── BCB Macro series ─────────────────────────────────────────────────────────

BCB_MACRO_SERIES = {
    # ── Juros ──
    "selic_daily":                  11,    # Meta SELIC diária (% a.a.)
    "cdi_daily":                    12,    # CDI diário (% a.a.)
    "tjlp":                         256,   # TJLP — taxa de juros de longo prazo
    "tlp":                          27572, # TLP — taxa de longo prazo (pós-2018)
    "tr_mensal":                    7168,  # TR — Taxa Referencial mensal
    # ── Inflação ──
    "ipca_monthly":                 433,   # IPCA geral (mensal, %)
    "ipca_acum_12m":                13522, # IPCA acumulado 12 meses (%)
    "ipca_15":                      2289,  # IPCA-15 mensal (%)
    "inpc_monthly":                 188,   # INPC mensal (%)
    "igp_m":                        189,   # IGP-M mensal (%)
    "igp_di":                       190,   # IGP-DI mensal (%)
    "incc_di":                      192,   # INCC-DI — construção civil mensal
    "ipc_fipe":                     193,   # IPC-FIPE mensal (%)
    "ipca_alimentos":               1635,  # IPCA — alimentação e bebidas
    "ipca_habitacao":               1636,  # IPCA — habitação
    "ipca_transportes":             1637,  # IPCA — transportes
    "ipca_saude":                   1638,  # IPCA — saúde
    "ipca_vestuario":               1639,  # IPCA — vestuário
    "ipca_comunicacao":             1640,  # IPCA — comunicação
    "ipca_educacao":                1641,  # IPCA — educação
    "ipca_servicos":                10844, # IPCA — serviços (% mensal)
    # ── Atividade econômica ──
    "gdp_yearly":                   7,     # PIB anual (% variação real)
    "pib_mensal_valor":             4380,  # PIB mensal corrente (R$ milhões)
    "ibc_br":                       24364, # IBC-Br — proxy mensal de atividade (BCB)
    "producao_industrial":          21859, # PIM-PF — produção industrial (índice)
    "vendas_varejo_pmc":            1455,  # PMC — vendas varejo (índice quantum)
    "confianca_consumidor":         4393,  # ICC FGV — confiança do consumidor
    "confianca_empresarial":        7344,  # ICI FGV — confiança industrial
    # ── Mercado de trabalho ──
    "desemprego_pnad":              24369, # PNAD Contínua — taxa desemprego (%)
    "caged_saldo":                  28763, # CAGED — admissões líquidas (emprego formal)
    "rendimento_real_medio":        24382, # Rendimento real médio habitual (R$)
    "salario_minimo":               1619,  # Salário mínimo vigente (R$)
    # ── Setor externo ──
    "exportacoes_fob":              22707, # Exportações FOB (US$ mi)
    "importacoes_fob":              22708, # Importações FOB (US$ mi)
    "saldo_bc":                     22709, # Saldo balança comercial (US$ mi)
    "transacoes_correntes":         22701, # Transações correntes (US$ mi)
    "idp":                          23645, # IDP — investimento direto no país (US$ mi)
    "reservas_internacionais":      3546,  # Reservas internacionais (US$ bi)
    # ── Fiscal e monetário ──
    "divida_bruta_pib":             4168,  # Dívida bruta governo geral (% PIB)
    "divida_liquida_pib":           2053,  # Dívida líquida setor público (% PIB)
    "resultado_primario_gc":        5793,  # Resultado primário governo central (R$ mi)
    "nfsp_nominal_pib":             4513,  # NFSP nominal (% PIB)
    "m1":                           1833,  # M1 (R$ mi)
    "m2":                           1838,  # M2 (R$ mi)
    "m3":                           1840,  # M3 (R$ mi)
    "m4":                           1841,  # M4 (R$ mi)
    # ── Câmbio PTAX oficial ──
    "ptax_usd_venda":               10813, # USD/BRL PTAX venda
    "ptax_eur_venda":               21619, # EUR/BRL PTAX venda
    "ptax_gbp_venda":               21621, # GBP/BRL PTAX venda
    "ptax_jpy_venda":               3698,  # JPY/BRL PTAX venda (100 JPY)
    "ptax_chf_venda":               21623, # CHF/BRL PTAX venda
    "ptax_aud_venda":               21625, # AUD/BRL PTAX venda
    "ptax_cad_venda":               21627, # CAD/BRL PTAX venda
    "ptax_cny_venda":               21631, # CNY/BRL PTAX venda
    "ptax_ars_venda":               3542,  # ARS/BRL PTAX venda
    "ptax_mxn_venda":               3544,  # MXN/BRL PTAX venda (100 MXN)
}

BCB_FIXED_INCOME_SERIES = {
    # ── Títulos públicos federais (yields) ──
    "ltn_6m":                   10199, # LTN 6 meses (% a.a.)
    "ltn_1y":                   10197, # LTN 1 ano (% a.a.)
    "ltn_2y":                   10193, # LTN 2 anos (% a.a.)
    "ntnb_ipca_5y":             11426, # NTN-B 5 anos (IPCA + %)
    "ntnb_ipca_10y":            11427, # NTN-B 10 anos
    "ntnb_ipca_30y":            11428, # NTN-B 30 anos
    "ntnf_10y":                 10187, # NTN-F 10 anos (taxa nominal)
    # ── Poupança ──
    "poupanca_rendimento":      196,   # Rendimento da poupança (% mensal)
    # ── Crédito — totais ──
    "credito_total":            1406,  # Operações de crédito — total (R$ mi)
    "credito_pf":               1403,  # Crédito total — pessoas físicas
    "credito_pj":               1404,  # Crédito total — pessoas jurídicas
    # ── Crédito — custo e inadimplência ──
    "spread_credito_pf":        20714, # Spread crédito PF (p.p.)
    "spread_credito_pj":        20715, # Spread crédito PJ (p.p.)
    "inadimplencia_pf":         21082, # Inadimplência PF (%)
    "inadimplencia_pj":         21083, # Inadimplência PJ (%)
    "taxa_juros_credito_pf":    25497, # Taxa juros crédito pessoal PF (% a.a.)
    "taxa_juros_credito_pj":    20635, # Taxa média crédito PJ (% a.a.)
    # ── Endividamento ──
    "endividamento_familias":   29037, # Endividamento das famílias (% renda)
    "comprometimento_renda":    29038, # Comprometimento de renda c/ serviço da dívida
}


def fetch_macro_data():
    print("\n[1/10] Fetching macro & PTAX indicators from BCB/SGS...")
    ensure_dirs()
    for name, code in BCB_MACRO_SERIES.items():
        _fetch_bcb(code, name, MACRO_DIR)


def fetch_fixed_income_data():
    print("\n[2/10] Fetching fixed-income indicators from BCB/SGS...")
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


# ─── BRL FX pairs + Crypto (via yfinance) ────────────────────────────────────

CURRENCIES = {
    # ── BRL FX ──
    "usd_brl":  "USDBRL=X",
    "eur_brl":  "EURBRL=X",
    "gbp_brl":  "GBPBRL=X",
    "jpy_brl":  "JPYBRL=X",
    "cny_brl":  "CNYBRL=X",
    "chf_brl":  "CHFBRL=X",
    "aud_brl":  "AUDBRL=X",
    "cad_brl":  "CADBRL=X",
    "mxn_brl":  "MXNBRL=X",
    "ars_brl":  "ARSBRL=X",
    # ── Referência global ──
    "dxy":      "DX-Y.NYB",   # Índice dólar (DXY)
    "eur_usd":  "EURUSD=X",
    # ── Crypto (em BRL e USD) ──
    "btc_brl":  "BTC-BRL",
    "btc_usd":  "BTC-USD",
    "eth_brl":  "ETH-BRL",
    "eth_usd":  "ETH-USD",
    "bnb_usd":  "BNB-USD",
    "sol_usd":  "SOL-USD",
    "xrp_usd":  "XRP-USD",
    "ada_usd":  "ADA-USD",
    "dot_usd":  "DOT-USD",
    "link_usd": "LINK-USD",
    "matic_usd":"MATIC-USD",
}


def fetch_currency_data():
    print("\n[3/10] Fetching BRL FX pairs & crypto from yfinance...")
    for name, ticker in CURRENCIES.items():
        _yf_download(ticker, name, CURRENCIES_DIR)


# ─── Equity indices ───────────────────────────────────────────────────────────

INDICES = {
    # ── Índices B3 (diretos / via ETF proxy) ──
    "ibovespa":         "^BVSP",      # Ibovespa
    "ifix":             "IFIX.SA",    # IFIX (FIIs)
    "small_caps_smll":  "SMLL.SA",    # Índice Small Caps
    "idiv_proxy":       "DIVO11.SA",  # IDIV proxy via ETF
    "ibrx100_proxy":    "BRAX11.SA",  # IBrX-100 proxy via ETF
    "ibov_proxy":       "BOVA11.SA",  # Ibovespa proxy via ETF
    "smal_proxy":       "SMAL11.SA",  # Small Caps proxy via ETF
    "imat_proxy":       "MATB11.SA",  # IMAT proxy via ETF
    # ── Referências internacionais (relevantes p/ Brasil) ──
    "sp500":            "^GSPC",
    "nasdaq":           "^IXIC",
    "dow_jones":        "^DJI",
    "russell2000":      "^RUT",
    "ftse100":          "^FTSE",
    "dax":              "^GDAXI",
    "nikkei225":        "^N225",
    "hang_seng":        "^HSI",
    "shanghai":         "000001.SS",
    "eurostoxx50":      "^STOXX50E",
    # ── Risco / juros ──
    "vix":              "^VIX",       # Volatilidade S&P 500
    "tnx_10y":          "^TNX",       # Treasury EUA 10 anos
    "embi_brasil":      "EWZ",        # EWZ como proxy de risco-Brasil (ETF USD)
}


def fetch_equity_indices():
    print("\n[4/10] Fetching equity indices...")
    for name, ticker in INDICES.items():
        _yf_download(ticker, name, INDICES_DIR)


# ─── B3 stocks (~130 tickers) ─────────────────────────────────────────────────

TOP_STOCKS = [
    # ── Petróleo / Energia ──
    "PETR4.SA", "PETR3.SA", "PRIO3.SA", "CSAN3.SA", "VBBR3.SA",
    "RRRP3.SA", "RECV3.SA", "ENGI11.SA", "AURE3.SA",
    # ── Mineração / Siderurgia / Metalurgia ──
    "VALE3.SA", "GGBR4.SA", "CSNA3.SA", "USIM5.SA", "BRAP4.SA",
    "FESA4.SA", "CMIN3.SA", "CBAV3.SA",
    # ── Financeiro / Bancos / Seguros ──
    "ITUB4.SA", "BBDC4.SA", "BBAS3.SA", "ITSA4.SA", "BPAC11.SA",
    "SANB11.SA", "BRSR6.SA", "BMGB4.SA", "ABCB4.SA", "BBDC3.SA",
    "PSSA3.SA", "SULA11.SA", "IRBR3.SA", "CXSE3.SA",
    # ── Fintechs / Bancos digitais ──
    "NUBR33.SA", "INTR3.SA", "XPBR31.SA", "CASH3.SA", "PAGS34.SA",
    # ── Consumo / Varejo / Alimentação ──
    "ABEV3.SA", "LREN3.SA", "MGLU3.SA", "VVAR3.SA", "NTCO3.SA",
    "SOMA3.SA", "ALPA4.SA", "MDIA3.SA", "PCAR3.SA", "ASAI3.SA",
    "CRFB3.SA", "AMAR3.SA", "ARZZ3.SA", "SBFG3.SA", "GMAT3.SA",
    "VIVA3.SA",
    # ── Frigoríficos / Proteínas ──
    "JBSS3.SA", "MRFG3.SA", "BEEF3.SA", "BRFS3.SA",
    # ── Telecom / Mídia ──
    "VIVT3.SA", "TIMS3.SA", "OIBR3.SA",
    # ── Construção civil / Incorporadoras ──
    "CYRE3.SA", "MRVE3.SA", "DIRR3.SA", "EVEN3.SA", "TEND3.SA",
    "EZTC3.SA", "TRIS3.SA", "MTRE3.SA", "MELK3.SA", "JHSF3.SA",
    # ── Shoppings / Imóveis ──
    "MULT3.SA", "IGTI11.SA", "BRPR3.SA",
    # ── Elétrico / Utilities / Saneamento ──
    "EGIE3.SA", "EQTL3.SA", "TAEE11.SA", "CPFE3.SA", "ENBR3.SA",
    "ELET3.SA", "ELET6.SA", "CMIG4.SA", "CPLE6.SA", "SBSP3.SA",
    "SAPR11.SA", "ENEV3.SA", "AESB3.SA",
    # ── Transporte / Logística / Aviação ──
    "RAIL3.SA", "CCRO3.SA", "AZUL4.SA", "GOLL4.SA", "EMBR3.SA",
    "SIMH3.SA", "VAMO3.SA", "MOVI3.SA", "STBP3.SA", "HBSA3.SA",
    # ── Papel / Celulose / Florestal ──
    "SUZB3.SA", "KLBN11.SA", "DTEX3.SA", "RANI3.SA",
    # ── Agronegócio / Açúcar-Etanol ──
    "SLCE3.SA", "AGRO3.SA", "SMTO3.SA", "RAIZ4.SA",
    # ── Saúde / Farmacêuticas / Diagnóstico ──
    "RDOR3.SA", "HAPV3.SA", "RADL3.SA", "HYPE3.SA", "FLRY3.SA",
    "DASA3.SA", "PARD3.SA",
    # ── Tecnologia / Software ──
    "TOTS3.SA", "LWSA3.SA", "INTB3.SA", "SQIA3.SA",
    # ── Veículos / Autopeças ──
    "POMO4.SA", "MYPK3.SA", "FRAS3.SA",
    # ── Educação ──
    "YDUQ3.SA", "COGN3.SA", "SEER3.SA",
    # ── Petroquímica / Química ──
    "UNIP6.SA", "BRKM5.SA",
    # ── Outros ──
    "WEGE3.SA", "B3SA3.SA", "RENT3.SA", "UGPA3.SA", "TRPL4.SA",
    "PETZ3.SA", "DXCO3.SA",
]


def fetch_top_stocks():
    print("\n[5/10] Fetching B3 stocks data...")
    for ticker in TOP_STOCKS:
        _yf_download(ticker, ticker, STOCKS_DIR)


# ─── FIIs (~75 tickers) ───────────────────────────────────────────────────────

FIIS = [
    # ── Logística / Galpões ──
    "HGLG11.SA", "XPLG11.SA", "BRCO11.SA", "LGCP11.SA", "GLOG11.SA",
    "BTLG11.SA", "LVBI11.SA", "VILG11.SA", "PATL11.SA", "XPIN11.SA",
    "RLOG11.SA", "GTLG11.SA", "SDIL11.SA", "GALG11.SA", "LUGG11.SA",
    # ── Lajes corporativas / Escritórios ──
    "KNRI11.SA", "BRCR11.SA", "RBRP11.SA", "PVBI11.SA", "TGAR11.SA",
    "ALZR11.SA", "RECT11.SA", "RCRB11.SA", "VINO11.SA", "JSRE11.SA",
    # ── Shoppings ──
    "XPML11.SA", "VISC11.SA", "HSML11.SA", "MALL11.SA", "HGBS11.SA",
    "WPLZ11.SA", "FVPQ11.SA",
    # ── Recebíveis / CRI / Papel ──
    "MXRF11.SA", "BCFF11.SA", "HFOF11.SA", "VRTA11.SA", "RBRF11.SA",
    "HGCR11.SA", "CSHG11.SA", "VGIP11.SA", "VGHF11.SA", "KNCR11.SA",
    "KNIP11.SA", "IRDM11.SA", "DEVA11.SA", "CPTS11.SA", "MCCI11.SA",
    "RBHY11.SA", "RBVA11.SA", "XPCI11.SA", "RECR11.SA", "CVBI11.SA",
    "VCRI11.SA", "FEXC11.SA", "RBRR11.SA", "RBRY11.SA", "VGIR11.SA",
    "SNCI11.SA", "PLRI11.SA",
    # ── Desenvolvimento / Residencial ──
    "HABT11.SA", "HCTR11.SA",
    # ── Agro / Rural ──
    "RURA11.SA", "GGRC11.SA", "RZTR11.SA",
    # ── Hotelaria / Educacional ──
    "HGRU11.SA", "XPPR11.SA",
    # ── Híbridos / Multiestratégia ──
    "MGFF11.SA", "HGFF11.SA", "BBPO11.SA", "OUJP11.SA",
]


def fetch_fiis():
    print("\n[6/10] Fetching FIIs data...")
    for ticker in FIIS:
        name = ticker.replace(".SA", "").lower()
        _yf_download(ticker, name, FIIS_DIR)


# ─── ETFs B3 (~30 tickers) ───────────────────────────────────────────────────

ETFS = {
    # ── Renda variável Brasil ──
    "bova11":   "BOVA11.SA",   # Ibovespa
    "bovv11":   "BOVV11.SA",   # Ibovespa (variante)
    "smal11":   "SMAL11.SA",   # Small Caps
    "divo11":   "DIVO11.SA",   # IDIV — dividendos
    "brax11":   "BRAX11.SA",   # IBrX-100
    "matb11":   "MATB11.SA",   # IMAT — materiais básicos
    "isus11":   "ISUS11.SA",   # ISE — sustentabilidade
    "find11":   "FIND11.SA",   # IFNC — financeiro
    "util11":   "UTIL11.SA",   # UTIL — utilities
    "acsc11":   "ACSC11.SA",   # Small Caps (outro gestor)
    # ── Renda variável internacional (em BRL) ──
    "ivvb11":   "IVVB11.SA",   # S&P 500 sem hedge
    "spxi11":   "SPXI11.SA",   # S&P 500 com hedge cambial
    "nasd11":   "NASD11.SA",   # Nasdaq 100
    "eurp11":   "EURP11.SA",   # Europa
    "acwi11":   "ACWI11.SA",   # MSCI ACWI (global)
    "wrld11":   "WRLD11.SA",   # MSCI World
    "esgb11":   "ESGB11.SA",   # ESG global
    # ── Renda fixa / Tesouro ──
    "imab11":   "IMAB11.SA",   # IMA-B (NTN-B)
    "irfm11":   "IRFM11.SA",   # IRF-M (prefixados)
    "b5p211":   "B5P211.SA",   # IMA-B 5+ (NTN-B longas)
    "fixa11":   "FIXA11.SA",   # Pré-fixado curto
    # ── Commodities / Alternativos ──
    "gold11":   "GOLD11.SA",   # Ouro (BRL)
    "hash11":   "HASH11.SA",   # Criptoativos
    "comc11":   "COMC11.SA",   # Commodities
}


def fetch_etfs():
    print("\n[7/10] Fetching B3 ETFs data...")
    for name, ticker in ETFS.items():
        _yf_download(ticker, name, ETFS_DIR)


# ─── BDRs — Brazilian Depositary Receipts (~40 tickers) ─────────────────────

BDRS = {
    # ── Tecnologia / FAANG+ ──
    "aapl34":  "AAPL34.SA",   # Apple
    "msft34":  "MSFT34.SA",   # Microsoft
    "amzo34":  "AMZO34.SA",   # Amazon
    "gogl34":  "GOGL34.SA",   # Alphabet (Google)
    "meta34":  "META34.SA",   # Meta (Facebook)
    "nvdc34":  "NVDC34.SA",   # NVIDIA
    "tsla34":  "TSLA34.SA",   # Tesla
    "nflx34":  "NFLX34.SA",   # Netflix
    "uber34":  "UBER34.SA",   # Uber
    "spot34":  "SPOT34.SA",   # Spotify
    # ── Semicondutores / Hardware ──
    "itlc34":  "ITLC34.SA",   # Intel
    "csco34":  "CSCO34.SA",   # Cisco
    "orcl34":  "ORCL34.SA",   # Oracle
    "ibmb34":  "IBMB34.SA",   # IBM
    "qual34":  "QUAL34.SA",   # Qualcomm
    # ── Financeiro / Bancos ──
    "jpmc34":  "JPMC34.SA",   # JPMorgan Chase
    "berk34":  "BERK34.SA",   # Berkshire Hathaway
    "boac34":  "BOAC34.SA",   # Bank of America
    "gsgi34":  "GSGI34.SA",   # Goldman Sachs
    "msbr34":  "MSBR34.SA",   # Morgan Stanley
    "wfco34":  "WFCO34.SA",   # Wells Fargo
    "visa34":  "VISA34.SA",   # Visa
    "mast34":  "MAST34.SA",   # Mastercard
    # ── Saúde / Farma ──
    "jnjb34":  "JNJB34.SA",   # Johnson & Johnson
    "pfiz34":  "PFIZ34.SA",   # Pfizer
    "abtt34":  "ABTT34.SA",   # Abbott
    "mrck34":  "MRCK34.SA",   # Merck
    "lily34":  "LILY34.SA",   # Eli Lilly
    # ── Consumo / Varejo ──
    "kofc34":  "KOFC34.SA",   # Coca-Cola
    "pepb34":  "PEPB34.SA",   # PepsiCo
    "mcdc34":  "MCDC34.SA",   # McDonald's
    "nike34":  "NIKE34.SA",   # Nike
    "disb34":  "DISB34.SA",   # Disney
    "amgn34":  "AMGN34.SA",   # Amgen
    # ── Energia / Petróleo ──
    "xomc34":  "XOMC34.SA",   # ExxonMobil
    "chev34":  "CHEV34.SA",   # Chevron
    "shel34":  "SHEL34.SA",   # Shell
    "toit34":  "TOIT34.SA",   # TotalEnergies
    # ── Ásia ──
    "baba34":  "BABA34.SA",   # Alibaba
    "tsmc34":  "TSMC34.SA",   # TSMC
    "sams34":  "SAMS34.SA",   # Samsung
}


def fetch_bdrs():
    print("\n[8/10] Fetching BDRs data...")
    for name, ticker in BDRS.items():
        _yf_download(ticker, name, BDRS_DIR)


# ─── Commodities relevantes ao Brasil ────────────────────────────────────────

COMMODITIES = {
    # ── Energia ──
    "brent":        "BZ=F",    # Petróleo Brent (USD/barril)
    "wti":          "CL=F",    # Petróleo WTI (USD/barril)
    "nat_gas":      "NG=F",    # Gás natural (USD/MMBtu)
    "ethanol":      "EH=F",    # Etanol (USD/galão) — relevante: Brasil maior exportador
    # ── Metais ──
    "gold":         "GC=F",    # Ouro (USD/oz)
    "silver":       "SI=F",    # Prata
    "copper":       "HG=F",    # Cobre (USD/lb) — Brasil grande produtor
    "iron_ore":     "TIOc1",   # Minério de ferro (USD/t) — VALE
    "aluminum":     "ALI=F",   # Alumínio — CBA/Novelis
    # ── Agrícolas — Brasil é líder mundial ──
    "soybeans":     "ZS=F",    # Soja (USD/bushel) — Brasil #1 exportador
    "corn":         "ZC=F",    # Milho (USD/bushel)
    "wheat":        "ZW=F",    # Trigo
    "coffee":       "KC=F",    # Café arábica (ICE) — Brasil #1 exportador
    "sugar":        "SB=F",    # Açúcar bruto #11 — Brasil #1 exportador
    "cotton":       "CT=F",    # Algodão
    "orange_juice": "OJ=F",    # FCOJ — Brasil maior fornecedor mundial
    "soybean_oil":  "ZL=F",    # Óleo de soja
    "soybean_meal": "ZM=F",    # Farelo de soja
    # ── Pecuária ──
    "live_cattle":  "LE=F",    # Boi gordo (USD/lb) — referência para BGI na B3
    "feeder_cattle":"GF=F",    # Boi magro
    # ── Outros ──
    "lumber":       "LBR=F",   # Madeira serrada
}


def fetch_commodities():
    print("\n[9/10] Fetching commodities data...")
    for name, ticker in COMMODITIES.items():
        _yf_download(ticker, name, COMMODITIES_DIR)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ensure_dirs()
    fetch_macro_data()           # [1/10] BCB macro + PTAX
    fetch_fixed_income_data()    # [2/10] BCB renda fixa + crédito
    fetch_currency_data()        # [3/10] BRL FX + crypto (yfinance)
    fetch_equity_indices()       # [4/10] Índices B3 + referências globais
    fetch_top_stocks()           # [5/10] ~130 ações B3
    fetch_fiis()                 # [6/10] ~75 FIIs
    fetch_etfs()                 # [7/10] ~30 ETFs B3
    fetch_bdrs()                 # [8/10] ~40 BDRs
    fetch_commodities()          # [9/10] Commodities relevantes ao Brasil
    print("\n[collector] All data collection complete.")


if __name__ == "__main__":
    main()
