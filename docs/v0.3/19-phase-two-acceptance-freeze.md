# P2-08 — پذیرش نهایی و Freeze مرحلهٔ دوم

وضعیت: **گیت پیاده‌سازی‌شده؛ ثبت evidence روی SHA مالک مخزن باقی است**

تاریخ تصمیم: `2026-10-15`

مبنای کد: P2-07 در commit
`cdf29ca37913458ec9660ab21958b2600fd18730`

این مرحله قابلیت محصولی، endpoint یا migration تازه اضافه نمی‌کند. هدف، اثبات کامل Live Data
Foundation در محدودهٔ `Crypto Spot / public read-only` روی یک commit تمیز است. freeze فقط وقتی
پذیرفته می‌شود که شواهد قبلی، providerها، تمام گیت‌های محلی، smoke دستی و GitHub Actions به همان
candidate متصل باشند.

## 1. ماتریس پذیرش

| gate | شاهد لازم |
| --- | --- |
| prior freeze | record پذیرفته‌شده و checksummed برای P0 و P1؛ commit هر دو ancestor کاندیدا باشد |
| provider SLO | 30 نمونهٔ زنده برای هر یک از `Kraken → Binance` روی همان SHA و در محدودهٔ policy |
| `repository_contract` | version، مرز امنیت و parserهای tamper-evident مربوط به P0/P1/P2 |
| `market_data_contract` | Event، ingestion، polling/fallback، finalization، replay، Monitoring و retention |
| `backend` | Ruff format/lint، mypy و تمام تست‌های غیر integration |
| `migration_cycle` | `upgrade head → downgrade base → upgrade head → alembic check` |
| `postgresql_resilience` | race، recovery، dedupe، lease reclaim، replay و retention روی PostgreSQL 17 |
| `frontend` | format، lint، typecheck، test و production build |
| manual smoke | stack، fallback/freshness، restart/dedupe، replay، retention hold و security inventory |
| GitHub Actions | run موفق با `head_sha` دقیقاً برابر candidate |

## 2. ویژگی fail-closed

اسکریپت `scripts/verify_v0_3_phase_two.py` موارد زیر را الزام می‌کند:

- worktree در شروع تمیز و HEAD متصل به branch باشد؛
- دیتابیس فقط PostgreSQL با نام دقیق `trd_bot_test` باشد؛
- چرخهٔ مخرب migration تأیید صریح داشته باشد؛
- P0 و P1 پذیرفته شده و SHA هر دو در تاریخچهٔ candidate باشد؛
- گزارش provider با SHA همان candidate ساخته شده باشد؛
- environment گزارش provider با verifier یکی و عمر evidence حداکثر 365 روز باشد؛
- ترتیب provider دقیقاً `kraken-public → binance-public` بماند؛
- حداقل 30 نمونه، failure حداکثر 1% و latency p95 حداکثر 3 ثانیه برای هر provider رعایت شود؛
- CI موفق و SHA آن برابر HEAD باشد؛
- فایل خروجی موجود بازنویسی نشود؛
- URL دیتابیس، credential، payload بازار و متن خام exception در evidence ذخیره نشود.

شکست یک command اجرای commandهای بعدی همان gate را متوقف می‌کند، اما سایر gateها اجرا می‌شوند تا
record نهایی تمام failureهای مستقل را قابل مشاهده نگه دارد.

## 3. دیتابیس یک‌بارمصرف PostgreSQL 17

پورت `55435` از دیتابیس‌های benchmark و P1 جدا است:

```bash
docker run --name trd-bot-p2-acceptance-db17 \
  -e POSTGRES_USER=trd_p2 \
  -e POSTGRES_PASSWORD=trd_p2_password \
  -e POSTGRES_DB=trd_bot_test \
  -p 55435:5432 \
  -d postgres:17-alpine

docker exec trd-bot-p2-acceptance-db17 \
  pg_isready -U trd_p2 -d trd_bot_test

export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://trd_p2:trd_p2_password@localhost:55435/trd_bot_test'
```

هیچ دیتابیس development، benchmark یا دارای دادهٔ قابل نگهداری نباید به verifier داده شود.

## 4. evidence زندهٔ provider روی همان SHA

گزارش را خارج از repository بسازید تا شرط clean worktree حفظ شود. برای دسترسی پایدار Binance ممکن
است همان VPN مرجع P0 لازم باشد:

