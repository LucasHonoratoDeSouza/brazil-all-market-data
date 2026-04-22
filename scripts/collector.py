#!/usr/bin/env python3
"""
Brazil All Market Data — Comprehensive data collector.

Focus: maximum Brazilian + global market data, including assets with
low correlation to equities (bonds, real assets, alternatives, volatility).

Data sources:
  - Banco Central do Brasil / SGS API  (via python-bcb)
  - Yahoo Finance                       (via yfinance)

Directories created under data/:
  macro/          BCB macro-economic indicators + PTAX rates
  fixed_income/   BCB fixed-income yields, credit, poupança
  macro_setorial/ BCB sectoral/activity indicators
  equities/
    stocks/       B3 equities — ~130 tickers (OHLCV)
    indices/      B3 indices + key international references
  fiis/           Brazilian real-estate funds — ~75 tickers
  etfs/           B3-listed ETFs — ~30 tickers
  bdrs/           Brazilian Depositary Receipts — ~40 tickers
  currencies/     BRL FX pairs + main crypto (via yfinance)
  commodities/    Commodity futures relevant to Brazil
  bonds/          Fixed-income ETFs — Treasuries, IG, HY, EM, TIPS (low equity corr.)
  real_assets/    Infrastructure, REITs, timber, water, ag ETFs (low equity corr.)
  alternatives/   Thematic, factor, volatility, EM ETFs (low equity corr.)
"""

import os
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from bcb import sgs

# ─── Directory layout ─────────────────────────────────────────────────────────

BASE_DIR              = "data"
MACRO_DIR             = os.path.join(BASE_DIR, "macro")
FIXED_INCOME_DIR      = os.path.join(BASE_DIR, "fixed_income")
MACRO_SETORIAL_DIR    = os.path.join(BASE_DIR, "macro_setorial")
STOCKS_DIR            = os.path.join(BASE_DIR, "equities", "stocks")
INDICES_DIR           = os.path.join(BASE_DIR, "equities", "indices")
FIIS_DIR              = os.path.join(BASE_DIR, "fiis")
ETFS_DIR              = os.path.join(BASE_DIR, "etfs")
BDRS_DIR              = os.path.join(BASE_DIR, "bdrs")
CURRENCIES_DIR        = os.path.join(BASE_DIR, "currencies")
COMMODITIES_DIR       = os.path.join(BASE_DIR, "commodities")
BONDS_DIR             = os.path.join(BASE_DIR, "bonds")
REAL_ASSETS_DIR       = os.path.join(BASE_DIR, "real_assets")
ALTERNATIVES_DIR      = os.path.join(BASE_DIR, "alternatives")

