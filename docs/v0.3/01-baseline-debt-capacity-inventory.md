# P0-02 — Baseline، بدهی‌های v0.2 و inventory ظرفیت

وضعیت: **تکمیل‌شده برای ادامهٔ Phase 0**

تاریخ بررسی: `2026-10-09`

شاخهٔ مرجع: `feature/v0.3-market-intelligence`

Commit مرجع مالک مخزن: `e702b233a427de277a6e7bf428874f94163c08f0`

این سند وضعیت قابل مشاهده در کد را پس از P0-01 ثبت می‌کند. هدف آن ساختن یک baseline صادقانه
برای طراحی قراردادهای v0.3 است؛ بنابراین ظرفیت‌هایی که اندازه‌گیری نشده‌اند با عدد تخمینی پر
نمی‌شوند. Benchmark عددی، SLO و retention در P0-04 تعیین می‌شوند.

## 1. خلاصهٔ تصمیم

هستهٔ v0.2 برای توسعهٔ v0.3 قابل استفاده است و بازنویسی لازم ندارد. Dataset immutable، provider
عمومی، Strategy/Experiment، Candidate/Risk، Paper/Shadow، صف PostgreSQL، Monitoring و رابط
فریز‌شدهٔ Nexora همگی در repository موجودند.

بااین‌حال، شروع P2 قبل از بستن بدهی‌های P1 مجاز نیست. مهم‌ترین مانع این است که همهٔ عملیات سنگین
هنوز از یک مرز durable مشترک عبور نمی‌کنند. همچنین telemetry فعلی برای تعیین SLO دادهٔ نزدیک به
real-time کافی نیست.

## 2. مشخصات baseline ایستا

| شاخص | مقدار مشاهده‌شده | شاهد |
| --- | ---: | --- |
| نسخهٔ runtime و manifest | `0.2.0` | package، config، frontend و test نسخه |
| فایل Python تولیدی | 143 | `src/**/*.py` |
| route handlerهای API | 88 | 55 `GET` و 33 `POST` در `api/routes` |
| جدول‌های SQLAlchemy | 17 | `src/trd_bot/db/models.py` |
| revisionهای Alembic | 17 | `alembic/versions` |
| فایل‌های تست backend | 146 | `tests/test_*.py` |
| test functionهای backend | 869 | شمارش ایستای توابع `test_*`؛ نه نتیجهٔ اجرا |
| routeهای عمومی frontend | 21 | `frontend/src/app/**/page.tsx` |
| فایل‌های تست frontend | 91 | Vitest |
| نتیجهٔ فعلی frontend | 429/429 موفق | اجرای P0-01 روی همین tree محصولی |
| locale | `fa` و `en` | قرارداد فریز Nexora |
| theme | dark و light | قرارداد فریز Nexora |

این شمارش‌ها snapshot معماری‌اند و معیار performance نیستند. افزایش یا کاهش آنها به‌تنهایی کیفیت
نسخه را نشان نمی‌دهد.

## 3. توپولوژی اجرای فعلی

```text
Next.js -> FastAPI -> PostgreSQL
                    -> FastAPI BackgroundTasks (Experiment / Walk-Forward)
                    -> Durable PostgreSQL Queue -> standalone worker
                                               -> Market Data Import
                                               -> Optimization Execution
```

مرز durable فعلی:

- `BackgroundJobKind` فقط `market_data_import` و `optimization_execution` دارد.
- registry تولید فقط همین دو handler را allowlist می‌کند.
- worker مستقل در هر iteration حداکثر یک job را claim و اجرا می‌کند.
- poll پیش‌فرض worker برابر 2 ثانیه و lease عمومی برابر 60 ثانیه است.
- handlerهای Import و Optimization lease را تا 5 دقیقه تمدید می‌کنند.
- صف از idempotency، retry، cancel، lease expiry و reclaim پشتیبانی می‌کند.

مرز غیر durable فعلی:

- `POST /api/v1/research/experiment-executions` اجرای کار را با FastAPI `BackgroundTasks`
  آغاز می‌کند.
- `POST /api/v1/research/walk-forward-executions` نیز همین رفتار را دارد.
- routeهای legacy اجرای مستقیم Experiment و Walk-Forward همچنان محاسبه را داخل request انجام
  می‌دهند.
- inspect، preview و commit فایل Dataset کل فایل را در request می‌خوانند و parse می‌کنند.

## 4. Provider و محدودیت‌های ورودی

| Provider | دسترسی | Pair پیش‌فرض | سقف/صفحه | timeout پیش‌فرض | نکته |
| --- | --- | --- | --- | ---: | --- |
| `nobitex-public` | direct | `BTC/USDT` | 500 در صفحه، حداکثر 100 صفحه | 10s | normalization برابر `nobitex-utc-grid-v1`؛ فاصلهٔ صفحه‌ها 1s |
| `binance-public` | VPN required | `BTC/USDT` | 1000 در صفحه | 10s | endpoint عمومی و بدون credential |
| `kraken-public` | VPN required | `BTC/USD` | حداکثر 719 کندل بستهٔ اخیر | 10s | recent-window adapter |

