# Brazil Financial Market Data (Open Source)

Este projeto tem como objetivo consolidar o maior volume possível de dados históricos e em tempo real do mercado financeiro brasileiro.

## Estrutura do Projeto

O projeto segue uma estrutura organizada por tipo de ativo e categoria de dado:

```text
/data
  /macro          # Dados macroeconômicos (SELIC, IPCA, PIB, etc.)
  /equities
    /stocks       # Dados históricos de ações individuais (OHLCV)
    /indices      # Índices de mercado (IBOVESPA, IFIX, etc.)
  /currencies     # Taxas de câmbio (USD/BRL, EUR/BRL, BTC/USD)
  /fixed_income   # (Em construção) Tesouro Direto e taxas DI
/scripts          # Scripts de mineração e atualização
```

## Dados Atuais

Atualmente, o projeto já conta com:
- **Macro:** SELIC diária, IPCA mensal, CDI diário, PIB, IGP-M.
- **Moedas:** Histórico de USD/BRL, EUR/BRL e cripto pares.
- **Ações:** Histórico de dezenas das principais ações da B3.
- **Índices:** IBOVESPA, IFIX e small caps.
- **Mineração local derivada:** retornos diários e resumo estatístico por ativo em `data/mined/`.

## Como Contribuir

Para adicionar novos dados:
1. Adicione a lógica no script em `scripts/collector.py`.
2. Garanta que o dado seja salvo em formato CSV na pasta correspondente em `/data`.
3. Mantenha o padrão de nomenclatura `ticker.csv` ou `nome_indicador.csv`.

## Requisitos

- Python 3.10+
- `pandas`
- `yfinance`
- `python-bcb`

Para instalar as dependências:
```bash
pip install pandas yfinance python-bcb requests
```

## Execução

Para atualizar todos os dados locais:
```bash
python scripts/collector.py
```

Para minerar dados derivados a partir dos CSVs já coletados:
```bash
python scripts/mine_local_data.py
```

## Fontes
- Banco Central do Brasil (SGS API)
- Yahoo Finance (via yfinance)
