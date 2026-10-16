# P3-06 — Durable Market Context Jobs

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P3-07**

تاریخ تصمیم: `2026-10-16`

مبنای کد: P3-05 در commit محلی `ff69383`

این مرحله pipeline قطعی P3-03 تا P3-05 را به صف durable موجود متصل می‌کند. یک job مجاز، windowهای
finalized را align می‌کند، feature snapshot را می‌سازد و assessment نهایی regime را در یک transaction
ثبت می‌کند. هیچ endpoint یا UI جدیدی در این مرحله اضافه نشده است؛ آن مرز متعلق به P3-08 است.

## 1. قرارداد payload

`MarketContextEvaluationJobPayload` با schema نسخهٔ
`market-context-evaluation-job-v1` فقط این intent محدود را حمل می‌کند:

- `source` و `TradingPair` نرمال‌شده؛
- `as_of` دقیقاً روی مرز ساعتی UTC؛
- `requested_at` ثابت و نه زودتر از `as_of`؛
- نسخهٔ alignment policy؛
- نسخه و checksum feature-set؛
- نسخه و checksum الگوریتم regime.

نسخه‌ها و checksumها هنگام parse دوباره با تعریف canonical کد تطبیق داده می‌شوند. بنابراین payload
قدیمی یا دست‌کاری‌شده به‌جای اجرای تقریبی به‌صورت terminal رد می‌شود.

## 2. idempotency

کلید job از hash canonical intent ساخته می‌شود و `requested_at` عمداً در hash نیست. درخواست دوباره
برای همان `source/pair/as_of` و همان نسخه‌های policy به همان job متصل می‌شود، ولی payload و
`requested_at` اولین درخواست را حفظ می‌کند.

ثابت ماندن `requested_at` برای retry ضروری است. این مقدار زمان منطقی alignment و `created_at`
manifest است؛ در نتیجه reclaim همان manifest، feature snapshot و assessment را دقیقاً بازتولید
می‌کند و با ID یکسان اما محتوای زمانی متفاوت برخورد نمی‌کند.

## 3. transaction اتمیک

`SqlAlchemyMarketContextEvaluationRunner` در یک transaction این مسیر را اجرا می‌کند:

1. `SqlAlchemyMarketContextAssembler` و stage manifest؛
2. `SqlAlchemyMarketContextFeatureCalculator` و stage feature snapshot؛
3. `SqlAlchemyMarketRegimeEvaluator` و stage assessment؛
4. تطبیق assessment نهایی با intent نسخه‌دار job.

اگر هر مرحله fail یا cancel شود، هر سه artifact rollback می‌شوند. هیچ manifest یا feature ناقص در
پایگاه داده باقی نمی‌ماند. commit موفق پیش از ثبت success صف انجام می‌شود؛ اگر worker در این فاصله
crash کند، lease منقضی reclaim می‌شود و اجرای مجدد به artifactهای immutable موجود متصل خواهد شد.

## 4. policy صف و failureها

kind جدید `market_context_evaluation` در allowlist production و handler registry ثبت شده است:

| Policy | مقدار |
| --- | ---: |
| حداکثر attempt | 3 |
| backoff بعد از attempt اول | 5s |
| backoff بعد از attempt دوم | 30s |
| lease | 5m |
| cancellation | cooperative |
| runtime p95 target | 30s |

رفتار خطاها fail-closed است:

- payload نامعتبر: `invalid_market_context_evaluation_job_payload` و بدون retry؛
- ورودی finalized ناکافی یا stale: `market_context_inputs_not_ready` و قابل retry؛
- ناسازگاری deterministic در lineage/result: `market_context_evaluation_rejected` و بدون retry؛
- خطای زیرساختی پیش‌بینی‌نشده: policy عمومی worker و retry محدود؛
- پایان attempt سوم: همان error code پایدار روی job terminal حفظ می‌شود.

## 5. reclaim و cancellation

در شروع کار و بین مرزهای alignment، feature calculation و regime evaluation درخواست cancellation
بررسی می‌شود. cancellation با exception داخلی transaction را rollback می‌کند؛ سپس lifecycle عمومی
worker job را `cancelled` می‌سازد.

اگر lease پس از commit artifactها ولی پیش از `succeed` منقضی شود، attempt بعدی:

- همان manifest را از checksum پیدا می‌کند؛
- همان feature snapshot را بازتولید می‌کند؛
- همان assessment را بازتولید می‌کند؛
- تنها یک نسخه از هر artifact نگه می‌دارد؛
- assessment ID را به‌عنوان `result_reference` job منتشر می‌کند.

## 6. benchmark contract

افزوده شدن kind جدید، fixture کامل jobها را به `background-job-workloads-v2` ارتقا می‌دهد. workload
جدید روی SQLite موقت، 56 window finalized شامل `24×1h`، `18×4h` و `14×1d` را stage می‌کند و مسیر
واقعی enqueue، alignment، feature calculation و regime evaluation را بدون شبکه یا secret اجرا
می‌کند.

گزارش‌های ظرفیت P0/P2 شواهد تاریخی commitهای freezeشده هستند و تغییر نمی‌کنند. benchmark بعدی باید
با fixture v2 و روی commit جدید تولید شود؛ این کار در P3-09 انجام خواهد شد.

## 7. مرز امنیتی

Job فقط windowهای public market data و artifactهای مشتق‌شده را می‌خواند و می‌نویسد. هیچ credential،
exchange account، wallet، deposit، withdrawal، live order یا adapter نوشتن به صرافی اضافه نشده است.
payload و errorهای صف نیز دادهٔ حساس یا exception خام را منتشر نمی‌کنند.

## 8. معیار خروج P3-06

- [x] payload نسخه‌دار، محدود و checksum-bound است.
- [x] enqueue برای intent یکسان idempotent است.
- [x] pipeline سه‌مرحله‌ای در یک transaction اجرا می‌شود.
- [x] ورودی stale/ناکافی بدون artifact ناقص retry می‌شود.
- [x] mismatch قطعی به‌صورت terminal و sanitized رد می‌شود.
- [x] cancellation باعث rollback می‌شود.
- [x] reclaim پس از commit، artifact تکراری تولید نمی‌کند.
- [x] نتیجهٔ job به assessment نهایی اشاره می‌کند.
- [x] allowlist، policy، registry و benchmark fixture kind جدید را پوشش می‌دهند.
- [x] محدودهٔ public read-only حفظ شده است.

گام بعدی `P3-07 — Market Context Monitoring and Freshness` است.
