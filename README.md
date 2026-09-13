# TRD BOT v2

TRD BOT v2 is a single-user research platform for:

- market-data research
- reproducible backtesting and walk-forward evaluation
- deterministic candidate ranking and risk evaluation
- simulated paper/shadow portfolios
- paper-position monitoring and exit-condition tracking
- immutable candidate journal lineage and read-only dashboards

## MVP operating boundary

The MVP supports only:

- `RESEARCH`
- `BACKTEST`
- `PAPER`
- `SHADOW`

There is intentionally no live-execution mode, exchange-account integration,
real-money order submission, or live trading.

## Requirements

- Python 3.12+
- Node.js 22+
- Docker with Docker Compose
- Git

## Fresh local setup

Create the Python environment and install backend dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Create the local environment file:

```bash
cp .env.example .env
```

Start PostgreSQL:

```bash
docker compose up -d postgres
docker compose ps
```

The development database is PostgreSQL 17 and the connection settings are
defined in `.env.example`.

Apply all migrations and verify that no model changes are missing:

```bash
python -m alembic upgrade head
python -m alembic check
```

Optional read-only demo data can be created with:

```bash
python scripts/seed_demo_data.py
python scripts/seed_monitoring_demo.py
```

Start the backend API:

```bash
python -m uvicorn trd_bot.main:app --reload
```

The health endpoint is:

```text
http://127.0.0.1:8000/api/v1/health
```

In another terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

The dashboard is available at:

```text
http://127.0.0.1:3000
```

## Quality gates

Backend:

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
```

PostgreSQL migration and integration verification:

```bash
python -m alembic upgrade head
python -m alembic check
python -m pytest -m integration -v
```

Frontend:

```bash
cd frontend
npm run format:check
npm run lint
npm run test
npm run build
```

The GitHub Actions workflow runs the same backend, PostgreSQL, and frontend
quality gates for pushes to `main`, `feature/**`, `fix/**`, and `bugfix/**`, as
well as pull requests targeting `main`.

## MVP release verification

The final fresh-start and release checklist is documented in
[`docs/mvp-release-checklist.md`](docs/mvp-release-checklist.md).

## Project structure

```text
trd-bot-v2/
├── .github/workflows/
├── alembic/
├── docker/
├── docs/
├── frontend/
├── scripts/
├── src/
│   └── trd_bot/
├── tests/
├── .env.example
├── compose.yaml
├── pyproject.toml
└── README.md
```