قرارداد مشترک retry حداکثر 3 تلاش، backoff اولیه 0.25 ثانیه، backoff حداکثر 2 ثانیه و
`Retry-After` حداکثر 30 ثانیه دارد. هر سه provider فقط Spot و timeframeهای `15m`، `1h`، `4h`
و `1d` را expose می‌کنند و credential نمی‌خواهند.

این محدودیت‌ها historical adapter هستند و هنوز قرارداد polling cadence، stream، watermark یا
freshness برای v0.3 محسوب نمی‌شوند.

## 5. سقف‌های حفاظتی موجود

| حوزه | سقف فعلی | اثر |
| --- | --- | --- |
| فایل Dataset | 10 MiB | فایل کامل در حافظهٔ request خوانده می‌شود |
| ردیف فایل | 100,000 | قبل از ساخت Dataset رد می‌شود |
| ستون فایل | 100 | قبل از normalization رد می‌شود |
| سلول فایل | 1,000,000 | کنترل ترکیبی row/column |
| payload دستی Dataset | 100,000 candle | request JSON همچنان bounded ولی synchronous است |
| Optimization | 100 trial | grid بزرگ‌تر رد می‌شود |
| Robustness folds | 3 تا 12 | قرارداد Walk-Forward Optimization |
| trial-fold run | 300 | سقف validation workload |
| retry job | حداکثر 10 در مدل، پیش‌فرض 3 | fail/retry توسط صف کنترل می‌شود |
| نمونهٔ اخیر Monitoring | 100 Import و 100 job terminal | projection عملیاتی bounded است |

هیچ‌یک از این سقف‌ها به معنی ظرفیت قابل تضمین v0.3 نیستند؛ فقط guardrailهای کد فعلی‌اند.

## 6. وضعیت ذخیره‌سازی و رشد داده

- PostgreSQL 17 تنها datastore عملیاتی تعریف‌شده است.
- 17 جدول فعلی شامل Dataset، Import، Job، Experiment، Walk-Forward، Portfolio، Monitoring و
  Candidate است.
- Snapshotهای Dataset و چند نتیجهٔ دامنه به شکل `payload_json` در ستون `Text` ذخیره می‌شوند.
- Dataset snapshot فعلی payload کامل candleها را نگه می‌دارد؛ بنابراین رشد storage با تکرار
  snapshot می‌تواند معنی‌دار شود.
- جدول مستقل برای Raw Observation، provisional window، watermark یا event outbox/inbox v0.3
  وجود ندارد.
- object storage، partitioning، TimescaleDB، ClickHouse و Redis در baseline استفاده نمی‌شوند.
- SQLAlchemy از pool پیش‌فرض استفاده می‌کند و اندازهٔ pool یا budget اتصال در config محصول
  صریح نشده است.

نتیجه: انتخاب فناوری تازه در P0-02 توجیه ندارد. ابتدا باید P0-04 حجم، latency، queue wait و رشد
storage را روی PostgreSQL فعلی اندازه‌گیری کند.

## 7. پوشش Observability

مدل Monitoring پانزده metric ظرفیت را نام‌گذاری کرده است، اما observation خودکار فعلی فقط این سه
metric process-local را تولید می‌کند:

- `api_request_latency_p95`؛
- `api_error_rate`؛
- `database_query_latency_p95`.

Collector به‌صورت پیش‌فرض خاموش است و در صورت فعال شدن هر 300 ثانیه window می‌سازد. projection
عملیاتی جداگانه queue depth، stuck lease، failure count و average job duration را از state ماندگار
می‌سازد.

metricهای زیر تعریف شده‌اند ولی collector واقعی baseline برایشان پیدا نشد:

- database pool/CPU/disk utilization؛
- job queue wait p95 و throughput؛
- backtest failure rate؛
- market-data lag و invalid-candle ratio؛
- candle storage share؛
- time-series و analytical query latency؛
- repeated-read ratio و analytical database resource share.

بنابراین dashboard فعلی برای عملیات v0.2 مفید است، اما شاهد کافی برای SLO و ظرفیت جریان پیوستهٔ
v0.3 نیست.

## 8. فهرست بدهی و تصمیم انتقال

