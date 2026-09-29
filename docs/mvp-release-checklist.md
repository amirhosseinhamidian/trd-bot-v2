# MVP release checklist

This checklist is the final acceptance gate for TRD BOT v2 MVP.

The current release profile is local-only. Server staging, deployment, pull-request
merge, tag creation, and GitHub Release publication are deferred until the owner
explicitly enables them. Local acceptance and CI on the candidate SHA remain required.

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

## 2. Local PostgreSQL startup

The default local path preserves the existing development volume:

```bash
docker compose up -d postgres
docker compose ps
```

Wait until the `postgres` service reports `healthy`.

Do not run `docker compose down -v` on a database whose data must be preserved.
The destructive fresh-database cycle is already enforced by CI and may only be
repeated locally against an explicitly disposable database.

## 3. Reversible fresh schema migration

This destructive cycle belongs only on a disposable database. CI performs it
against a fresh `trd_bot_test` service for every candidate SHA. Do not point
these commands at the local development database when its data must be kept:

```bash
export TRD_BOT_DATABASE_URL=postgresql+psycopg://trd_bot:trd_bot_dev_password@127.0.0.1:5432/trd_bot_test
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
python -m alembic check
unset TRD_BOT_DATABASE_URL
```

Expected result:

- the full migration chain upgrades successfully from an empty database;
- the complete chain downgrades to `base` and rebuilds to `head`;
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
python -m pytest tests/test_release_security_boundary.py -q
```

These checks verify that a closed historical candidate lifecycle can be persisted and
read back through candidate, lineage, portfolio, position, and timeline APIs, and that
the release exposes no live execution route, credential input, or frontend execution page.

The PostgreSQL race and restart acceptance test must run against the isolated
`trd_bot_test` database:

```bash
python -m pytest \
  tests/test_postgresql_integration.py::test_postgresql_background_job_races_and_expired_lease_recovery \
  -m integration -v
```

It proves idempotent concurrent enqueue, single-worker claim, expired lease reclaim, and
rejection of the stale worker after recovery.

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
- The complete Alembic chain downgrades to `base` and rebuilds to `head`.
- `alembic check` reports no pending migration.
- Backend formatting, lint, type checking, unit tests, and integration tests pass.
- The end-to-end MVP acceptance test passes.
- The PostgreSQL job race/recovery and release security boundary tests pass.
- Frontend formatting, lint, tests, and production build pass.
- The API health smoke check returns HTTP 200.
- Candidate journal/projection and paper portfolio dashboards remain read-only.
- No live trading or exchange execution capability exists.
- GitHub Actions is green on the exact candidate SHA.
- The candidate is accepted for local use; server deployment and publication remain deferred.