```bash
P2_SHA=$(git rev-parse HEAD)

PYTHONPATH=src python scripts/benchmark_market_data_providers.py \
  --provider kraken-public \
  --provider binance-public \
  --samples-per-provider 30 \
  --interval-seconds 10 \
  --environment-label macbook-pro-vpn-reference \
  --commit-sha "$P2_SHA" \
  --output /tmp/trd-bot-p2-provider-capacity.json
```

کامل‌بودن probe به‌تنهایی کافی نیست؛ verifier مقدار failure و p95 latency هر دو provider را دوباره
مستقل از derived state گزارش بررسی می‌کند.

## 5. smoke دستی پیش از freeze

این شش مورد باید روی همان commit و همان stack واقعاً مشاهده شوند و فقط بعد با `pass` ثبت شوند:

1. API، worker، polling scheduler و frontend هم‌زمان بالا بیایند؛ health و Monitoring قابل استفاده
   باشند.
2. یک Watchlist فعال با ترتیب Kraken/Binance poll شود؛ Poll Run ترتیب attempt، provider منتخب و
   freshness/lag متناظر را در Monitoring نشان دهد. مسیر fallback نیز با unavailable شدن موقت route
   اصلی بدون fallback پنهان ثبت شود.
3. worker در میانهٔ Poll قطع و پس از انقضای lease دوباره اجرا شود؛ همان slot/job reclaim شود و
   Window، Event یا Outbox تکراری ساخته نشود.
4. یک late/correction decision به replay ماندگار برسد؛ restart نتیجه را از بین نبرد، نسخهٔ finalized
   قبلی overwrite نشود و Monitoring backlog را قبل/بعد درست نشان دهد.
5. retention ابتدا با `plan` اجرا شود؛ hold آزمایشی هر دو mode را blocked کند، پس از release فقط یک
   batch محدود حذف شود و finalized Window/lineage محافظت‌شده باقی بماند.
6. route، OpenAPI، Network و provider inventory هیچ live order، credential، account، wallet،
   deposit یا withdrawal نداشته باشند.

## 6. ساخت record نهایی

پس از push و سبزشدن هر سه job در GitHub Actions، URL و SHA همان run را وارد کنید:

```bash
P2_SHA=$(git rev-parse HEAD)

PYTHONPATH=src python scripts/verify_v0_3_phase_two.py \
  --database-url "$TRD_BOT_TEST_DATABASE_URL" \
  --confirm-destructive-migration-cycle trd_bot_test \
  --provider-capacity-report /tmp/trd-bot-p2-provider-capacity.json \
  --github-actions-run-url 'https://github.com/OWNER/REPOSITORY/actions/runs/RUN_ID' \
  --github-actions-head-sha "$P2_SHA" \
  --github-actions-conclusion success \
  --local-stack-smoke pass \
  --watchlist-fallback-smoke pass \
  --worker-restart-smoke pass \
  --late-data-replay-smoke pass \
  --retention-hold-smoke pass \
  --security-network-smoke pass \
  --environment-label macbook-pro-vpn-reference \
  --output artifacts/p2-08/phase-two-acceptance.json
```

خروجی با schema `phase-two-acceptance-record-v1` شامل checksum شواهد قبلی و provider، metricهای
ضروری، نتیجهٔ هر command، smokeها و CI است. شرط freeze نهایی:

```json
{
  "failed_gates": [],
  "provider": {
    "passed": true
  },
  "ready_to_freeze_phase_two": true
}
```

## 7. معیار خروج P2-08

- [x] verifier واحد و fail-closed برای تمام گیت‌های P2 وجود دارد.
- [x] P0/P1 با checksum، پذیرش و ancestry دوباره اعتبارسنجی می‌شوند.
- [x] provider evidence زنده، same-SHA و مطابق SLO فریز‌شده ارزیابی می‌شود.
- [x] migration cycle فقط روی `trd_bot_test` و با تأیید مخرب اجرا می‌شود.
- [x] race/recovery/dedupe/fallback/replay/retention در گیت‌های خودکار پوشش دارند.
- [x] derived outcomeهای دست‌کاری‌شده هنگام parse رد می‌شوند.
- [x] scope امنیتی public read-only صریح و تست‌شده باقی می‌ماند.
- [ ] provider benchmark نهایی روی SHA مالک مخزن پذیرفته شود.
- [ ] GitHub Actions موفق همان SHA ثبت شود.
- [ ] smoke دستی شش‌گانه روی همان SHA ثبت شود.
- [ ] record نهایی `ready_to_freeze_phase_two=true` تولید شود.

تا بسته‌شدن چهار مورد آخر، Phase 2 از نظر کد آماده است اما **freeze نشده** و ورود رسمی به P3 مجاز
نیست.
