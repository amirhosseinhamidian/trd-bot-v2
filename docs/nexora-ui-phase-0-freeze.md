# Nexora / TRD BOT UI Phase 0 Freeze

Status: **Frozen for Phase 1 implementation**

Baseline: `v0.2.0` / `219818d10622ffb4b29ceccb60f925fd8de76703`

Future merge target: `main`

Proposal: `Nexora / TRD BOT Platform-ready UI Redesign & Refactor Proposal v0.1`

This document closes the Phase 0 design and compatibility gate. It is the review contract for
the incremental UI migration. A later phase may amend this contract only through an explicit,
reviewed decision; it must not change routes or business behavior incidentally.

## 1. Preserved contracts

- All existing public URLs and dynamic parameter names remain unchanged through this milestone.
- Existing server/client boundaries, typed API behavior, loading/error states, keyboard behavior,
  RTL/LTR routing, and dark/light theme bootstrap remain regression-protected.
- Backend contracts, database schemas, strategy logic, candidate logic, risk logic, and execution
  behavior are outside this UI milestone.
- Existing screens move by the strangler pattern. Legacy modules are deleted only after their last
  consumer has migrated and the replacement tests pass.

## 2. Route inventory and screen archetypes

| Preserved route | Target IA area | Screen archetype |
| --- | --- | --- |
| `/[locale]` | Overview | Overview |
| `/[locale]/datasets` | Research / Datasets | Catalog |
| `/[locale]/datasets/[datasetId]` | Research / Datasets | Research detail |
| `/[locale]/experiments` | Research / Experiments | Catalog |
| `/[locale]/experiments/[experimentId]` | Research / Experiments | Research detail |
| `/[locale]/walk-forward` | Research / Walk-forward | Catalog |
| `/[locale]/walk-forward/[executionId]` | Research / Walk-forward | Research detail |
| `/[locale]/optimizations` | Research / Optimizations | Catalog |
| `/[locale]/optimizations/[executionId]` | Research / Optimizations | Research detail |
| `/[locale]/strategies` | Strategy & Decision / Strategies | Catalog |
| `/[locale]/strategies/[strategyName]/[version]` | Strategy & Decision / Strategies | Decision detail |
| `/[locale]/signals` | Strategy & Decision / Signals | Catalog |
| `/[locale]/signals/[experimentId]/[signalId]` | Strategy & Decision / Signals | Decision detail |
| `/[locale]/candidates` | Strategy & Decision / Candidates | Catalog |
| `/[locale]/candidates/[candidateId]` | Strategy & Decision / Candidates | Candidate detail |
| `/[locale]/risk` | Strategy & Decision / Risk | Risk |
| `/[locale]/portfolios` | Simulation / Historical Portfolios | Catalog |
| `/[locale]/portfolios/[portfolioId]` | Simulation / Historical Portfolios | Historical portfolio detail |
| `/[locale]/portfolios/[portfolioId]/positions/[positionId]` | Simulation / Historical Portfolios | Position detail |
| `/[locale]/connections` | Data / Connections | Configuration/workspace |
| `/[locale]/monitoring` | System / Monitoring | Monitoring |

Supported locale values remain `fa` and `en`. Invalid locale values continue to resolve through
the existing not-found behavior.

## 3. Frozen information architecture and labels

The grouping changes navigation presentation only. It does not change the URL column below.

