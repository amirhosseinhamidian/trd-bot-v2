# Changelog

All notable changes to TRD BOT v2 are documented in this file.

## 0.3.0 - local release candidate

Status: untagged candidate for local research, paper, and shadow use. Server deployment, public
release publication, exchange-account connectivity, and live execution remain deferred.

### Added

- Near-real-time public Crypto Spot ingestion with versioned events, provisional/finalized windows,
  watermark semantics, late-data replay, retention controls, and freshness observability.
- Deterministic multi-timeframe Market Context, feature and regime evidence, durable context jobs,
  monitoring, API/UI integration, and a golden acceptance benchmark.
- Versioned alert rules, durable evaluation jobs, inbox lifecycle, quiet-hours and expiry policy,
  Paper/Shadow simulation, outcome journals, and drift evidence.
- Decision Intelligence lineage from Strategy and Context through Candidate ranking, Risk Gate,
  position sizing, and limited simulated Portfolio Intelligence.
- Read-only progressive disclosure across Strategy, Signal, Candidate, Risk, and Portfolio screens.
- Phase-by-phase acceptance records and same-SHA benchmark evidence through the Phase 5 freeze.
- A deterministic release-surface inventory covering OpenAPI operations, frontend pages, public
  providers, worker policies, database tables, migrations, version sources, and network identity.
- A commit-bound PostgreSQL release-capacity benchmark covering the 100-job overload boundary,
  single-worker drain budget, concurrent claim and enqueue safety, retry, lease reclaim,
  stale-owner fencing, and cleanup.
- A commit-bound, aggregate Outcome/Learning review across alert outcomes, candidate lifecycle,
  decision-stage dispositions, and simulated Paper/Shadow position results, with deterministic
  sample readiness and human-review-only warnings.
- A commit-bound retention and maintenance plan covering audited Market Data dry-runs, bounded
  cleanup of expired dataset upload stages, append-only Alert expiry evidence, and rebuildable
  Candidate projections without automatic execution or immutable-evidence deletion.

### Changed

- Long-running imports, experiments, walk-forward runs, optimization, context evaluation, alerts,
  and decision evaluation use durable, retry-safe worker policies.
- The runtime, backend package, environment example, and frontend manifests now identify v0.3.0.

### Operating boundary

- Supported modes remain `RESEARCH`, `BACKTEST`, `PAPER`, and `SHADOW`.
- Market access remains public and read-only; no exchange credentials or private account APIs exist.
- Portfolio Intelligence remains advisory for simulated portfolios and cannot submit orders or
  manage real assets.
- This release cut does not create a tag, GitHub Release, deployment, or merge to `main`.

## 0.2.0 — local release candidate

Status: untagged candidate for local research use. Server deployment and public
release publication are deferred.

### Added

- The frozen Nexora / TRD BOT interface foundation, including bilingual RTL/LTR navigation,
  light/dark themes, responsive feature screens, accessible interaction contracts, and a stable
  21-route public inventory.
- Release regression coverage for 42 localized route patterns, critical user journeys, theme and
  locale hydration, responsive layouts, keyboard/focus behavior, and the frontend/OpenAPI boundary.
- Real public market-data adapters for Nobitex and Kraken, provider capability
  metadata, access probes, and provider selection in the import UI.
- Reproducible dataset preview/import, atomic version history, quality scoring,
  provenance, and CSV/JSON/Parquet ingestion.
- Durable PostgreSQL jobs for provider imports and optimization with progress,
  retry, cancellation, lease recovery, and operational monitoring.
- Versioned strategy registry, experiment replay, walk-forward optimization,
  robustness ranking, and persisted trial evidence.
- Candidate ranking evidence, comparison lineage, risk analytics, portfolio
  performance, and position detail timelines.
- Release gates for PostgreSQL migration rollback/rebuild, queue races and
  recovery, end-to-end research lifecycle, and the no-live-trading boundary.

### Changed

- Frontend ownership now follows feature boundaries. Shared HTTP transport remains in
  `frontend/src/lib/api/core`, while domain clients, types, copy, and screens live under their
  owning feature.
- The legacy dashboard shell, global API facades, and superseded language control were removed
  after their final consumers migrated.

### Operating boundary

- Supported modes remain `RESEARCH`, `BACKTEST`, `PAPER`, and `SHADOW`.
- There is no exchange-account credential flow, live order submission, wallet,
  deposit, or withdrawal capability.
- TB2-022 research templates, notes, tags, and export enhancements remain deferred.
- Raw file upload processing and legacy Experiment/Walk-Forward request paths are
  not fully moved to the durable worker and require an explicit local-release exception.
