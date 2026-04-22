#!/usr/bin/env python3
"""
Brazil All Market Data — Maximum coverage collector.

Goal: collect ALL data relevant to the B3 — every asset class listed on
the exchange plus every external variable known to influence Brazilian markets.

Data sources:
  - Banco Central do Brasil / SGS API  (via python-bcb)
  - Yahoo Finance                       (via yfinance)

Directories created under data/:
  macro/            BCB macro indicators + PTAX (55+ series)
  fixed_income/     BCB fixed-income yields, credit, poupança (22+ series)
  macro_setorial/   BCB sectoral activity: industry, services, construction (15+ series)
  equities/
    stocks/         B3 equities — ~290 tickers (OHLCV)
    indices/        B3 indices + global references
  fiis/             Brazilian real-estate funds — ~130 tickers
  etfs/             B3-listed ETFs — ~50 tickers
  bdrs/             Brazilian Depositary Receipts — ~90 tickers
  currencies/       BRL FX pairs + crypto
  commodities/      Commodity futures relevant to Brazil
  global_macro/     External drivers of B3 — China, iron ore, LatAm, US yields,
                    credit spreads, steel, agro majors, volatility indices
  bonds/            Fixed-income ETFs (Treasuries, IG, HY, EM, TIPS)
  real_assets/      Infrastructure, REITs, timber, water, ag ETFs
  alternatives/     Thematic, factor, volatility, EM ETFs
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
from bcb import sgs

# Full history start date used when no local CSV exists yet
_FULL_HISTORY_START = "2000-01-01"

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
GLOBAL_MACRO_DIR      = os.path.join(BASE_DIR, "global_macro")
BONDS_DIR             = os.path.join(BASE_DIR, "bonds")
REAL_ASSETS_DIR       = os.path.join(BASE_DIR, "real_assets")
ALTERNATIVES_DIR      = os.path.join(BASE_DIR, "alternatives")
US_SP500_DIR          = os.path.join(BASE_DIR, "us_equities", "sp500")
EUROPE_DIR            = os.path.join(BASE_DIR, "global_equities", "europe")
ASIA_DIR              = os.path.join(BASE_DIR, "global_equities", "asia")
LATAM_GLOBAL_DIR      = os.path.join(BASE_DIR, "global_equities", "latam")
RATES_DIR             = os.path.join(BASE_DIR, "rates")

ALL_DIRS = [
    MACRO_DIR, FIXED_INCOME_DIR, MACRO_SETORIAL_DIR,
    STOCKS_DIR, INDICES_DIR,
    FIIS_DIR, ETFS_DIR, BDRS_DIR,
    CURRENCIES_DIR, COMMODITIES_DIR,
    GLOBAL_MACRO_DIR,
    BONDS_DIR, REAL_ASSETS_DIR, ALTERNATIVES_DIR,
    US_SP500_DIR, EUROPE_DIR, ASIA_DIR, LATAM_GLOBAL_DIR, RATES_DIR,
]


def ensure_dirs():
    for d in ALL_DIRS:
        os.makedirs(d, exist_ok=True)


# ─── Incremental helpers ──────────────────────────────────────────────────────

def _last_csv_date(csv_path: str) -> Optional[str]:
    """Return the latest date index in an existing CSV as YYYY-MM-DD, or None."""
    if not os.path.exists(csv_path):
        return None
    try:
        # Read only the index column (col 0).  Works for both single-header (BCB)
        # and two-header (yfinance) CSVs because non-date rows parse to NaT.
        raw = pd.read_csv(csv_path, index_col=0, header=0, low_memory=False)
        idx = pd.to_datetime(raw.index, errors="coerce").dropna()
        if idx.empty:
            return None
        return idx.max().strftime("%Y-%m-%d")
    except Exception:
        return None


def _resume_start(csv_path: str, full_start: str) -> tuple[str, bool]:
    """
    Return (effective_start_date, is_incremental).

    If the CSV already exists and has data, returns (day_after_last_row, True).
    Otherwise returns (full_start, False).
    """
    last = _last_csv_date(csv_path)
    if last is None:
        return full_start, False
    next_day = datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)
    today = datetime.now(tz=None).replace(hour=0, minute=0, second=0, microsecond=0)
    if next_day >= today:
        return "", True  # empty string signals "already up to date"
    return next_day.strftime("%Y-%m-%d"), True


# ─── BCB / SGS helpers ────────────────────────────────────────────────────────

def _fetch_bcb(code: int, name: str, target_dir: str, start_date: str = _FULL_HISTORY_START) -> None:
    """Download one BCB/SGS series (incrementally if CSV exists) and save as CSV."""
    csv_path = os.path.join(target_dir, f"{name}.csv")
    effective_start, is_incremental = _resume_start(csv_path, start_date)

    if is_incremental and effective_start == "":
        last = _last_csv_date(csv_path)
        print(f"  BCB [{code}] {name} — up to date ({last})")
        return

    print(f"  BCB [{code}] {name}... (from {effective_start})")

    def _do_fetch(start: str) -> Optional[pd.DataFrame]:
        try:
            return sgs.get(code, start=start)
        except Exception as e:
            err = str(e)
            if "10 anos" in err or "period" in err.lower():
                print(f"    10-year limit hit, chunking...")
                chunks = []
                cur = datetime.strptime(start, "%Y-%m-%d")
                end_limit = datetime.now()
                while cur < end_limit:
                    chunk_end = min(cur + timedelta(days=365 * 10 - 1), end_limit)
                    try:
                        chunk = sgs.get(code, start=cur, end=chunk_end)
                        if not chunk.empty:
                            chunks.append(chunk)
                    except Exception as ce:
                        print(f"    chunk error: {ce}")
                    cur = chunk_end + timedelta(days=1)
                    time.sleep(0.5)
                if chunks:
                    merged = pd.concat(chunks)
                    return merged[~merged.index.duplicated(keep="first")]
                return None
            print(f"    error: {e}")
            return None

    new_df = _do_fetch(effective_start)
    if new_df is None or new_df.empty:
        print(f"    no new data")
        return

    if is_incremental:
        try:
            existing = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            combined = pd.concat([existing, new_df])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
            combined.to_csv(csv_path)
            print(f"    -> appended {len(new_df)} rows (total: {len(combined)})")
            return
        except Exception as e:
            print(f"    append error, overwriting: {e}")

    new_df.to_csv(csv_path)
    print(f"    -> saved ({len(new_df)} rows)")


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
    "ipca_saude":                   1638,  # IPCA — saúde e cuidados pessoais
    "ipca_vestuario":               1639,  # IPCA — vestuário
    "ipca_comunicacao":             1640,  # IPCA — comunicação
    "ipca_educacao":                1641,  # IPCA — educação
    "ipca_servicos":                10844, # IPCA — serviços (% mensal)
    "ipca_bens_industriais":        10843, # IPCA — bens industriais
    # ── Atividade econômica ──
    "gdp_yearly":                   7,     # PIB anual (% variação real)
    "pib_mensal_valor":             4380,  # PIB mensal corrente (R$ milhões)
    "ibc_br":                       24364, # IBC-Br — proxy mensal de atividade
    "producao_industrial":          21859, # PIM-PF — produção industrial (índice)
    "vendas_varejo_pmc":            1455,  # PMC — vendas varejo (índice quantum)
    "vendas_varejo_ampliado":       1479,  # PMC ampliado (inclui veículos e mat. construção)
    "confianca_consumidor":         4393,  # ICC FGV — confiança do consumidor
    "confianca_empresarial":        7344,  # ICI FGV — confiança industrial
    "nuci":                         28694, # NUCI FGV — nível de utilização da cap. instalada
    # ── Mercado de trabalho ──
    "desemprego_pnad":              24369, # PNAD Contínua — taxa desemprego (%)
    "caged_saldo":                  28763, # CAGED — admissões líquidas (emprego formal)
    "rendimento_real_medio":        24382, # Rendimento real médio habitual (R$)
    "salario_minimo":               1619,  # Salário mínimo vigente (R$)
    "massa_salarial":               28544, # Massa de rendimentos habituais (R$ bi)
    # ── Setor externo ──
    "exportacoes_fob":              22707, # Exportações FOB (US$ mi)
    "importacoes_fob":              22708, # Importações FOB (US$ mi)
    "saldo_bc":                     22709, # Saldo balança comercial (US$ mi)
    "transacoes_correntes":         22701, # Transações correntes (US$ mi)
    "idp":                          23645, # IDP — investimento direto no país (US$ mi)
    "reservas_internacionais":      3546,  # Reservas internacionais (US$ bi)
    "divida_externa_bruta":         3585,  # Dívida externa bruta total (US$ bi)
    "fluxo_cambial_liquido":        23986, # Fluxo cambial líquido total (US$ mi)
    "exportacoes_basicos":          22765, # Exportações — básicos (US$ mi)
    "exportacoes_semimanuf":        22766, # Exportações — semimanufaturados (US$ mi)
    "exportacoes_manufaturados":    22767, # Exportações — manufaturados (US$ mi)
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
    # ── PIB componentes pela ótica da demanda ──
    "fbcf_pib":                     22100, # FBCF (% PIB)
    "consumo_familias_pib":         22102, # Consumo das famílias (% PIB)
    "consumo_governo_pib":          22101, # Consumo governo (% PIB)
    "exportacoes_pib_dem":          22103, # Exportações bens/serv (% PIB)
    "importacoes_pib_dem":          22104, # Importações bens/serv (% PIB)
    "poupanca_bruta_pib":           22099, # Poupança bruta (% PIB)
    "pib_trimestral_dessaz":        22109, # PIB trimestral dessazonalizado (R$ mi)
    "ibc_br_dessaz":                24365, # IBC-Br dessazonalizado
    "pms_servicos_volume":          25392, # PMS — volume de serviços (índice)
    # ── Atividade — desagregações industriais ──
    "producao_bens_capital":        21863, # PIM — bens de capital (índice)
    "producao_bens_intermedios":    21864, # PIM — bens intermediários (índice)
    "producao_bens_consumo":        21865, # PIM — bens de consumo (índice)
    "producao_industrial_dessaz":   21862, # PIM dessazonalizado
    # ── Mercado de trabalho — adicionais ──
    "caged_admissoes":              28762, # CAGED — admissões brutas
    "caged_desligamentos":          28761, # CAGED — desligamentos
    "pnad_populacao_ocupada":       24371, # PNAD — população ocupada (mi)
    "pnad_forca_trabalho":          28543, # PNAD — força de trabalho (mi)
    # ── Monetário — adicionais ──
    "base_monetaria":               1408,  # Base monetária (R$ mi)
    "papel_moeda_poder_publico":    1383,  # PMPP — papel-moeda em poder do público
    "reservas_bancarias":           1791,  # Reservas bancárias (R$ mi)
    "nota_credito_bcb":             3034,  # Nota de crédito (% a.a.)
    # ── Fiscal — adicionais ──
    "resultado_primario_estados":   5534,  # Resultado primário estados/municípios (R$ mi)
    "juros_nominais_nfsp":          4512,  # Juros nominais NFSP (R$ mi)
    "divida_mob_federal":           4182,  # Dívida mobiliária federal (R$ bi)
    "receita_total_gc":             7442,  # Receita total governo central (R$ mi)
    "despesa_total_gc":             7443,  # Despesa total governo central (R$ mi)
    "transferencias_constitucionais": 7428, # Transferências constitucionais (R$ mi)
    # ── Setor externo — adicionais ──
    "exportacoes_commodities_agro": 22768, # Exportações — commodities agro (US$ mi)
    "importacoes_combustiveis":     22714, # Importações — combustíveis (US$ mi)
    "importacoes_bens_capital":     22711, # Importações — bens de capital (US$ mi)
    "remessas_lucros_dividendos":   22706, # Remessas lucros/dividendos (US$ mi)
    "turismo_receitas":             13091, # Turismo — receitas (US$ mi)
    "turismo_despesas":             13092, # Turismo — despesas (US$ mi)
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
    # ── Taxas de juros por modalidade (% a.m.) ──
    "juros_cheque_especial_pf":     20456, # Cheque especial PF (% a.m.)
    "juros_cartao_rotativo_pf":     20447, # Cartão de crédito rotativo PF (% a.m.)
    "juros_consignado_pf":          20446, # Crédito consignado PF (% a.m.)
    "juros_veiculo_pf":             20448, # Financiamento de veículos PF (% a.m.)
    "juros_imobiliario_pf":         20435, # Financiamento imobiliário PF (% a.m.)
    "juros_capital_giro_pj":        20439, # Capital de giro PJ (% a.m.)
    "juros_desconto_duplicatas_pj": 20440, # Desconto de duplicatas PJ (% a.m.)
    "juros_conta_garantida_pj":     20441, # Conta garantida PJ (% a.m.)
    # ── Inadimplência por modalidade ──
    "inadimpl_cheque_especial":     21096, # Inadimplência cheque especial (%)
    "inadimpl_cartao_credito":      21100, # Inadimplência cartão de crédito (%)
    "inadimpl_veiculo_pf":          21097, # Inadimplência veículos PF (%)
    "inadimpl_capital_giro_pj":     21101, # Inadimplência capital de giro PJ (%)
    # ── Crédito por modalidade — saldos ──
    "credito_cheque_especial":      20589, # Cheque especial — saldo (R$ mi)
    "credito_cartao_credito":       20588, # Cartão de crédito — saldo (R$ mi)
    "credito_consignado_saldo":     20590, # Consignado — saldo (R$ mi)
    "credito_veiculos_pf":          20591, # Veículos PF — saldo (R$ mi)
    "credito_imobiliario_pf":       20592, # Imobiliário PF — saldo (R$ mi)
    "credito_capital_giro":         20600, # Capital de giro PJ — saldo (R$ mi)
    # ── Títulos públicos — adicionais ──
    "ltn_3m":                       10204, # LTN 3 meses (% a.a.)
    "ltn_4y":                       10191, # LTN 4 anos (% a.a.)
    "ntnf_3y":                      10189, # NTN-F 3 anos
    "ntnf_5y":                      10188, # NTN-F 5 anos
    "selic_meta_copom":             432,   # Meta Selic reunião COPOM (% a.a.)
    "selic_over_mensal":            1178,  # Taxa Selic over acumulada no mês (% a.m.)
    # ── Mercado de capitais ──
    "emissao_debentures":           4440,  # Emissão de debêntures (R$ mi)
}


# ─── BCB Sectoral / Activity indicators ──────────────────────────────────────

BCB_SECTORAL_SERIES = {
    # ── Indústria — produção física ──
    "producao_veiculos":            1374,  # Licenciamentos Fenabrave (unidades)
    "producao_aco_bruto":           7382,  # Produção de aço bruto (mil toneladas)
    "producao_cimento":             7384,  # Produção de cimento (mil toneladas)
    "producao_papel_papelao":       7386,  # Produção de papel e papelão (toneladas)
    "extracao_petroleo":            7388,  # Extração de petróleo (mil barris/dia)
    "geracao_energia_eletrica":     7415,  # Geração de energia elétrica (GWh)
    # ── Confiança e utilização ──
    "nuci_industria":               28694, # NUCI FGV — cap. instalada industrial (%)
    "confianca_comercio":           28745, # ICS FGV — confiança do comércio
    "confianca_servicos":           24352, # ICS FGV — confiança do setor de serviços
    "confianca_construcao":         24283, # ICST FGV — confiança da construção civil
    # ── Crédito setorial ──
    "credito_habitacional_sbpe":    4464,  # SBPE — financiamentos (R$ mi)
    "credito_consignado":           25060, # Crédito consignado total (R$ mi)
    # ── Produção agropecuária ──
    "producao_soja_ibge":           7391,  # Produção de soja (mil toneladas)
    "producao_milho_ibge":          7392,  # Produção de milho (mil toneladas)
    "producao_cana_ibge":           7393,  # Produção de cana-de-açúcar (mil toneladas)
    # ── Setor externo setorial ──
    "exportacoes_soja":             22769, # Exportações de soja em grão (US$ mi)
    "exportacoes_petroleo_derivados": 22770, # Exportações petróleo e derivados (US$ mi)
    "exportacoes_minério_ferro":    22771, # Exportações de minério de ferro (US$ mi)
    "exportacoes_carne":            22772, # Exportações de carne bovina (US$ mi)
    "exportacoes_celulose":         22773, # Exportações de celulose (US$ mi)
    "exportacoes_cafe":             22774, # Exportações de café (US$ mi)
    "exportacoes_acucar":           22775, # Exportações de açúcar (US$ mi)
    # ── Energia ──
    "consumo_energia_industrial":   1402,  # Consumo de energia elétrica — industrial (GWh)
    "consumo_energia_residencial":  1401,  # Consumo de energia elétrica — residencial (GWh)
    # ── Construção civil ──
    "licencas_construcao":          7390,  # Licenças construção civil (índice)
    "producao_insumos_construcao":  7389,  # Produção de insumos para construção
    # ── Serviços ──
    "pms_receita_servicos":         25406, # PMS — receita nominal serviços (índice)
    "pms_servicos_transportes":     25419, # PMS — transportes
    "pms_servicos_informacao":      25421, # PMS — informação e comunicação
    "pms_servicos_profissionais":   25422, # PMS — atividades profissionais
}


def fetch_macro_data():
    print("\n[ 1/19] Fetching macro & PTAX indicators from BCB/SGS...")
    ensure_dirs()
    for name, code in BCB_MACRO_SERIES.items():
        _fetch_bcb(code, name, MACRO_DIR)


def fetch_fixed_income_data():
    print("\n[ 2/19] Fetching fixed-income & credit indicators from BCB/SGS...")
    for name, code in BCB_FIXED_INCOME_SERIES.items():
        _fetch_bcb(code, name, FIXED_INCOME_DIR)


def fetch_sectoral_data():
    print("\n[ 3/19] Fetching sectoral/activity indicators from BCB/SGS...")
    for name, code in BCB_SECTORAL_SERIES.items():
        _fetch_bcb(code, name, MACRO_SETORIAL_DIR)


# ─── Yahoo Finance helper ─────────────────────────────────────────────────────

def _yf_download(ticker: str, name: str, target_dir: str, start: str = _FULL_HISTORY_START) -> None:
    """Download one yfinance ticker (incrementally if CSV exists) and save as CSV."""
    csv_path = os.path.join(target_dir, f"{name}.csv")
    effective_start, is_incremental = _resume_start(csv_path, start)

    if is_incremental and effective_start == "":
        last = _last_csv_date(csv_path)
        print(f"  yfinance [{ticker}] — up to date ({last})")
        return

    print(f"  yfinance [{ticker}] {name}... (from {effective_start})")
    try:
        new_df = yf.download(ticker, start=effective_start, progress=False, auto_adjust=False)
        if new_df.empty:
            print(f"    no new data")
            return

        if is_incremental:
            try:
                # yfinance CSVs use a two-row header (Price + Ticker)
                existing = pd.read_csv(csv_path, header=[0, 1], index_col=0)
                existing.index = pd.to_datetime(existing.index, errors="coerce")
                existing = existing[existing.index.notna()]
                combined = pd.concat([existing, new_df])
                combined = combined[~combined.index.duplicated(keep="last")].sort_index()
                combined.to_csv(csv_path)
                print(f"    -> appended {len(new_df)} rows (total: {len(combined)})")
                return
            except Exception as e:
                print(f"    append error, overwriting: {e}")

        new_df.to_csv(csv_path)
        print(f"    -> saved ({len(new_df)} rows)")
    except Exception as e:
        print(f"    error: {e}")


# ─── BRL FX pairs + Crypto ────────────────────────────────────────────────────

CURRENCIES = {
    # ── BRL FX ──
    "usd_brl":    "USDBRL=X",
    "eur_brl":    "EURBRL=X",
    "gbp_brl":    "GBPBRL=X",
    "jpy_brl":    "JPYBRL=X",
    "cny_brl":    "CNYBRL=X",
    "chf_brl":    "CHFBRL=X",
    "aud_brl":    "AUDBRL=X",
    "cad_brl":    "CADBRL=X",
    "mxn_brl":    "MXNBRL=X",
    "ars_brl":    "ARSBRL=X",
    "clp_brl":    "CLPBRL=X",   # Peso chileno
    "cop_brl":    "COPBRL=X",   # Peso colombiano
    "try_brl":    "TRYBRL=X",   # Lira turca (peer EM)
    "zar_brl":    "ZARBRL=X",   # Rand sul-africano (peer EM)
    "rub_brl":    "RUBBRL=X",   # Rublo (peer commodities)
    # ── Cross rates ──
    "dxy":        "DX-Y.NYB",   # Índice dólar DXY
    "eur_usd":    "EURUSD=X",
    "usd_cny":    "USDCNY=X",   # Dólar-Yuan (chave para commodities)
    # ── Crypto em BRL e USD ──
    "btc_brl":    "BTC-BRL",
    "btc_usd":    "BTC-USD",
    "eth_brl":    "ETH-BRL",
    "eth_usd":    "ETH-USD",
    "bnb_usd":    "BNB-USD",
    "sol_usd":    "SOL-USD",
    "xrp_usd":    "XRP-USD",
    "ada_usd":    "ADA-USD",
    "dot_usd":    "DOT-USD",
    "link_usd":   "LINK-USD",
    "matic_usd":  "MATIC-USD",
    "avax_usd":   "AVAX-USD",
    "atom_usd":   "ATOM-USD",
    "ltc_usd":    "LTC-USD",
    "usdt_brl":   "USDT-BRL",
    # ── Mais criptoativos ──
    "doge_usd":   "DOGE-USD",
    "shib_usd":   "SHIB-USD",
    "trx_usd":    "TRX-USD",
    "xlm_usd":    "XLM-USD",
    "near_usd":   "NEAR-USD",
    "icp_usd":    "ICP-USD",
    "algo_usd":   "ALGO-USD",
    "apt_usd":    "APT-USD",
    "arb_usd":    "ARB-USD",
    "op_usd":     "OP-USD",
    "inj_usd":    "INJ-USD",
    "sui_usd":    "SUI20947-USD",
    "sei_usd":    "SEI-USD",
    "fil_usd":    "FIL-USD",
    "hbar_usd":   "HBAR-USD",
    "grt_usd":    "GRT-USD",
    "sand_usd":   "SAND-USD",
    "mana_usd":   "MANA-USD",
    "axs_usd":    "AXS-USD",
    "imx_usd":    "IMX-USD",
    "stx_usd":    "STX-USD",
    "aave_usd":   "AAVE-USD",
    "uni_usd":    "UNI-USD",
    "mkr_usd":    "MKR-USD",
    "snx_usd":    "SNX-USD",
    "crv_usd":    "CRV-USD",
    "ldo_usd":    "LDO-USD",
    "wbtc_usd":   "WBTC-USD",
    "steth_usd":  "STETH-USD",
    # ── FX cross rates adicionais ──
    "usd_jpy":    "USDJPY=X",
    "usd_chf":    "USDCHF=X",
    "usd_aud":    "USDAUD=X",
    "usd_brl":    "USDBRL=X",  # também como cross explícito
    "gbp_usd":    "GBPUSD=X",
    "usd_inr":    "USDINR=X",  # Rúpia indiana
    "usd_krw":    "USDKRW=X",  # Won coreano
    "usd_mxn":    "USDMXN=X",  # Peso mexicano
    "usd_clp":    "USDCLP=X",  # Peso chileno
    "usd_ars":    "USDARS=X",  # Peso argentino
    "usd_try":    "USDTRY=X",  # Lira turca
    "usd_zar":    "USDZAR=X",  # Rand sul-africano
    "usd_rub":    "USDRUB=X",  # Rublo
    "usd_idr":    "USDIDR=X",  # Rupia indonésia
}


def fetch_currency_data():
    print("\n[ 4/19] Fetching BRL FX pairs & crypto from yfinance...")
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
    "ifnc_proxy":       "FIND11.SA",
    "iutil_proxy":      "UTIL11.SA",
    # ── Referências globais ──
    "sp500":            "^GSPC",
    "nasdaq":           "^IXIC",
    "dow_jones":        "^DJI",
    "russell2000":      "^RUT",
    "ftse100":          "^FTSE",
    "dax":              "^GDAXI",
    "cac40":            "^FCHI",
    "nikkei225":        "^N225",
    "hang_seng":        "^HSI",
    "shanghai":         "000001.SS",
    "eurostoxx50":      "^STOXX50E",
    "msci_em":          "EEM",       # EM (via ETF)
    "msci_latam":       "ILF",       # América Latina (via ETF)
    "bovespa_usd":      "EWZ",       # Brasil em USD
    # ── Risco / Juros / Volatilidade ──
    "vix":              "^VIX",
    "tnx_10y":          "^TNX",
    "tyx_30y":          "^TYX",
    "fvx_5y":           "^FVX",
    "irx_3m":           "^IRX",
}


def fetch_equity_indices():
    print("\n[5/14] Fetching equity indices...")
    for name, ticker in INDICES.items():
        _yf_download(ticker, name, INDICES_DIR)


# ─── B3 stocks — IBrX-200 + SMLL + outros líquidos (~290 tickers) ─────────────

TOP_STOCKS = [
    # ── Petróleo / Energia / Gás ──
    "PETR4.SA", "PETR3.SA", "PRIO3.SA", "CSAN3.SA", "VBBR3.SA",
    "RRRP3.SA", "RECV3.SA", "RPMG3.SA", "CGAS3.SA", "CGAS5.SA",
    "3RCO3.SA", "LEVE3.SA", "PTNT3.SA",
    # ── Energia elétrica / Renováveis / Utilities ──
    "EGIE3.SA", "EQTL3.SA", "TAEE11.SA", "CPFE3.SA", "ENBR3.SA",
    "ELET3.SA", "ELET6.SA", "CMIG4.SA", "CMIG3.SA", "CPLE6.SA",
    "CPLE3.SA", "SBSP3.SA", "SAPR11.SA", "SAPR3.SA", "SAPR4.SA",
    "ENEV3.SA", "AESB3.SA", "NEOE3.SA", "ALUP11.SA", "ALUP3.SA",
    "AURE3.SA", "ENGI11.SA", "ENGI3.SA", "ENGI4.SA", "EQPA3.SA",
    "EQPA7.SA", "TRPL4.SA", "TRPL3.SA", "EMAE3.SA", "CEEB3.SA",
    "COCE5.SA", "CLSC4.SA", "CLSC3.SA", "CSMG3.SA", "GEPA4.SA",
    "GEPA3.SA", "DESA3.SA",
    # ── Saneamento ──
    "CSBR3.SA", "AMBP3.SA",
    # ── Mineração / Siderurgia / Metalurgia ──
    "VALE3.SA", "VALE5.SA", "GGBR4.SA", "GGBR3.SA", "GOAU4.SA",
    "GOAU3.SA", "CSNA3.SA", "USIM5.SA", "USIM3.SA", "BRAP4.SA",
    "BRAP3.SA", "FESA4.SA", "FESA3.SA", "CMIN3.SA", "CBAV3.SA",
    "MOAR3.SA", "HBOR3.SA",
    # ── Petroquímica / Química ──
    "UNIP6.SA", "UNIP3.SA", "BRKM5.SA", "BRKM3.SA",
    # ── Financeiro / Bancos ──
    "ITUB4.SA", "ITUB3.SA", "BBDC4.SA", "BBDC3.SA", "BBAS3.SA",
    "BBAS11.SA", "ITSA4.SA", "ITSA3.SA", "BPAC11.SA", "BPAC3.SA",
    "SANB11.SA", "SANB3.SA", "SANB4.SA", "BRSR6.SA", "BRSR3.SA",
    "BRSR5.SA", "BMGB4.SA", "BMGB3.SA", "ABCB4.SA", "ABCB3.SA",
    "BPAN4.SA", "PINE4.SA", "PINE3.SA", "MODL3.SA", "BRGE7.SA",
    "BMEB4.SA", "BMEB3.SA",
    # ── Seguros / Previdência ──
    "PSSA3.SA", "SULA11.SA", "IRBR3.SA", "CXSE3.SA", "BBSE3.SA",
    "WIZS3.SA", "ODPV3.SA", "QUAL3.SA",
    # ── Fintechs / Bancos digitais ──
    "NUBR33.SA", "INTR3.SA", "XPBR31.SA", "CASH3.SA", "PAGS34.SA",
    "MELI34.SA",
    # ── Consumo / Varejo / Alimentação ──
    "ABEV3.SA", "LREN3.SA", "MGLU3.SA", "VVAR3.SA", "NTCO3.SA",
    "SOMA3.SA", "ALPA4.SA", "ALPA3.SA", "MDIA3.SA", "PCAR3.SA",
    "ASAI3.SA", "CRFB3.SA", "AMAR3.SA", "ARZZ3.SA", "SBFG3.SA",
    "GMAT3.SA", "VIVA3.SA", "VIVR3.SA", "GRND3.SA", "CEAB3.SA",
    "VULC3.SA", "CGRA4.SA", "ESPA3.SA", "VSTE3.SA", "LLIS3.SA",
    "HGTX3.SA", "MOVI3.SA", "JALL3.SA", "CAMB3.SA", "DOHL4.SA",
    "FHER3.SA",
    # ── Frigoríficos / Proteínas ──
    "JBSS3.SA", "MRFG3.SA", "BEEF3.SA", "BRFS3.SA", "CAML3.SA",
    # ── Agronegócio / Açúcar-Etanol / Grãos ──
    "SLCE3.SA", "AGRO3.SA", "SMTO3.SA", "RAIZ4.SA", "TTEN3.SA",
    "LAND3.SA", "LJQQ3.SA", "SLC3.SA", "SOJA3.SA",
    # ── Papel / Celulose / Florestal ──
    "SUZB3.SA", "KLBN11.SA", "KLBN3.SA", "KLBN4.SA", "DTEX3.SA",
    "RANI3.SA", "DXCO3.SA",
    # ── Telecom / Mídia / Tecnologia ──
    "VIVT3.SA", "TIMS3.SA", "OIBR3.SA", "TOTS3.SA", "LWSA3.SA",
    "INTB3.SA", "SQIA3.SA", "BSEV3.SA", "SEQL3.SA", "ROMI3.SA",
    "NGRD3.SA",
    # ── Construção civil / Incorporadoras ──
    "CYRE3.SA", "MRVE3.SA", "DIRR3.SA", "EVEN3.SA", "TEND3.SA",
    "EZTC3.SA", "TRIS3.SA", "MTRE3.SA", "MELK3.SA", "JHSF3.SA",
    "LAVV3.SA", "CALI3.SA", "CALI4.SA", "HELN3.SA", "TFCO4.SA",
    "RSID3.SA", "GFSA3.SA", "PLPL3.SA",
    # ── Shoppings / Imóveis listados ──
    "MULT3.SA", "IGTI11.SA", "BRPR3.SA", "ALSO3.SA",
    # ── Transporte / Logística / Aviação / Portos ──
    "RAIL3.SA", "CCRO3.SA", "AZUL4.SA", "GOLL4.SA", "EMBR3.SA",
    "SIMH3.SA", "VAMO3.SA", "STBP3.SA", "HBSA3.SA", "LOGG3.SA",
    "JSLG3.SA", "TGMA3.SA", "TPIS3.SA", "AZEV4.SA", "PSSA3.SA",
    # ── Saúde / Farmacêuticas / Diagnóstico ──
    "RDOR3.SA", "HAPV3.SA", "RADL3.SA", "HYPE3.SA", "FLRY3.SA",
    "DASA3.SA", "PARD3.SA", "GNDI3.SA", "BLAU3.SA", "AALR3.SA",
    "MATD3.SA", "OPCT3.SA",
    # ── Educação ──
    "YDUQ3.SA", "COGN3.SA", "SEER3.SA", "ANIM3.SA",
    # ── Veículos / Autopeças ──
    "POMO4.SA", "POMO3.SA", "MYPK3.SA", "FRAS3.SA", "TUPY3.SA",
    "RAPT4.SA", "RAPT3.SA",
    # ── Outros ──
    "WEGE3.SA", "B3SA3.SA", "RENT3.SA", "UGPA3.SA", "PETZ3.SA",
    "KEPL3.SA", "TASA4.SA", "TASA3.SA", "VLID3.SA", "SHOW3.SA",
    "SHUL4.SA", "KRSA3.SA", "BRML3.SA",
]


def fetch_top_stocks():
    print("\n[6/14] Fetching B3 stocks data...")
    for ticker in TOP_STOCKS:
        _yf_download(ticker, ticker, STOCKS_DIR)


# ─── FIIs — cobertura máxima (~130 tickers) ───────────────────────────────────

FIIS = [
    # ── Logística / Galpões ──
    "HGLG11.SA", "XPLG11.SA", "BRCO11.SA", "LGCP11.SA", "GLOG11.SA",
    "BTLG11.SA", "LVBI11.SA", "VILG11.SA", "PATL11.SA", "XPIN11.SA",
    "RLOG11.SA", "GTLG11.SA", "SDIL11.SA", "GALG11.SA", "LUGG11.SA",
    "LOGG11.SA", "TRXF11.SA", "WLOG11.SA", "ALZR11.SA",
    # ── Lajes corporativas / Escritórios ──
    "KNRI11.SA", "BRCR11.SA", "RBRP11.SA", "PVBI11.SA", "TGAR11.SA",
    "RECT11.SA", "RCRB11.SA", "VINO11.SA", "JSRE11.SA", "BROF11.SA",
    "EDGA11.SA", "ONEF11.SA", "SARE11.SA",
    # ── Shoppings ──
    "XPML11.SA", "VISC11.SA", "HSML11.SA", "MALL11.SA", "HGBS11.SA",
    "WPLZ11.SA", "FVPQ11.SA", "JRPT11.SA", "ABCP11.SA",
    # ── Recebíveis / CRI / Papel ──
    "MXRF11.SA", "BCFF11.SA", "HFOF11.SA", "VRTA11.SA", "RBRF11.SA",
    "HGCR11.SA", "CSHG11.SA", "VGIP11.SA", "VGHF11.SA", "KNCR11.SA",
    "KNIP11.SA", "IRDM11.SA", "DEVA11.SA", "CPTS11.SA", "MCCI11.SA",
    "RBHY11.SA", "RBVA11.SA", "XPCI11.SA", "RECR11.SA", "CVBI11.SA",
    "VCRI11.SA", "FEXC11.SA", "RBRR11.SA", "RBRY11.SA", "VGIR11.SA",
    "SNCI11.SA", "PLRI11.SA", "AFCR11.SA", "BCRI11.SA", "BTCR11.SA",
    "FLCR11.SA", "GCRI11.SA", "HCRI11.SA", "MGCR11.SA", "NCHB11.SA",
    "NPAR11.SA", "PEBB11.SA", "RBCO11.SA", "RFOF11.SA", "RIET11.SA",
    "RVBI11.SA", "SADI11.SA", "TFOF11.SA", "URPR11.SA", "VCJR11.SA",
    "VCRR11.SA", "XPCA11.SA", "XPCM11.SA", "XPCO11.SA",
    # ── Desenvolvimento / Residencial ──
    "HABT11.SA", "HCTR11.SA", "HOSI11.SA", "MINT11.SA", "PORD11.SA",
    # ── Agro / Rural / CRA ──
    "RURA11.SA", "GGRC11.SA", "RZTR11.SA", "RZAG11.SA",
    # ── Hotelaria / Educacional / Hospitalar ──
    "HGRU11.SA", "XPPR11.SA", "HTMX11.SA", "BBPO11.SA",
    # ── Híbridos / Fundos de fundos / Multiestratégia ──
    "MGFF11.SA", "HGFF11.SA", "OUJP11.SA", "BCFF11.SA", "HFOF11.SA",
    "RBRF11.SA", "FIIB11.SA", "MFII11.SA", "KFOF11.SA",
    # ── Outros segmentos / Mid-small ──
    "BLMG11.SA", "BOTT11.SA", "CJCT11.SA", "CYCR11.SA", "DVFF11.SA",
    "FIIP11.SA", "FLFL11.SA", "FOFT11.SA", "HIOF11.SA", "HMOC11.SA",
    "LASC11.SA", "MMVE11.SA", "NEWL11.SA", "PABY11.SA", "PFIN11.SA",
    "PNDL11.SA", "RBDS11.SA", "RBRM11.SA", "RBTS11.SA", "RODG11.SA",
    "RSPD11.SA", "SEQR11.SA", "TPFT11.SA", "TVRI11.SA", "VOTS11.SA",
    "VVCR11.SA", "VTLT11.SA", "WHGR11.SA", "XPDV11.SA",
]


def fetch_fiis():
    print("\n[7/14] Fetching FIIs data...")
    # Deduplicate while preserving order
    seen = set()
    unique_fiis = [t for t in FIIS if not (t in seen or seen.add(t))]
    for ticker in unique_fiis:
        name = ticker.replace(".SA", "").lower()
        _yf_download(ticker, name, FIIS_DIR)


# ─── ETFs B3 — cobertura máxima (~50 tickers) ────────────────────────────────

ETFS = {
    # ── Renda variável Brasil — índices amplos ──
    "bova11":   "BOVA11.SA",   # Ibovespa
    "bovv11":   "BOVV11.SA",   # Ibovespa (Vanguard variant)
    "pibb11":   "PIBB11.SA",   # IBrX-50 (iShares, mais antigo)
    "brax11":   "BRAX11.SA",   # IBrX-100
    "smal11":   "SMAL11.SA",   # Small Caps
    "smab11":   "SMAB11.SA",   # Small Cap (variante)
    # ── Renda variável Brasil — temáticos ──
    "divo11":   "DIVO11.SA",   # Dividendos (IDIV)
    "matb11":   "MATB11.SA",   # Materiais básicos (IMAT)
    "isus11":   "ISUS11.SA",   # Sustentabilidade (ISE)
    "find11":   "FIND11.SA",   # Financeiro (IFNC)
    "util11":   "UTIL11.SA",   # Utilidades (IUTIL)
    "csmo11":   "CSMO11.SA",   # Consumo (ICON)
    "agri11":   "AGRI11.SA",   # Agronegócio (IAGRO)
    "infra11":  "INFRA11.SA",  # Infraestrutura
    "ecoo11":   "ECOO11.SA",   # ESG / Eficiência Carbono
    # ── Renda variável internacional (em BRL) ──
    "ivvb11":   "IVVB11.SA",   # S&P 500 sem hedge
    "spxi11":   "SPXI11.SA",   # S&P 500 com hedge cambial
    "nasd11":   "NASD11.SA",   # Nasdaq 100
    "eurp11":   "EURP11.SA",   # Europa (MSCI Europe)
    "acwi11":   "ACWI11.SA",   # MSCI ACWI (global)
    "wrld11":   "WRLD11.SA",   # MSCI World
    "esgb11":   "ESGB11.SA",   # ESG global
    "chna11":   "CHNA11.SA",   # China (MSCI China)
    "xina11":   "XINA11.SA",   # China A-shares
    "spxb11":   "SPXB11.SA",   # S&P 500 ESG
    # ── Renda fixa / Tesouro BR ──
    "imab11":   "IMAB11.SA",   # IMA-B — NTN-B (IPCA+)
    "b5p211":   "B5P211.SA",   # IMA-B 5+ (NTN-B longas)
    "irfm11":   "IRFM11.SA",   # IRF-M — prefixados
    "fixa11":   "FIXA11.SA",   # Pré-fixado curto
    "ntnb11":   "NTNB11.SA",   # NTN-B (variante Itaú)
    "lbri11":   "LBRI11.SA",   # IMA-Geral (todas maturidades)
    "usdb11":   "USDB11.SA",   # IMA-S — pós-fixado (LFT/SELIC)
    "gove11":   "GOVE11.SA",   # Tesouro Pré-fixado (short duration)
    # ── Debêntures / Crédito ──
    "debn11":   "DEBN11.SA",   # Debêntures incentivadas
    "debb11":   "DEBB11.SA",   # Debêntures corporativas
    "fiit11":   "FIIT11.SA",   # FII (fundo de FIIs)
    # ── Commodities / Cripto / Alternativos ──
    "gold11":   "GOLD11.SA",   # Ouro físico (BRL)
    "hash11":   "HASH11.SA",   # Criptoativos diversificados
    "comc11":   "COMC11.SA",   # Commodities (índice)
    "defi11":   "DEFI11.SA",   # DeFi/Cripto
    "bith11":   "BITH11.SA",   # Bitcoin (variante)
}


def fetch_etfs():
    print("\n[8/14] Fetching B3 ETFs data...")
    for name, ticker in ETFS.items():
        _yf_download(ticker, name, ETFS_DIR)


# ─── BDRs — cobertura máxima (~90 tickers) ───────────────────────────────────

BDRS = {
    # ── Big Tech / FAANG+ ──
    "aapl34":   "AAPL34.SA",   # Apple
    "msft34":   "MSFT34.SA",   # Microsoft
    "amzo34":   "AMZO34.SA",   # Amazon
    "gogl34":   "GOGL34.SA",   # Alphabet (Google)
    "meta34":   "META34.SA",   # Meta (Facebook)
    "nvdc34":   "NVDC34.SA",   # NVIDIA
    "tsla34":   "TSLA34.SA",   # Tesla
    "nflx34":   "NFLX34.SA",   # Netflix
    "uber34":   "UBER34.SA",   # Uber
    "spot34":   "SPOT34.SA",   # Spotify
    "adbe34":   "ADBE34.SA",   # Adobe
    "crm34":    "CRM34.SA",    # Salesforce
    "intu34":   "INTU34.SA",   # Intuit
    "pypl34":   "PYPL34.SA",   # PayPal
    "sq34":     "SQ34.SA",     # Block (Square)
    "meli34":   "MELI34.SA",   # MercadoLibre (maior EM tech LatAm)
    "shop32":   "SHOP32.SA",   # Shopify
    # ── Semicondutores / Hardware ──
    "itlc34":   "ITLC34.SA",   # Intel
    "csco34":   "CSCO34.SA",   # Cisco
    "orcl34":   "ORCL34.SA",   # Oracle
    "ibmb34":   "IBMB34.SA",   # IBM
    "qual34":   "QUAL34.SA",   # Qualcomm
    "txn34":    "TXN34.SA",    # Texas Instruments
    "amd34":    "AMD34.SA",    # AMD
    # ── Financeiro / Bancos ──
    "jpmc34":   "JPMC34.SA",   # JPMorgan Chase
    "berk34":   "BERK34.SA",   # Berkshire Hathaway
    "boac34":   "BOAC34.SA",   # Bank of America
    "gsgi34":   "GSGI34.SA",   # Goldman Sachs
    "msbr34":   "MSBR34.SA",   # Morgan Stanley
    "wfco34":   "WFCO34.SA",   # Wells Fargo
    "c34":      "C34.SA",      # Citigroup
    "axp34":    "AXP34.SA",    # American Express
    "visa34":   "VISA34.SA",   # Visa
    "mast34":   "MAST34.SA",   # Mastercard
    "pru34":    "PRU34.SA",    # Prudential Financial
    # ── Saúde / Farma ──
    "jnjb34":   "JNJB34.SA",   # Johnson & Johnson
    "pfiz34":   "PFIZ34.SA",   # Pfizer
    "abtt34":   "ABTT34.SA",   # Abbott
    "mrck34":   "MRCK34.SA",   # Merck
    "lily34":   "LILY34.SA",   # Eli Lilly
    "unh34":    "UNH34.SA",    # UnitedHealth
    "abbv34":   "ABBV34.SA",   # AbbVie
    "bmy34":    "BMY34.SA",    # Bristol-Myers Squibb
    "amgn34":   "AMGN34.SA",   # Amgen
    "nvo34":    "NVO34.SA",    # Novo Nordisk
    # ── Consumo / Varejo ──
    "kofc34":   "KOFC34.SA",   # Coca-Cola
    "pepb34":   "PEPB34.SA",   # PepsiCo
    "mcdc34":   "MCDC34.SA",   # McDonald's
    "nike34":   "NIKE34.SA",   # Nike
    "disb34":   "DISB34.SA",   # Disney
    "wmt34":    "WMT34.SA",    # Walmart
    "tgt34":    "TGT34.SA",    # Target
    "hd34":     "HD34.SA",     # Home Depot
    "low34":    "LOW34.SA",    # Lowe's
    "sbux34":   "SBUX34.SA",   # Starbucks
    "pg34":     "PG34.SA",     # Procter & Gamble
    "cl34":     "CL34.SA",     # Colgate-Palmolive
    # ── Industrial / Aerospace / Defesa ──
    "ba34":     "BA34.SA",     # Boeing
    "ge34":     "GE34.SA",     # GE Aerospace
    "mmm34":    "MMM34.SA",    # 3M
    "hon34":    "HON34.SA",    # Honeywell
    "cat34":    "CAT34.SA",    # Caterpillar
    "de34":     "DE34.SA",     # Deere & Co
    "ups34":    "UPS34.SA",    # UPS
    "fdx34":    "FDX34.SA",    # FedEx
    # ── Energia / Petróleo ──
    "xomc34":   "XOMC34.SA",   # ExxonMobil
    "chev34":   "CHEV34.SA",   # Chevron
    "shel34":   "SHEL34.SA",   # Shell
    "toit34":   "TOIT34.SA",   # TotalEnergies
    "bp34":     "BP34.SA",     # BP
    "slb34":    "SLB34.SA",    # SLB (Schlumberger)
    # ── Mineração / Metais (influência direta na B3) ──
    "bhpb34":   "BHPB34.SA",   # BHP Billiton BDR
    "riot34":   "RIOT34.SA",   # Rio Tinto BDR
    # ── Ásia ──
    "baba34":   "BABA34.SA",   # Alibaba
    "tsmc34":   "TSMC34.SA",   # TSMC
    "sams34":   "SAMS34.SA",   # Samsung
    # ── Telecom / Streaming ──
    "t34":      "T34.SA",      # AT&T
    "vz34":     "VZ34.SA",     # Verizon
}


def fetch_bdrs():
    print("\n[9/14] Fetching BDRs data...")
    for name, ticker in BDRS.items():
        _yf_download(ticker, name, BDRS_DIR)


# ─── Commodities relevantes ao Brasil ────────────────────────────────────────

COMMODITIES = {
    # ── Energia ──
    "brent":          "BZ=F",
    "wti":            "CL=F",
    "nat_gas":        "NG=F",
    "ethanol":        "EH=F",
    "heating_oil":    "HO=F",
    "rbob_gasoline":  "RB=F",
    # ── Metais ──
    "gold":           "GC=F",
    "silver":         "SI=F",
    "copper":         "HG=F",
    "aluminum":       "ALI=F",
    "platinum":       "PL=F",
    "palladium":      "PA=F",
    "nickel":         "NI=F",
    "zinc":           "ZNC=F",
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
    "rice":           "ZR=F",
    # ── Pecuária ──
    "live_cattle":    "LE=F",
    "feeder_cattle":  "GF=F",
    "lean_hogs":      "HE=F",
    # ── Madeira / Outros ──
    "lumber":         "LBR=F",
}


def fetch_commodities():
    print("\n[10/14] Fetching commodities data...")
    for name, ticker in COMMODITIES.items():
        _yf_download(ticker, name, COMMODITIES_DIR)


# ─── Global Macro — variáveis externas que influenciam a B3 ──────────────────
# Esta categoria captura TODOS os drivers externos da B3:
#   - China (maior parceiro, VALE = 15%+ do IBOV)
#   - Minério de ferro / aço (VALE, CSN, Gerdau, Usiminas)
#   - Curva de juros EUA (custo de capital, carry trade BRL)
#   - Crédito / risco EM (fluxo de capital estrangeiro p/ B3)
#   - LatAm peers (contágio de sentimento regional)
#   - Agro global (ADRs de processadores/traders de commodities)
#   - Volatilidades específicas (petróleo, ouro, câmbio)

GLOBAL_MACRO = {
    # ── China — drives VALE, minério, aço, soja ──
    "fxi":          "FXI",       # iShares China Large-Cap
    "mchi":         "MCHI",      # iShares MSCI China
    "kweb":         "KWEB",      # KraneShares China Internet (tech chinesa)
    "ashr":         "ASHR",      # Deutsche X-trackers CSI 300 (A-shares)
    "cnya":         "CNYA",      # iShares MSCI China A (onshore)
    # ── Iron ore / Mineração — VALE é ~15% do IBOV ──
    "vale_adr":     "VALE",      # Vale S.A. ADR (NYSE) — mesma empresa em USD
    "rio_tinto":    "RIO",       # Rio Tinto ADR — define price discovery de minério
    "bhp":          "BHP",       # BHP ADR — maior mineradora, produtora de minério
    "pick":         "PICK",      # iShares Diversified Mining ETF
    "xme":          "XME",       # SPDR S&P Metals & Mining ETF
    # ── Aço — CSN, Gerdau, Usiminas ──
    "slx":          "SLX",       # VanEck Steel ETF
    "mt":           "MT",        # ArcelorMittal ADR
    "stld":         "STLD",      # Steel Dynamics (benchmark aço EUA)
    # ── Petróleo — PETR3/PETR4 = ~10% do IBOV ──
    "pbr":          "PBR",       # Petrobras ADR ON (NYSE)
    "pbr_a":        "PBR-A",     # Petrobras ADR PN (NYSE)
    "oih":          "OIH",       # VanEck Oil Services ETF
    "xle":          "XLE",       # SPDR Energy Select Sector
    # ── América Latina — contágio de sentimento regional ──
    "ilf":          "ILF",       # iShares Latin America 40
    "eww":          "EWW",       # iShares MSCI Mexico
    "gxg":          "GXG",       # iShares MSCI Colombia
    "ech":          "ECH",       # iShares MSCI Chile
    "epu":          "EPU",       # iShares MSCI Peru
    "argt":         "ARGT",      # Global X MSCI Argentina
    "ewz":          "EWZ",       # iShares MSCI Brazil (Brasil em USD)
    # ── Mercados emergentes — fluxo de capital para/de B3 ──
    "eem":          "EEM",       # iShares MSCI EM
    "vwo":          "VWO",       # Vanguard FTSE EM
    "emhy":         "EMHY",      # iShares EM High Yield
    "emb":          "EMB",       # iShares EM Bonds USD
    "cew":          "CEW",       # WisdomTree EM Currency ETF
    # ── Curva de juros EUA — carry trade BRL, custo de capital ──
    "tnx":          "^TNX",      # US 10y Treasury yield
    "tyx":          "^TYX",      # US 30y Treasury yield
    "fvx":          "^FVX",      # US 5y Treasury yield
    "irx":          "^IRX",      # US 3-month T-bill
    "shy":          "SHY",       # 1-3yr Treasury (proxy Fed rate)
    # ── Crédito EUA — apetite por risco global ──
    "hyg":          "HYG",       # High Yield (risco-on/off)
    "lqd":          "LQD",       # Investment Grade
    # ── Crescimento global / Ciclo econômico ──
    "vt":           "VT",        # Vanguard Total World Stock
    "acwi":         "ACWI",      # iShares MSCI ACWI
    "xlf":          "XLF",       # SPDR Financials (stress bancário)
    "xly":          "XLY",       # SPDR Consumer Discretionary
    # ── Agro global — traders/processadores de soja, milho, café ──
    "adm":          "ADM",       # Archer-Daniels-Midland (soja, milho)
    "bunge":        "BG",        # Bunge Limited (maior trader de soja)
    "cargill_proxy":"CF",        # CF Industries (fertilizantes)
    "mosaic":       "MOS",       # Mosaic (potássio/fosfato — insumos agro)
    # ── Celulose / Papel — Suzano é maior do mundo ──
    "intl_paper":   "IP",        # International Paper
    "weyerhaeuser": "WY",        # Weyerhaeuser (florestal EUA)
    # ── Bancos brasileiros ADR ──
    "itub_adr":     "ITUB",      # Itaú ADR (NYSE)
    "bbd":          "BBD",       # Bradesco ADR (NYSE)
    # ── Aviação — Azul, Gol (ciclo econômico BR) ──
    "jets":         "JETS",      # US Global Jets ETF (cias aéreas global)
    # ── Volatilidades específicas (risco em ativos-chave da B3) ──
    "vix":          "^VIX",      # Volatilidade S&P 500
    "ovx":          "^OVX",      # Volatilidade do petróleo
    "gvz":          "^GVZ",      # Volatilidade do ouro
    # ── Frete / Comércio global ──
    "dbc":          "DBC",       # Invesco Commodities (índice amplo)
    "gsg":          "GSG",       # iShares GSCI Commodity Index
}


def fetch_global_macro():
    print("\n[11/14] Fetching global macro drivers of B3...")
    for name, ticker in GLOBAL_MACRO.items():
        _yf_download(ticker, name, GLOBAL_MACRO_DIR)


# ─── Bonds / Fixed Income ETFs ───────────────────────────────────────────────

BONDS_ETFS = {
    # ── Treasuries EUA ──
    "shy":    "SHY",
    "ief":    "IEF",
    "tlt":    "TLT",
    "govt":   "GOVT",
    # ── TIPS — proteção inflação ──
    "tip":    "TIP",
    "stip":   "STIP",
    # ── Crédito investment grade ──
    "lqd":    "LQD",
    "vcit":   "VCIT",
    "vclt":   "VCLT",
    # ── High yield ──
    "hyg":    "HYG",
    "jnk":    "JNK",
    # ── Bonds EM ──
    "emb":    "EMB",
    "lemb":   "LEMB",
    # ── Bonds globais ──
    "bndx":   "BNDX",
    "iagg":   "IAGG",
    # ── Alternativos ──
    "icvt":   "ICVT",
    "bkln":   "BKLN",
    # ── BR reference ──
    "imab11_ref":  "IMAB11.SA",
    "irfm11_ref":  "IRFM11.SA",
}


def fetch_bonds():
    print("\n[12/14] Fetching bonds / fixed-income ETFs...")
    for name, ticker in BONDS_ETFS.items():
        _yf_download(ticker, name, BONDS_DIR)


# ─── Real Assets ETFs ────────────────────────────────────────────────────────

REAL_ASSETS_ETFS = {
    # ── REITs EUA ──
    "vnq":    "VNQ",
    "iyr":    "IYR",
    "rem":    "REM",
    "schh":   "SCHH",
    # ── REITs Internacional ──
    "reet":   "REET",
    "ifgl":   "IFGL",
    # ── Infraestrutura ──
    "ifra":   "IFRA",
    "pave":   "PAVE",
    "igf":    "IGF",
    # ── Madeira ──
    "wood":   "WOOD",
    "cut":    "CUT",
    # ── Água ──
    "pho":    "PHO",
    "fiw":    "FIW",
    "cgw":    "CGW",
    # ── Agricultura ──
    "dba":    "DBA",
    "soyb":   "SOYB",
    "corn_et": "CORN",
    "cane":   "CANE",
    "jo":     "JO",
    # ── Metais preciosos físicos ──
    "gld":    "GLD",
    "iau":    "IAU",
    "gdx":    "GDX",
    "gdxj":   "GDXJ",
    "slv":    "SLV",
    "pplt":   "PPLT",
    # ── Energia real ──
    "uso":    "USO",
    "ung":    "UNG",
    "mlp":    "AMLP",
}


def fetch_real_assets():
    print("\n[13/14] Fetching real assets ETFs (low equity correlation)...")
    for name, ticker in REAL_ASSETS_ETFS.items():
        _yf_download(ticker, name, REAL_ASSETS_DIR)


# ─── Alternative / Thematic ETFs ─────────────────────────────────────────────

ALTERNATIVES_ETFS = {
    # ── Volatilidade ──
    "uvxy":   "UVXY",
    "svxy":   "SVXY",
    "vixm":   "VIXM",
    # ── Setores defensivos ──
    "xlv":    "XLV",
    "xlu":    "XLU",
    "xlp":    "XLP",
    "xli":    "XLI",
    "xlb":    "XLB",
    # ── Energia limpa ──
    "icln":   "ICLN",
    "tan":    "TAN",
    "fan":    "FAN",
    "ura":    "URA",
    "qcln":   "QCLN",
    # ── Defesa ──
    "ita":    "ITA",
    "xar":    "XAR",
    # ── Mercados emergentes ──
    "fm":     "FM",
    "ewy":    "EWY",
    "inda":   "INDA",
    "mchi":   "MCHI",
    # ── Fatores / Smart Beta ──
    "usmv":   "USMV",
    "qual":   "QUAL",
    "mtum":   "MTUM",
    "vlue":   "VLUE",
    "size":   "SIZE",
    # ── Dividendos ──
    "vym":    "VYM",
    "schd":   "SCHD",
    "hdv":    "HDV",
    # ── Tecnologia disruptiva ──
    "arkk":   "ARKK",
    "arkg":   "ARKG",
    "lit":    "LIT",
    "hack":   "HACK",
    "robo":   "ROBO",
    "botz":   "BOTZ",
    # ── Índices de commodities ──
    "pdbc":   "PDBC",
    # ── Inflação ──
    "rinf":   "RINF",
}


def fetch_alternatives():
    print("\n[14/14] Fetching alternative/thematic ETFs...")
    for name, ticker in ALTERNATIVES_ETFS.items():
        _yf_download(ticker, name, ALTERNATIVES_DIR)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ensure_dirs()
    fetch_macro_data()        # [ 1/14] BCB macro + PTAX (65+ series)
    fetch_fixed_income_data() # [ 2/14] BCB renda fixa + crédito (23+ series)
    fetch_sectoral_data()     # [ 3/14] BCB setorial + atividade (15 series)
    fetch_currency_data()     # [ 4/14] BRL FX (15 pares) + cripto (14)
    fetch_equity_indices()    # [ 5/14] Índices B3 + globais (30)
    fetch_top_stocks()        # [ 6/14] ~290 ações B3
    fetch_fiis()              # [ 7/14] ~130 FIIs
    fetch_etfs()              # [ 8/14] ~50 ETFs B3
    fetch_bdrs()              # [ 9/14] ~90 BDRs
    fetch_commodities()       # [10/14] ~30 futuros de commodities
    fetch_global_macro()      # [11/14] ~55 drivers externos da B3
    fetch_bonds()             # [12/14] ~20 bond ETFs (baixa corr.)
    fetch_real_assets()       # [13/14] ~29 real asset ETFs
    fetch_alternatives()      # [14/14] ~36 temáticos / fatores
    print("\n[collector] All data collection complete.")


if __name__ == "__main__":
    main()