| Group | English label | Persian label | Preserved destination |
| --- | --- | --- | --- |
| Root | Overview | نمای کلی | `/[locale]` |
| Research | Research | پژوهش | Section label only |
| Research | Datasets | مجموعه‌داده‌ها | `/[locale]/datasets` |
| Research | Experiments | آزمایش‌ها | `/[locale]/experiments` |
| Research | Walk-forward | تحلیل Walk-forward | `/[locale]/walk-forward` |
| Research | Optimizations | بهینه‌سازی‌ها | `/[locale]/optimizations` |
| Strategy & Decision | Strategy & Decision | استراتژی و تصمیم‌گیری | Section label only |
| Strategy & Decision | Strategies | استراتژی‌ها | `/[locale]/strategies` |
| Strategy & Decision | Signals | سیگنال‌ها | `/[locale]/signals` |
| Strategy & Decision | Candidates | کاندیدها | `/[locale]/candidates` |
| Strategy & Decision | Risk | ریسک | `/[locale]/risk` |
| Simulation | Simulation | شبیه‌سازی | Section label only |
| Simulation | Historical Portfolios | پرتفوی‌های تاریخی | `/[locale]/portfolios` |
| Data | Data | داده | Section label only |
| Data | Connections | اتصال‌های داده | `/[locale]/connections` |
| System | System | سامانه | Section label only |
| System | Monitoring | پایش سامانه | `/[locale]/monitoring` |

Brand hierarchy is frozen as `Nexora` (platform) → `TRD BOT` (active product). The combined brand
title is `Nexora / TRD BOT` in both locales. Product-supporting descriptions may be localized.

## 4. Frozen component boundaries and folder map

```text
frontend/src/
├── app/[locale]/
│   ├── (overview)/
│   ├── (research)/
│   ├── (trading)/
│   └── (system)/
├── components/
│   ├── ui/               # domain-free primitives
│   └── platform/         # shell, navigation, page frame/header, status context
├── features/
│   ├── research/
│   │   ├── datasets/
│   │   ├── experiments/
│   │   ├── walk-forward/
│   │   └── optimizations/
│   ├── strategies/
│   ├── signals/
│   ├── candidates/
│   ├── risk/
│   ├── portfolios/
│   ├── connections/
│   └── monitoring/
├── lib/api/core/         # transport, base URL, headers, cache policy, error parsing
└── platform/i18n/        # platform and shell terminology
```

Dependency rules:

1. `components/ui` must not import a feature or domain module.
2. `components/platform` may consume UI primitives and platform i18n, but contains no domain
   behavior.
3. A feature owns its presentation, feature copy, API adapter, and types.
4. `lib/api/core` owns transport concerns only.
5. Business calculations remain in domain/API outputs, not React components.
6. No circular dependency may be introduced among `ui`, `platform`, and `features`.

Route groups are deferred until the relevant migration patch and may not alter generated URLs.

## 5. Frozen design-token policy

Existing semantic `--app-*` tokens remain the compatibility layer. Phase 1 expands coverage; it
does not perform a broad rename. Raw brand colors may be used only to define semantic tokens, not
inside feature components.

### 5.1 Core palette

| Semantic role | Dark | Light |
| --- | --- | --- |
| Background | `#020817` | `#f5f9fc` |
| Surface | `#08162a` | `#ffffff` |
| Muted surface | `#0d1d34` | `#eaf2f8` |
| Border | `#1a3554` | `#c9d9e8` |
| Foreground | `#f2f8ff` | `#0a1a2f` |
| Muted text | `#9cb0c8` | `#4d647d` |
| Subtle text | `#70859f` | `#5f748a` |
| Accent | `#22d3ee` | `#0e7490` |
| Accent soft | `rgba(34, 211, 238, 0.12)` | `rgba(6, 182, 212, 0.10)` |
| Accent border | `rgba(34, 211, 238, 0.30)` | `rgba(8, 145, 178, 0.28)` |

Status roles are semantic and must cover foreground, soft background, and border variants:

| Role | Dark foreground | Light foreground |
| --- | --- | --- |
| Success | `#34d399` | `#047857` |
| Danger | `#fb7185` | `#be123c` |
| Warning | `#fbbf24` | `#b45309` |
| Info | `#38bdf8` | `#0369a1` |

Chart series order is frozen as cyan, blue, teal, violet, amber, rose. Charts consume semantic
series tokens and must also expose a textual metric/summary.

### 5.2 Spacing, radius, and typography

