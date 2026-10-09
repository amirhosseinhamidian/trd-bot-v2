# TRD BOT v2

Current local release candidate: **v0.2.0**. This repository is configured for
local research use; server staging and deployment are intentionally deferred.

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

Provider imports and optimization executions use the durable background queue.
Keep a worker running in a separate terminal:

```bash
source .venv/bin/activate
python scripts/run_background_worker.py
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
npm run typecheck
npm run test
npm run build
```

The GitHub Actions workflow runs the same backend, PostgreSQL, and frontend
quality gates for pushes to `main`, `feature/**`, `fix/**`, `bugfix/**`, and
`refactor/**`, as well as pull requests targeting `main`.

## MVP release verification

The final fresh-start and release checklist is documented in
[`docs/mvp-release-checklist.md`](docs/mvp-release-checklist.md).
The local v0.2.0 candidate runbook and evidence template are documented in
[`docs/v0.2/26-local-release-candidate.md`](docs/v0.2/26-local-release-candidate.md).
The frozen Nexora UI contract, release notes, and upgrade guidance are documented in
[`docs/nexora-ui-release-and-migration.md`](docs/nexora-ui-release-and-migration.md).

Development of v0.3 starts from the frozen product scope and Crypto Spot market target in
[`docs/v0.3/00-scope-and-market-target.md`](docs/v0.3/00-scope-and-market-target.md). The runtime
and release manifests remain at v0.2.0 until the v0.3 release gates are complete.
The verified v0.2 baseline, deferred debt, existing guardrails, and capacity-observability gaps are
tracked in [`docs/v0.3/01-baseline-debt-capacity-inventory.md`](docs/v0.3/01-baseline-debt-capacity-inventory.md).
The versioned event envelope, watermark, late-arrival, and immutable window contracts are frozen in
[`docs/v0.3/02-event-contract-and-window-semantics.md`](docs/v0.3/02-event-contract-and-window-semantics.md).

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
