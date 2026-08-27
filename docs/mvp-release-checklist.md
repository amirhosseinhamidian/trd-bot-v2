# MVP release checklist

This checklist is the final acceptance gate for TRD BOT v2 MVP.

The MVP is a research and historical-simulation system only. It must remain
limited to `RESEARCH`, `BACKTEST`, `PAPER`, and `SHADOW` operation. A release
must not add exchange credentials, account connectivity, real-money order
submission, or live execution.

## 1. Clean repository state

Start from the release branch or candidate commit:

```bash
git status --short
git diff --check
```

Expected result: no unintended working-tree changes and no whitespace errors.

## 2. Fresh PostgreSQL startup

This step intentionally removes the local development database volume. Do not
run it when local PostgreSQL data must be preserved.

```bash
docker compose down -v
docker compose up -d postgres
docker compose ps
```

Wait until the `postgres` service reports `healthy`.

## 3. Fresh schema migration

Load the development environment and upgrade an empty database:

```bash
cp -n .env.example .env
python -m alembic upgrade head
python -m alembic check
```

Expected result:

- the full migration chain upgrades successfully from an empty database;
- `alembic check` reports no pending schema operations.

## 4. Backend release gates

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
python -m pytest -m integration -v
```

Expected result: every command exits with status `0`.

The MVP end-to-end acceptance test must also pass:

```bash
python -m pytest tests/test_mvp_acceptance.py -q
```

It verifies that a closed historical candidate lifecycle can be persisted and
read back through candidate, lineage, portfolio, position, and timeline APIs.

## 5. API smoke check

Start the API:

```bash
python -m uvicorn trd_bot.main:app
```

From another terminal:

```bash
curl --fail http://127.0.0.1:8000/api/v1/health
```

Expected result: HTTP 200 with `"status":"ok"`.

## 6. Frontend release gates

```bash
cd frontend
npm ci
npm run format:check
npm run lint
npm run test
npm run build
cd ..
```

Expected result: all frontend checks pass and the production Next.js build is
created successfully.

## 7. Optional dashboard smoke data

For a manual local dashboard review:

```bash
python scripts/seed_demo_data.py
python scripts/seed_monitoring_demo.py
```

Review the English and Persian dashboard routes and confirm that research,
candidate, portfolio, and monitoring pages are read-only and render without
runtime errors.

## 8. Final release decision

The MVP can be marked complete only when all of the following are true:

- PostgreSQL starts cleanly through Docker Compose.
- The complete Alembic chain upgrades an empty database.
- `alembic check` reports no pending migration.
- Backend formatting, lint, type checking, unit tests, and integration tests pass.
- The end-to-end MVP acceptance test passes.
- Frontend formatting, lint, tests, and production build pass.
- The API health smoke check returns HTTP 200.
- Candidate journal/projection and paper portfolio dashboards remain read-only.
- No live trading or exchange execution capability exists.
- GitHub Actions is green on the final pull request or `main` commit.
