# Nexora UI — Release and Migration Notes

Status: **Frozen after P6 acceptance**

Release line: **TRD BOT v0.2.0 local release candidate**

Branch: `refactor/nexora-ui-foundation`

This document records the completed Nexora interface redesign, the compatibility boundary for
future work, and the migration steps for code built against the pre-Nexora frontend structure.
It does not authorize a deployment, merge to `main`, version tag, or public release.

## Release highlights

- Nexora is the platform identity and TRD BOT is the active product context.
- The responsive Platform Shell provides desktop sidebar, tablet drawer, and compact mobile
  navigation while preserving every existing public URL.
- Persian and English are first-class, including RTL/LTR direction, localized navigation, and
  locale-preserving deep links.
- Dark and light themes use semantic design tokens and preserve the user's existing theme choice.
- Dataset, Experiment, Walk-forward, Optimization, Strategy, Signal, Candidate, Risk, Portfolio,
  Connection, and Monitoring screens now use feature-owned UI and API boundaries.
- Dense research tables expose labelled horizontal scrolling; decision-oriented pages lead with
  readable summaries and move secondary raw data into progressive disclosure.
- Keyboard focus, landmarks, progress indicators, touch targets, reduced motion, long identifiers,
  empty/error states, Persian numerals, and mixed RTL/LTR content have regression coverage.

## Compatibility contract

The following behavior is frozen until an explicit reviewed change updates the contract:

- 21 public route patterns under `/[locale]` and their dynamic parameter names;
- locales `fa` and `en`, with Persian as the default redirect target;
- `Nexora / TRD BOT` brand hierarchy;
- theme values `dark` and `light` stored under `app-theme`;
- responsive acceptance widths `360`, `390`, `768`, `1024`, and `1440` pixels;
- research-only operating modes `RESEARCH`, `BACKTEST`, `PAPER`, and `SHADOW`;
- frontend API calls restricted to versioned operations present in the backend OpenAPI schema.

The freeze protects compatibility; it does not prevent additive improvements. A future change to a
frozen item must update the relevant contract test and release note in the same reviewed patch.

## Migration notes

### API imports

The former global API facades are deleted. Import domain operations and types from the owning
feature, and keep generic transport concerns in the API core.

| Retired import | Replacement |
| --- | --- |
| `@/lib/api/client` | `@/features/<feature>/api/client` |
| `@/lib/api/types` | `@/features/<feature>/api/types` or `@/lib/api/core/types` for `Page<T>` |
| `@/lib/api/portfolio-analytics` | `@/features/portfolios/api/types` |

Endpoint literals belong only in `src/features/<feature>/api/client.ts`. Feature UI should consume
the feature client rather than calling `fetch` directly.

### Shell, locale, and navigation

- Replace the deleted dashboard shell with `@/components/platform/platform-shell`.
- The old standalone language switcher is removed; locale switching is part of Platform Shell.
- Build feature destinations with the locale prefix and preserve the remaining pathname, including
  URL-encoded dynamic identifiers.
- Invalid locale values must continue to call `notFound()` at route entry points.

### Theme storage

The active storage key is `app-theme`. The bootstrap still reads legacy `trd-theme` and migrates a
valid preference, so no manual browser-storage cleanup is needed. New code must not write the
legacy key or use the old `trd-theme-change` and `trd-theme-bootstrap` identifiers.

### Environment and API origin

`NEXT_PUBLIC_API_BASE_URL` is optional for the standard local setup and defaults to
`http://127.0.0.1:8000`. For another API origin, set an absolute base URL before build or dev start:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

The backend CORS allowlist must contain the exact frontend origin. The default development config
allows `http://localhost:3000` and `http://127.0.0.1:3000`; do not enable wildcard origins with
credentials.

### Styling and responsive behavior

- Use semantic `--app-*` tokens instead of raw feature colors.
- Keep primary actions keyboard-visible and touch targets usable on mobile.
- Do not add page-level `100vw`, `w-screen`, or hidden horizontal overflow.
- Put wide data tables in a labelled, focusable scroll region.
- Every chart must retain a textual metric or summary in narrow layouts.

## Upgrade checklist

1. Reinstall dependencies with `npm ci`.
2. Update retired imports using the table above.
3. Remove custom shell-level language or theme controls.
4. Confirm the API origin and backend CORS allowlist.
5. Run `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run test`, and
   `npm run build` from `frontend`.
6. Review affected screens in both locales and themes at the five frozen viewport widths.
7. Record any intentional frozen-contract change in this document and its regression test.

## Known boundaries

- The release remains local and untagged; server deployment and public release are deferred.
- Playwright is not part of the repository toolchain, so the release has structural and component
  responsive coverage rather than pixel-diff screenshots.
- The backend's existing request-bound Experiment/Walk-forward paths remain a v0.2.0 release
  exception documented in `docs/v0.2/26-local-release-candidate.md`.
- No exchange-account credentials, live orders, deposits, or withdrawals are introduced by this UI.

## Freeze gate

The UI freeze is accepted only when the worktree is clean and all repository quality gates pass on
the same commit. GitHub Actions must report successful backend, PostgreSQL, and frontend jobs before
merge. Merge, tag, deployment, and GitHub Release each require a separate owner decision.