- Spacing scale: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64px`.
- Page gutters: `16px` mobile, `24px` tablet, `32px` desktop.
- Radius scale: `8px` small, `12px` control, `16px` card, `24px` large surface, pill only for
  compact status/labels.
- Vazirmatn remains the shared UI font for both locales in this milestone.
- Body text is `14–16px`; labels/captions are `12–14px`; page titles are responsive and start at
  `24px` on mobile. Technical IDs, formulas, and numerical data may use LTR isolation and tabular
  numerals.
- Focus indicators use the semantic accent and must remain visible in both themes.

## 6. Frozen responsive behavior

| Range | Contract |
| --- | --- |
| `320–479px` | Compact mobile navigation, stacked details/cards, no page-level horizontal scroll |
| `480–767px` | Wide mobile; two columns only where readability is preserved |
| `768–1023px` | Adaptive rail/drawer and two-column summaries |
| `1024–1439px` | Sidebar plus bounded content grid |
| `1440px+` | Bounded wide layout; content does not stretch indefinitely |

- Phase 2 replaces the mobile drawer target with a compact primary navigation for Overview,
  Research, Strategy & Decision, and More. Risk, Connections, and Monitoring live in More.
- Page actions remain visible. On mobile they stack or move to a controlled action bar/menu; no
  critical action may depend on hover or sit outside the viewport.
- Research-heavy tables may use a labelled, keyboard-accessible horizontal scroll region.
- Decision, risk, and portfolio summary data becomes cards/rows on mobile. Secondary columns may
  collapse into a detail view.
- Detail pages keep the decision summary in the first viewport; raw formulas, long identifiers,
  and configuration move into collapsible Advanced sections.

## 7. Migration map and legacy identifiers

| Current asset/debt | Target | Planned phase |
| --- | --- | --- |
| `components/layout/dashboard-shell.tsx` | `PlatformShell`, navigation, header, mobile nav, page frame | Phase 2 |
| Inline shell navigation array | Typed, config-driven grouped navigation | Phase 2 |
| `components/dashboard/dashboard-copy.ts` shell copy | `platform/i18n` | Phase 2–3 |
| `components/dashboard/*` bucket | Feature-owned modules | Phase 3–5 |
| `lib/api/client.ts` | transport core plus domain clients | Phase 4 |
| `lib/api/types.ts` | feature/domain-owned types | Phase 4 |
| `TRD Research` brand copy | `Nexora / TRD BOT` | Phase 1 |
| `trd-theme`, `trd-theme-change`, `trd-theme-bootstrap` | app/Nexora identifiers with compatibility read | Phase 1 |
| `.trd-select-content`, `trd-select-*` | `.app-select-content`, `app-select-*` | Phase 1 |
| Hard-coded emerald/red/amber/cyan statuses | semantic status tokens | Phase 1 and feature migrations |
| Scattered feature copy | feature-local copy with one convention | Phase 3–5 |

Storage-key migration must read the legacy `trd-theme` preference before writing the new key so a
user's selected theme is not reset.

## 8. Phase 0 acceptance record

- [x] Baseline tag, commit, and integration branch verified.
- [x] Existing route inventory captured and route-preservation policy frozen.
- [x] Screen archetypes captured.
- [x] English/Persian IA labels and grouping frozen.
- [x] Target folder map and dependency direction frozen.
- [x] Palette, status, chart, spacing, radius, and typography policies frozen.
- [x] Mobile navigation, table, detail, and page-action behavior frozen.
- [x] Legacy identifiers and migration map captured.
- [x] Pre-change frontend gates passed: 64 test files / 205 tests, ESLint, Prettier, and Next.js
  production build.

## 9. Authorized first Phase 1 patch

`P1-01 — Nexora identity and product context` is limited to:

- placing the approved Nexora mark in the existing shell;
- rendering `Nexora` as platform and `TRD BOT` as active product in both locales;
- replacing stale `TRD Research` metadata/brand copy with `Nexora / TRD BOT`;
- adding focused regression assertions for the new identity;
- preserving routes, navigation order, business behavior, theme identifiers, tokens, and
  responsive mechanics.

Token expansion, global identifier migration, theme palette changes, primitive restyling, and
shell/navigation restructuring are explicitly deferred to later Phase 1/2 patches.
