# TRD BOT v2

TRD BOT v2 is a single-user research platform for:

- market-data research
- reproducible backtesting
- candidate ranking
- simulated paper portfolios
- paper-position monitoring
- exit-condition tracking

## MVP operating modes

The MVP supports only:

- `RESEARCH`
- `BACKTEST`
- `PAPER`
- `SHADOW`

There is intentionally no live-execution mode or exchange-account integration.

## Requirements

- Python 3.12+
- Git

## Project structure

```text
trd-bot-v2/
├── src/
│   └── trd_bot/
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```