ALL_DIRS = [
    MACRO_DIR, FIXED_INCOME_DIR, MACRO_SETORIAL_DIR,
    STOCKS_DIR, INDICES_DIR,
    FIIS_DIR, ETFS_DIR, BDRS_DIR,
    CURRENCIES_DIR, COMMODITIES_DIR,
    BONDS_DIR, REAL_ASSETS_DIR, ALTERNATIVES_DIR,
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
    "ibc_br":                       24364, # IBC-Br — proxy mensal de atividade
    "producao_industrial":          21859, # PIM-PF — produção industrial (índice)
    "vendas_varejo_pmc":            1455,  # PMC — vendas varejo (índice quantum)
    "confianca_consumidor":         4393,  # ICC FGV — confiança do consumidor
    "confianca_empresarial":        7344,  # ICI FGV — confiança industrial
    # ── Mercado de trabalho ──
    "desemprego_pnad":              24369, # PNAD Contínua — taxa desemprego (%)
    "caged_saldo":                  28763, # CAGED — admissões líquidas
    "rendimento_real_medio":        24382, # Rendimento real médio habitual (R$)
    "salario_minimo":               1619,  # Salário mínimo vigente (R$)
    # ── Setor externo ──
    "exportacoes_fob":              22707, # Exportações FOB (US$ mi)
    "importacoes_fob":              22708, # Importações FOB (US$ mi)
    "saldo_bc":                     22709, # Saldo balança comercial (US$ mi)
    "transacoes_correntes":         22701, # Transações correntes (US$ mi)
    "idp":                          23645, # IDP — investimento direto no país (US$ mi)
    "reservas_internacionais":      3546,  # Reservas internacionais (US$ bi)
    "divida_externa_bruta":         3585,  # Dívida externa bruta total (US$ bi)
    "fluxo_cambial_liquido":        23986, # Fluxo cambial líquido total (US$ mi)
    # ── Fiscal e monetário ──
    "divida_bruta_pib":             4168,  # Dívida bruta governo geral (% PIB)
    "divida_liquida_pib":           2053,  # Dívida líquida setor público (% PIB)
    "resultado_primario_gc":        5793,  # Resultado primário governo central (R$ mi)
    "nfsp_nominal_pib":             4513,  # NFSP nominal (% PIB)
    "arrecadacao_federal":          4320,  # Arrecadação Receita Federal (R$ mi)
    "m1":                           1833,  # M1 (R$ mi)
    "m2":                           1838,  # M2 (R$ mi)
    "m3":                           1840,  # M3 (R$ mi)
    "m4":                           1841,  # M4 (R$ mi)
    # ── PTAX oficial (BCB) ──
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

# ─── BCB Fixed Income + Credit ────────────────────────────────────────────────

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
    "poupanca_captacao_liq":    7453,  # Captação líquida da poupança (R$ mi)
    # ── Crédito — totais ──
    "credito_total":            1406,  # Operações de crédito total (R$ mi)
    "credito_pf":               1403,  # Crédito total — pessoas físicas
    "credito_pj":               1404,  # Crédito total — pessoas jurídicas
    "credito_habitacional":     4464,  # Crédito habitacional total (R$ mi)
    "credito_rural_total":      2085,  # Crédito rural total (R$ mi)
    "concessoes_credito":       1420,  # Novas concessões de crédito (R$ mi)
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

# ─── BCB Sectoral / Activity indicators ──────────────────────────────────────

BCB_SECTORAL_SERIES = {
    # ── Produção física ──
    "producao_veiculos":            7383,  # Produção de veículos (ANFAVEA, unidades)
    "licenciamentos_veiculos":      1374,  # Licenciamentos (Fenabrave, unidades)
    "producao_aco_bruto":           7382,  # Produção de aço bruto (mil toneladas)
    "producao_cimento":             7384,  # Produção de cimento (mil toneladas)
    "producao_papel_papelao":       7386,  # Produção de papel e papelão (toneladas)
    # ── Comércio exterior — detalhe ──
    "exportacoes_basicos":          22765, # Exportações básicos (US$ mi)
    "exportacoes_semimanuf":        22766, # Exportações semimanufaturados (US$ mi)
    "exportacoes_manufaturados":    22767, # Exportações manufaturados (US$ mi)
    # ── Turismo / Serviços ──
    "receitas_turismo":             22709, # placeholder — substituir se necessário
    # ── Mercado imobiliário ──
    "financiamentos_sbpe":          7383,  # SBPE — financiamentos imobiliários — verificar
    # ── Energia ──
    "consumo_energia_industrial":   1406,  # placeholder — verificar código correto
}


def fetch_macro_data():
    print("\n[1/13] Fetching macro & PTAX indicators from BCB/SGS...")
    ensure_dirs()
    for name, code in BCB_MACRO_SERIES.items():
        _fetch_bcb(code, name, MACRO_DIR)


def fetch_fixed_income_data():
    print("\n[2/13] Fetching fixed-income & credit indicators from BCB/SGS...")
    for name, code in BCB_FIXED_INCOME_SERIES.items():
        _fetch_bcb(code, name, FIXED_INCOME_DIR)


def fetch_sectoral_data():
    print("\n[3/13] Fetching sectoral/activity indicators from BCB/SGS...")
    for name, code in BCB_SECTORAL_SERIES.items():
        _fetch_bcb(code, name, MACRO_SETORIAL_DIR)


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


# ─── BRL FX pairs + Crypto ────────────────────────────────────────────────────

CURRENCIES = {
    # ── BRL FX ──
    "usd_brl":   "USDBRL=X",
    "eur_brl":   "EURBRL=X",
    "gbp_brl":   "GBPBRL=X",
    "jpy_brl":   "JPYBRL=X",
    "cny_brl":   "CNYBRL=X",
    "chf_brl":   "CHFBRL=X",
    "aud_brl":   "AUDBRL=X",
    "cad_brl":   "CADBRL=X",
    "mxn_brl":   "MXNBRL=X",
    "ars_brl":   "ARSBRL=X",
    # ── Referência global ──
    "dxy":       "DX-Y.NYB",  # Índice dólar (DXY)
    "eur_usd":   "EURUSD=X",
    # ── Crypto (em BRL e USD) ──
    "btc_brl":   "BTC-BRL",
    "btc_usd":   "BTC-USD",
    "eth_brl":   "ETH-BRL",
    "eth_usd":   "ETH-USD",
    "bnb_usd":   "BNB-USD",
    "sol_usd":   "SOL-USD",
    "xrp_usd":   "XRP-USD",
    "ada_usd":   "ADA-USD",
    "dot_usd":   "DOT-USD",
    "link_usd":  "LINK-USD",
    "matic_usd": "MATIC-USD",
    "avax_usd":  "AVAX-USD",
    "atom_usd":  "ATOM-USD",
}


def fetch_currency_data():
    print("\n[4/13] Fetching BRL FX pairs & crypto from yfinance...")
    for name, ticker in CURRENCIES.items():
        _yf_download(ticker, name, CURRENCIES_DIR)


# ─── Equity indices ───────────────────────────────────────────────────────────

INDICES = {
    # ── Índices B3 ──
    "ibovespa":         "^BVSP",
    "ifix":             "IFIX.SA",
    "small_caps_smll":  "SMLL.SA",
    "idiv_proxy":       "DIVO11.SA",
    "ibrx100_proxy":    "BRAX11.SA",
    "ibov_proxy":       "BOVA11.SA",
    "smal_proxy":       "SMAL11.SA",
    "imat_proxy":       "MATB11.SA",
    # ── Referências internacionais ──
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
    "bovespa_usd_ewz":  "EWZ",       # Brasil em USD (referência internacional)
    # ── Risco / juros ──
    "vix":              "^VIX",
    "tnx_10y":          "^TNX",
    "tyx_30y":          "^TYX",      # Treasury EUA 30 anos
    "irx_13w":          "^IRX",      # T-Bill 13 semanas (taxa livre de risco EUA)
}


def fetch_equity_indices():
    print("\n[5/13] Fetching equity indices...")
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
    print("\n[6/13] Fetching B3 stocks data...")
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
    print("\n[7/13] Fetching FIIs data...")
    for ticker in FIIS:
        name = ticker.replace(".SA", "").lower()
        _yf_download(ticker, name, FIIS_DIR)


# ─── ETFs B3 (~30 tickers) ───────────────────────────────────────────────────

ETFS = {
    # ── Renda variável Brasil ──
    "bova11":   "BOVA11.SA",
    "bovv11":   "BOVV11.SA",
    "smal11":   "SMAL11.SA",
    "divo11":   "DIVO11.SA",
    "brax11":   "BRAX11.SA",
    "matb11":   "MATB11.SA",
    "isus11":   "ISUS11.SA",
    "find11":   "FIND11.SA",
    "util11":   "UTIL11.SA",
    # ── Renda variável internacional (em BRL) ──
    "ivvb11":   "IVVB11.SA",
    "spxi11":   "SPXI11.SA",
    "nasd11":   "NASD11.SA",
    "eurp11":   "EURP11.SA",
    "acwi11":   "ACWI11.SA",
    "wrld11":   "WRLD11.SA",
    "esgb11":   "ESGB11.SA",
    # ── Renda fixa / Tesouro BR ──
    "imab11":   "IMAB11.SA",   # IMA-B (NTN-B — IPCA+)
    "irfm11":   "IRFM11.SA",   # IRF-M (prefixados)
    "b5p211":   "B5P211.SA",   # IMA-B 5+ (NTN-B longas)
    "fixa11":   "FIXA11.SA",   # Pré-fixado curto
    # ── Infraestrutura ──
    "infra11":  "INFRA11.SA",  # Índice de infraestrutura B3
    # ── Commodities / Cripto / Alternativos ──
    "gold11":   "GOLD11.SA",
    "hash11":   "HASH11.SA",
    "comc11":   "COMC11.SA",
    # ── Debentures ──
    "debn11":   "DEBN11.SA",   # ETF de debêntures incentivadas
    "debb11":   "DEBB11.SA",   # ETF de debêntures corporativas
}


def fetch_etfs():
    print("\n[8/13] Fetching B3 ETFs data...")
    for name, ticker in ETFS.items():
        _yf_download(ticker, name, ETFS_DIR)


# ─── BDRs (~40 tickers) ──────────────────────────────────────────────────────

BDRS = {
    # ── Tecnologia ──
    "aapl34":  "AAPL34.SA",
    "msft34":  "MSFT34.SA",
    "amzo34":  "AMZO34.SA",
    "gogl34":  "GOGL34.SA",
    "meta34":  "META34.SA",
    "nvdc34":  "NVDC34.SA",
    "tsla34":  "TSLA34.SA",
    "nflx34":  "NFLX34.SA",
    "uber34":  "UBER34.SA",
    "spot34":  "SPOT34.SA",
    # ── Semicondutores / Hardware ──
    "itlc34":  "ITLC34.SA",
    "csco34":  "CSCO34.SA",
    "orcl34":  "ORCL34.SA",
    "ibmb34":  "IBMB34.SA",
    "qual34":  "QUAL34.SA",
    # ── Financeiro ──
    "jpmc34":  "JPMC34.SA",
    "berk34":  "BERK34.SA",
    "boac34":  "BOAC34.SA",
    "gsgi34":  "GSGI34.SA",
    "msbr34":  "MSBR34.SA",
    "wfco34":  "WFCO34.SA",
    "visa34":  "VISA34.SA",
    "mast34":  "MAST34.SA",
    # ── Saúde / Farma ──
    "jnjb34":  "JNJB34.SA",
    "pfiz34":  "PFIZ34.SA",
    "abtt34":  "ABTT34.SA",
    "mrck34":  "MRCK34.SA",
    "lily34":  "LILY34.SA",
    # ── Consumo ──
    "kofc34":  "KOFC34.SA",
    "pepb34":  "PEPB34.SA",
    "mcdc34":  "MCDC34.SA",
    "nike34":  "NIKE34.SA",
    "disb34":  "DISB34.SA",
    # ── Energia ──
    "xomc34":  "XOMC34.SA",
    "chev34":  "CHEV34.SA",
    "shel34":  "SHEL34.SA",
    "toit34":  "TOIT34.SA",
    # ── Ásia ──
    "baba34":  "BABA34.SA",
    "tsmc34":  "TSMC34.SA",
    "sams34":  "SAMS34.SA",
}


def fetch_bdrs():
    print("\n[9/13] Fetching BDRs data...")
    for name, ticker in BDRS.items():
        _yf_download(ticker, name, BDRS_DIR)


# ─── Commodities relevantes ao Brasil ────────────────────────────────────────

COMMODITIES = {
    # ── Energia ──
    "brent":          "BZ=F",
    "wti":            "CL=F",
    "nat_gas":        "NG=F",
    "ethanol":        "EH=F",     # Etanol — Brasil maior exportador
    "heating_oil":    "HO=F",
    # ── Metais ──
    "gold":           "GC=F",
    "silver":         "SI=F",
    "copper":         "HG=F",
    "aluminum":       "ALI=F",
    "platinum":       "PL=F",
    "palladium":      "PA=F",
    # ── Agrícolas — Brasil líder mundial ──
    "soybeans":       "ZS=F",
    "soybean_oil":    "ZL=F",
    "soybean_meal":   "ZM=F",
    "corn":           "ZC=F",
    "wheat":          "ZW=F",
    "coffee":         "KC=F",
    "sugar":          "SB=F",
    "cotton":         "CT=F",
    "orange_juice":   "OJ=F",
    "cocoa":          "CC=F",
    # ── Pecuária ──
    "live_cattle":    "LE=F",
    "feeder_cattle":  "GF=F",
    "lean_hogs":      "HE=F",
    # ── Madeira / Outros ──
    "lumber":         "LBR=F",
}


def fetch_commodities():
    print("\n[10/13] Fetching commodities data...")
    for name, ticker in COMMODITIES.items():
        _yf_download(ticker, name, COMMODITIES_DIR)


# ─── Bonds / Fixed Income ETFs (baixa correlação com ações) ─────────────────
# Esses ETFs têm correlação historicamente negativa ou baixa com renda variável,
# funcionando como hedge em períodos de risco (risk-off).

BONDS_ETFS = {
    # ── Treasuries EUA (correlação negativa c/ ações em crises) ──
    "shy":    "SHY",     # iShares 1-3yr Treasury Bond
    "ief":    "IEF",     # iShares 7-10yr Treasury Bond
    "tlt":    "TLT",     # iShares 20+ Year Treasury Bond
    "tyx":    "^TYX",    # 30-year yield (série de referência)
    "govt":   "GOVT",    # iShares US Treasury Bond (toda a curva)
    # ── TIPS — proteção contra inflação ──
    "tip":    "TIP",     # iShares TIPS Bond (inflation-linked EUA)
    "stip":   "STIP",    # iShares Short-Term TIPS
    # ── Crédito investment grade ──
    "lqd":    "LQD",     # iShares IG Corporate Bond
    "vcit":   "VCIT",    # Vanguard Intermediate-Term Corp
    "vclt":   "VCLT",    # Vanguard Long-Term Corp
    # ── High yield (correlação maior c/ ações, mas diversifica) ──
    "hyg":    "HYG",     # iShares High Yield Corporate Bond
    "jnk":    "JNK",     # SPDR Bloomberg High Yield
    # ── Bonds de mercados emergentes ──
    "emb":    "EMB",     # iShares JP Morgan EM Bond (USD)
    "lemb":   "LEMB",    # iShares EM Local Currency Bond
    # ── Bonds globais ──
    "bndx":   "BNDX",    # Vanguard Total International Bond
    "iagg":   "IAGG",    # iShares International Aggregate Bond
    # ── Bonds conversíveis / alternativos ──
    "icvt":   "ICVT",    # iShares Convertible Bond
    "bkln":   "BKLN",    # Invesco Senior Loan (floating rate)
    # ── Tesouro Brasil (já coberto em ETFs B3, repetido aqui p/ referência) ──
    "imab11_ref":  "IMAB11.SA",
    "irfm11_ref":  "IRFM11.SA",
}


def fetch_bonds():
    print("\n[11/13] Fetching bonds / fixed-income ETFs (low equity correlation)...")
    for name, ticker in BONDS_ETFS.items():
        _yf_download(ticker, name, BONDS_DIR)


# ─── Real Assets ETFs (baixa correlação / proteção real) ────────────────────
# Ativos reais têm correlação historicamente baixa com ações e funcionam como
# proteção contra inflação: imóveis, infraestrutura, madeira, água, agro.

REAL_ASSETS_ETFS = {
    # ── REITs EUA ──
    "vnq":    "VNQ",     # Vanguard Real Estate (REITs EUA)
    "iyr":    "IYR",     # iShares US Real Estate
    "rem":    "REM",     # iShares Mortgage REIT
    "schh":   "SCHH",    # Schwab US REIT
    # ── REITs internacionais ──
    "reet":   "REET",    # iShares Global REIT
    "ifgl":   "IFGL",    # iShares International Developed Real Estate
    # ── Infraestrutura ──
    "ifra":   "IFRA",    # iShares US Infrastructure
    "pave":   "PAVE",    # Global X US Infrastructure Development
    "igf":    "IGF",     # iShares Global Infrastructure
    "toll":   "TOLL",    # iShares US Transportation Infrastructure
    # ── Madeira / Florestal ──
    "wood":   "WOOD",    # iShares Global Timber & Forestry
    "cut":    "CUT",     # Invesco MSCI Global Timber ETF
    # ── Água ──
    "pho":    "PHO",     # Invesco Water Resources
    "fiw":    "FIW",     # First Trust Water ETF
    "cgw":    "CGW",     # Invesco S&P Global Water
    # ── Agricultura / Farmland ──
    "dba":    "DBA",     # Invesco DB Agriculture Fund
    "soyb":   "SOYB",    # Teucrium Soybean
    "corn_et":"CORN",    # Teucrium Corn
    "cane":   "CANE",    # Teucrium Sugar Cane
    "jo":     "JO",      # iPath Bloomberg Coffee Subindex
    # ── Ouro / Metais preciosos físicos ──
    "gld":    "GLD",     # SPDR Gold Shares (ouro físico)
    "iau":    "IAU",     # iShares Gold Trust
    "gdx":    "GDX",     # VanEck Gold Miners
    "gdxj":   "GDXJ",    # VanEck Junior Gold Miners
    "slv":    "SLV",     # iShares Silver Trust
    "pplt":   "PPLT",    # abrdn Physical Platinum
    # ── Energia real ──
    "uso":    "USO",     # United States Oil Fund
    "ung":    "UNG",     # United States Natural Gas Fund
    "mlp":    "AMLP",    # Alerian MLP ETF (midstream/pipeline)
}


def fetch_real_assets():
    print("\n[12/13] Fetching real assets ETFs (low equity correlation)...")
    for name, ticker in REAL_ASSETS_ETFS.items():
        _yf_download(ticker, name, REAL_ASSETS_DIR)


# ─── Alternative / Thematic ETFs (diversificação e baixa correlação) ────────
# Inclui: volatilidade (hedge), energia limpa, defesa, mercados emergentes,
# fatores (low-vol, momentum, quality, value) e estratégias temáticas.

ALTERNATIVES_ETFS = {
    # ── Volatilidade — correlação negativa com ações ──
    "uvxy":   "UVXY",    # ProShares Ultra VIX Short-Term Futures (long vol)
    "svxy":   "SVXY",    # ProShares Short VIX (short vol)
    "vixm":   "VIXM",    # ProShares VIX Mid-Term Futures
    # ── Setores defensivos (baixa correlação em ciclos de queda) ──
    "xlv":    "XLV",     # SPDR Healthcare
    "xlu":    "XLU",     # SPDR Utilities
    "xlp":    "XLP",     # SPDR Consumer Staples
    "xli":    "XLI",     # SPDR Industrials
    "xlb":    "XLB",     # SPDR Materials
    # ── Energia limpa / Renovável ──
    "icln":   "ICLN",    # iShares Global Clean Energy
    "tan":    "TAN",     # Invesco Solar Energy
    "fan":    "FAN",     # First Trust Global Wind Energy
    "ura":    "URA",     # Global X Uranium/Nuclear
    "qcln":   "QCLN",    # First Trust NASDAQ Clean Edge Green Energy
    # ── Defesa / Aeroespacial ──
    "ita":    "ITA",     # iShares US Aerospace & Defense
    "xar":    "XAR",     # SPDR S&P Aerospace & Defense
    # ── Mercados emergentes ──
    "eem":    "EEM",     # iShares MSCI Emerging Markets
    "vwo":    "VWO",     # Vanguard FTSE Emerging Markets
    "fm":     "FM",      # iShares MSCI Frontier Markets
    "ewz":    "EWZ",     # iShares MSCI Brazil (Brasil em USD)
    "ewy":    "EWY",     # iShares MSCI South Korea
    "inda":   "INDA",    # iShares MSCI India
    "mchi":   "MCHI",    # iShares MSCI China
    "eww":    "EWW",     # iShares MSCI Mexico
    # ── Fatores / Smart Beta ──
    "usmv":   "USMV",    # iShares MSCI Min Volatility (baixa volatilidade)
    "qual":   "QUAL",    # iShares MSCI Quality Factor
    "mtum":   "MTUM",    # iShares MSCI Momentum Factor
    "vlue":   "VLUE",    # iShares MSCI Value Factor
    "size":   "SIZE",    # iShares MSCI Size Factor
    # ── Dividendos (renda estável) ──
    "vym":    "VYM",     # Vanguard High Dividend Yield
    "schd":   "SCHD",    # Schwab US Dividend Equity
    "hdv":    "HDV",     # iShares High Dividend Equity
    # ── Tecnologia emergente ──
    "arkk":   "ARKK",    # ARK Innovation ETF
    "arkg":   "ARKG",    # ARK Genomic Revolution
    "lit":    "LIT",     # Global X Lithium & Battery Tech
    "hack":   "HACK",    # ETFMG Prime Cyber Security
    "robo":   "ROBO",    # ROBO Global Robotics and Automation
    "botz":   "BOTZ",    # Global X Robotics & Artificial Intelligence
    # ── Índices de commodities (diversificação real) ──
    "gsg":    "GSG",     # iShares S&P GSCI Commodity-Indexed
    "pdbc":   "PDBC",    # Invesco Optimum Yield Diversified Commodity
    # ── Outros ──
    "tip2":   "RINF",    # ProShares Inflation Expectations
    "cpi":    "CPI",     # iShares TIPS Bond (curto prazo)
}


def fetch_alternatives():
    print("\n[13/13] Fetching alternative/thematic ETFs (diversification)...")
    for name, ticker in ALTERNATIVES_ETFS.items():
        _yf_download(ticker, name, ALTERNATIVES_DIR)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ensure_dirs()
    fetch_macro_data()        # [1/13] BCB macro + PTAX
    fetch_fixed_income_data() # [2/13] BCB renda fixa + crédito
    fetch_sectoral_data()     # [3/13] BCB setorial + atividade
    fetch_currency_data()     # [4/13] BRL FX + crypto
    fetch_equity_indices()    # [5/13] Índices B3 + referências globais
    fetch_top_stocks()        # [6/13] ~130 ações B3
    fetch_fiis()              # [7/13] ~75 FIIs
    fetch_etfs()              # [8/13] ~30 ETFs B3
    fetch_bdrs()              # [9/13] ~40 BDRs
    fetch_commodities()       # [10/13] Commodities
    fetch_bonds()             # [11/13] Bonds ETFs (baixa correlação c/ ações)
    fetch_real_assets()       # [12/13] Real assets (infra, madeira, água, agro)
    fetch_alternatives()      # [13/13] Temáticos, fatores, volatilidade, EM
    print("\n[collector] All data collection complete.")


if __name__ == "__main__":
    main()

