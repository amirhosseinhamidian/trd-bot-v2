# Nexora / TRD BOT frontend

The frontend is a Next.js 16 application for the local TRD BOT v0.2.0 research platform. It
supports Persian (`fa`, RTL) and English (`en`, LTR), dark and light themes, and 21 frozen public
route patterns.

## Local development

From the repository root, start the backend API first. Then:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. Requests without a locale prefix redirect to Persian. The frontend
uses `http://127.0.0.1:8000` by default; set `NEXT_PUBLIC_API_BASE_URL` when the API is elsewhere.
Trailing slashes are normalized, and an empty value falls back to the local default.

## Quality gates

```bash
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run build
```

Run all five gates before merging a UI change. The root GitHub Actions workflow runs the same
frontend checks for pull requests to `main` and supported branch pushes.

## Architecture contract

- `src/app/[locale]` owns route entry points; public route names and dynamic parameter names are
  frozen in `src/platform/route-contract.ts`.
- `src/components/ui` contains domain-free primitives.
- `src/components/platform` owns the shell and navigation without domain behavior.
- `src/features/<feature>` owns its screen, copy, API client, and domain types.
- `src/lib/api/core` owns transport, base-URL normalization, shared pagination, and error parsing.
- `src/platform/i18n` owns platform and shell terminology.

Do not restore imports from the retired `@/lib/api/client`, `@/lib/api/types`, or
`@/lib/api/portfolio-analytics` facades. The complete upgrade map and release boundary are in
[`../docs/nexora-ui-release-and-migration.md`](../docs/nexora-ui-release-and-migration.md).
