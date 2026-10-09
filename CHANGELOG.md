# Changelog

All notable changes to TRD BOT v2 are documented in this file.

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