| شناسه | بدهی/تصمیم | شدت | تصمیم و owner |
| --- | --- | --- | --- |
| V3-D01 | فایل Dataset داخل request خوانده و parse می‌شود | Blocker P2 | P1: staging امن، checksum-bound، expiry/cleanup و job durable |
| V3-D02 | Experiment Execution از FastAPI BackgroundTasks استفاده می‌کند | Blocker P2 | P1: انتقال به `BackgroundJob` با enqueue اتمیک |
| V3-D03 | Walk-Forward Execution از FastAPI BackgroundTasks استفاده می‌کند | Blocker P2 | P1: انتقال به `BackgroundJob` با progress و recovery |
| V3-D04 | routeهای legacy محاسبهٔ synchronous هنوز عمومی‌اند | High | P1: inventory مصرف‌کننده، compatibility path و cutover/deprecation تست‌شده |
| V3-D05 | فقط دو job kind در worker مستقل پشتیبانی می‌شوند | High | P1: افزودن file/experiment/walk-forward به allowlist پس از قرارداد payload |
| V3-D06 | export فقط report قطعی Experiment را به CSV می‌دهد | Medium | baseline حداقلی v0.2 پذیرفته شد؛ exportهای v0.3 فقط با use case همان فاز اضافه شوند |
| V3-D07 | Research templates، notes و tags در محصول وجود ندارند | Low برای v0.3 | خارج از Must/Should نسخه؛ به backlog پس از v0.3 منتقل شدند |
| V3-D08 | collector فقط 3 metric واقعی دارد | Blocker SLO | P0-04: benchmark harness؛ P2/P6: instrumentation ماندگار لازم |
| V3-D09 | raw observation/window/event store وجود ندارد | Expected gap | P0-03 قرارداد؛ P2 schema و implementation |
| V3-D10 | Dataset payload تکراری در Text می‌تواند storage را رشد دهد | Risk | P0-04 اندازه‌گیری؛ optimization فقط با evidence |
| V3-D11 | DB pool budget و worker concurrency صریح نیست | Risk | P0-04 baseline؛ سپس config محدود و آزمون overload در P2/P6 |
| V3-D12 | گیت کامل backend/PostgreSQL روی SHA این مرحله محلی اجرا نشده | Verification | CI و محیط مالک مخزن؛ P1 پیش از P2 همهٔ گیت‌ها را دوباره سبز می‌کند |

## 9. موارد بسته یا پذیرفته‌شده

- رابط Nexora روی 21 route، دو locale، دو theme و معماری feature-owned فریز شده است.
- CI سه job مستقل Backend، PostgreSQL و Frontend دارد؛ timeout آنها به‌ترتیب 15، 15 و 20 دقیقه
  است.
- migration chain از نظر workflow برای `base -> head -> base -> head` و `alembic check` گیت دارد.
- صف PostgreSQL race، idempotency و lease recovery را در integration test پوشش می‌دهد.
- release security test نبود route سفارش، credential معامله و provider خصوصی را کنترل می‌کند.
- CSV قطعی Experiment Report به‌عنوان minimum export baseline نسخهٔ دوم پذیرفته می‌شود.
- Research Templates، Notes و Tags برای v0.3 الزام نیستند و نباید P2 را بلوکه کنند.

## 10. ورودی لازم برای مراحل بعد

### P0-03

- قرارداد `MarketEvent` و envelope نسخه‌دار؛
- event time در برابر processing time؛
- idempotency key و dedupe؛
- provisional/final window، watermark و late arrival؛
- status و failure semantics؛
- outbox/inbox boundary بدون انتخاب زودهنگام broker تازه.

### P0-04

- سنجش واقعی provider latency/failure و request budget؛
- queue wait، runtime و throughput برای هر job kind؛
- API/DB latency و pool utilization؛
- اندازهٔ Dataset payload و نرخ رشد storage؛
- ظرفیت یک worker و حد overload؛
- تعریف SLO فقط پس از ثبت این اعداد.

### P1

- بستن V3-D01 تا V3-D05؛
- اجرای کامل backend، PostgreSQL/migration، frontend و manual smoke؛
- ثبت CI سبز روی SHA نهایی P1؛
- ممنوعیت ورود به P2 تا بسته شدن blockerها.

## 11. شاهد بررسی P0-02

- repository روی commit مرجع بدون تغییر محلی بررسی شد.
- شمارش route، table، migration، test و page با AST/path inventory بدون import runtime انجام شد.
- provider metadata، hard limitها، worker registry، queue و request-bound routeها از source بررسی
  شدند.
- `python -m compileall -q src tests` در P0-01 روی همین tree محصولی بدون خطا بود.
- frontend روی همین tree محصولی `91` فایل و `429` تست موفق داشت.
- محیط Codex dependencyهای backend و PostgreSQL را نداشت؛ نتیجهٔ pytest/migration جدید ادعا
  نمی‌شود.

## 12. معیار خروج P0-02

- [x] baseline کد و توپولوژی اجرا ثبت شد.
- [x] hard limitهای موجود از ظرفیت تضمین‌شده تفکیک شدند.
- [x] همهٔ بدهی‌های شناخته‌شده owner و phase دارند.
- [x] تصمیم Research Templates/Notes/Tags و minimum export مبهم نماند.
- [x] شکاف telemetry بدون عددسازی ثبت شد.
- [x] ورودی‌های P0-03، P0-04 و P1 مشخص شدند.

گام مجاز بعدی `P0-03 — Event Contract and Window Semantics` است. هیچ schema یا سرویس Live Data
پیش از فریز قرارداد این مرحله اضافه نمی‌شود.
