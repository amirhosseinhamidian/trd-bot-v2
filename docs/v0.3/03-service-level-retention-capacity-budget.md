# P0-04 — SLO، Retention، Provider Budget و Capacity Benchmark

وضعیت: **Policy و benchmark contract فریز؛ evidence محیط مرجع باز**

تاریخ تصمیم: `2026-10-09`

مبنای کد: `feature/v0.3-market-intelligence`

این مرحله عددهای عملیاتی v0.3 را به‌صورت policy نسخه‌دار ثبت می‌کند و هم‌زمان جلوی تبدیل
اندازه‌گیری ناقص به ادعای ظرفیت را می‌گیرد. ورود به P0-05 فقط پس از تکمیل پنج scope شاهد در محیط
مرجع مجاز است.

## 1. تفکیک Target و Evidence

عددهای `market-data-service-level-policy-v1` هدف عملیاتی و guardrail هستند؛ capacity تضمین‌شده
نیستند. گزارش `market-data-capacity-benchmark-v1` باید مشخص کند هر target روی چه commit، محیط،
روش و تعداد مشاهده سنجیده شده است.

پنج scope مستقل و اجباری‌اند:

1. Provider عمومی و شبکهٔ deployment؛
2. پردازش Event و Window؛
3. PostgreSQL؛
4. صف و worker؛
5. رشد واقعی Storage.

هر scope ناقص یا unavailable باعث `ready_to_freeze=false` می‌شود. projection اندازهٔ JSON جای
اندازه‌گیری row، index و WAL در PostgreSQL را نمی‌گیرد و SQLite نیز شاهد جایگزین PostgreSQL نیست.

## 2. Freshness و Watermark SLO

SLO فقط روی windowهای eligible محاسبه می‌شود: provider در دسترس بوده، pair در watchlist فعال بوده
و maintenance ثبت‌شده وجود نداشته است. denominator یا exclusion پنهان مجاز نیست.

| Timeframe | Polling | Allowed lateness | Provisional p95 | Finalized p95 | Future skew | موفقیت window |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `15m` | 60s | 180s | 120s | 300s | 30s | 99% |
| `1h` | 120s | 300s | 300s | 600s | 30s | 99% |
| `4h` | 300s | 900s | 600s | 1800s | 30s | 99% |
| `1d` | 600s | 1800s | 1200s | 3600s | 30s | 99% |

تعریف‌ها:

- `provisional freshness = first_valid_observed_at - window_end`؛
- `finalized freshness = finalized_at - window_end`؛
- Event با `event_time > processing_time + 30s` تا بررسی clock skew پذیرفته نمی‌شود؛
- Event با `event_time <= watermark_time` مطابق P0-03 late است؛
- window ناموجود، invalid یا late در numerator موفقیت وارد نمی‌شود، اما از denominator حذف نیز
  نمی‌شود؛ outcome آن صریح ثبت می‌شود.

این اعداد برای polling نزدیک به real-time در مقیاس دقیقه‌اند، نه HFT یا tick trading.

## 3. Provider Request Budget

برای هر یک از adapterهای `nobitex-public`، `binance-public` و `kraken-public` سقف داخلی محافظه‌کارانه
یکسان است:

| Budget | مقدار |
| --- | ---: |
| sustained request | 10 درخواست در دقیقه |
| burst | 3 درخواست |
| concurrency | 2 درخواست |
| timeout | 10s |
| attempts | حداکثر 3 |
| `Retry-After` | حداکثر 30s |
| HTTP latency p95 target | 3s |
| failure fraction target | حداکثر 1% |
| حداقل نمونه برای تصمیم | 30 نمونه برای هر provider/environment |

این سقف‌ها rate limit اعلامی provider نیستند و تغییر مستندات بیرونی آنها را خودکار تغییر نمی‌دهد.
اگر provider limit پایین‌تری داشته باشد، حد پایین‌تر حاکم است. پاسخ `429`، geo-block، timeout و
payload نامعتبر failure مستقل‌اند و fallback نباید آنها را پنهان کند.

انتخاب provider اصلی هنوز از این جدول نتیجه نمی‌شود. eligibility نیازمند حداقل 30 probe از همان
شبکه‌ای است که runtime روی آن deploy خواهد شد. Providerهای VPN-required باید در محیط VPN و direct
با labelهای جداگانه سنجیده شوند.

## 4. Retention Policy

Retention به معنی زمان مجاز شدن حذف است، نه حذف خودکار. اجرای purge در P2 باید batch محدود، audit
و dry-run داشته باشد.

| Record | Retention |
| --- | ---: |
| raw observation | 30 روز |
| normalized Event | 90 روز |
| inbox/deduplication identity | 180 روز |
| outbox تحویل‌شده | 7 روز |
| outbox شکست‌خورده | 30 روز |
| provisional version پس از finalization | 30 روز |
| finalized window | بدون حذف خودکار |
| revision/replay evidence | 365 روز |
| benchmark evidence | 365 روز |

قواعد:

- tombstone مربوط به dedupe پیش از Event نرمال‌شده منقضی نمی‌شود؛
- revision evidence باید از horizon مربوط به dedupe طولانی‌تر باشد؛
- Dataset، Experiment و decision snapshotهای immutable از retention عملیاتی Event مستقل‌اند؛
- legal hold یا incident hold همیشه purge را متوقف می‌کند؛
- تغییر این policy نیازمند schema version و migration plan است.

## 5. Capacity Budget اولیه

| Metric | Target/Guardrail |
| --- | ---: |
| Event contract processing p95 | حداکثر 10ms |
| Event contract throughput | حداقل 1000 event/s |
| DB query p95 | حداکثر 250ms |
| DB pool utilization p95 | حداکثر 80% |
| Queue wait p95 | حداکثر 10s |
| Queue warning | 25 job |
| Queue overload | 100 job |
| Worker concurrency baseline | 1 |
| Storage growth warning | 5 GiB در 30 روز |

Runtime p95 برای jobهای فعلی:

| Job kind | Runtime p95 target |
| --- | ---: |
| `dataset_file_import` | 120s |
| `market_data_import` | 120s |
| `experiment_execution` | 60s |
| `walk_forward_execution` | 300s |
| `optimization_execution` | 600s |

این runtimeها با workload fixture نسخه‌دار سنجیده می‌شوند. مقایسهٔ دو benchmark با تعداد candle،
trial یا fold متفاوت معتبر نیست. افزایش concurrency فقط وقتی مجاز است که queue wait از target عبور
کند و DB pool، CPU و memory headroom حداقل 20% باقی بماند.

## 6. Benchmark contract

مدل‌های `src/trd_bot/market_data/service_levels.py` شامل این قراردادها هستند:

- `MarketDataServiceLevelPolicy`؛
- `TimeframeServiceLevel`؛
- `ProviderRequestBudget`؛
- `MarketDataRetentionPolicy`؛
- `MarketDataCapacityBudget`؛
- `CapacityBenchmarkReport` و `CapacityEvidence`.

Evidence باید sanitized باشد و credential، response body، DSN یا payload کاربر را نگه ندارد. هر
گزارش commit SHA کامل، label محیط، Python version، platform، observed count و metricها را ثبت
می‌کند. scope ناقص با `complete=false` و limitation صریح باقی می‌ماند.

## 7. Harness پردازش Event

فرمان زیر یک workload synthetic و deterministic می‌سازد، validation، idempotency، تصمیم window،
duplicate path و serialization را اندازه می‌گیرد و storage خام JSON را projection می‌کند:

```bash
PYTHONPATH=src python scripts/benchmark_market_data_capacity.py \
  --iterations 20000 \
  --warmup-iterations 1000 \
  --pair-count 1 \
  --environment-label macbook-pro-reference \
  --output artifacts/p0-04/event-capacity.json
```

خروجی این harness عمداً exit code `2` دارد تا زمانی که Provider، PostgreSQL، Job و storage واقعی
به گزارش مرجع متصل شوند. این exit code شکست microbenchmark نیست؛ gate ناقص P0-04 است.

Smoke run محیط Codex با 1000 observation قرارداد را اجرا کرد و report معتبر ساخت، اما به دلیل تفاوت
سخت‌افزار و نبود PostgreSQL/شبکهٔ deployment، عدد آن baseline محصول نیست و commit نمی‌شود.

## 8. اجرای Provider Benchmark مرجع

Runner تکرارشونده از Probe عمومی sanitized استفاده می‌کند و response body را نگه نمی‌دارد. نمونهٔ
زیر دو provider کاندید را هرکدام 30 بار با فاصلهٔ 10 ثانیه می‌سنجد:

```bash
PYTHONPATH=src python scripts/benchmark_market_data_providers.py \
  --provider nobitex-public \
  --provider kraken-public \
  --samples-per-provider 30 \
  --interval-seconds 10 \
  --environment-label macbook-pro-reference \
  --output artifacts/p0-04/provider-capacity.json
```

برای eligibility حداقل 30 نمونه در چند window زمانی لازم است. اجرای پشت‌سرهم بدون فاصله برای نتیجهٔ
latency معتبر نیست. خروجی p50/p95، success/failure fraction، rate-limit، timeout، invalid response
و geo-block را به تفکیک provider ثبت می‌کند. Primary/fallback order فقط بعد از این evidence فریز
می‌شود.

## 9. PostgreSQL و Worker benchmark مرجع

Runner فقط PostgreSQL را می‌پذیرد و نام database باید شامل `test` یا `bench` باشد. یک schema یکتای
`p0_04_bench_*` می‌سازد، اندازه‌گیری را انجام می‌دهد و همان schema را در `finally` پاک می‌کند؛ هیچ
جدول محصولی truncate یا overwrite نمی‌شود.

```bash
export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://.../trd_bot_benchmark'

PYTHONPATH=src python scripts/benchmark_postgresql_capacity.py \
  --event-count 100000 \
  --job-count 250 \
  --query-samples 200 \
  --environment-label macbook-pro-reference \
  --output artifacts/p0-04/postgresql-capacity.json
```

این runner موارد زیر را ثبت می‌کند:

- enqueue، claim و terminal write latency؛
- queue wait p50/p95 و throughput با concurrency برابر 1؛
- lifecycle p95 هر پنج job kind با bounded no-op fixture؛
- pool checked-out/max utilization؛
- query latency p50/p95 برای inbox، current window و time-range read؛
- row، index، TOAST و WAL bytes برای حداقل 100,000 Event؛

Database و Storage با workload کامل می‌توانند `complete=true` شوند. scope مربوط به Job عمداً
`complete=false` می‌ماند، چون no-op lifecycle جای runtime واقعی Import، Experiment، Walk-Forward و
Optimization را نمی‌گیرد.

استفاده از production dataset یا secret در benchmark ممنوع است. fixture باید synthetic، قابل حذف و
روی database جدا باشد.

## 10. ادغام evidence

سه گزارش باید commit SHA، label محیط، Python version و platform یکسان داشته باشند. merge در صورت
اختلاف fail می‌شود و دو evidence کامل متعارض را حدس نمی‌زند:

```bash
PYTHONPATH=src python scripts/merge_market_data_capacity_reports.py \
  artifacts/p0-04/event-capacity.json \
  artifacts/p0-04/provider-capacity.json \
  artifacts/p0-04/postgresql-capacity.json \
  --output artifacts/p0-04/reference-capacity.json
```

تا وقتی runtime واقعی پنج job kind اضافه نشده باشد، خروجی merged باید exit code `2` و
`ready_to_freeze=false` داشته باشد.

## 11. تصمیم معماری تا زمان evidence

- PostgreSQL datastore و durable queue فعلی باقی می‌ماند؛
- Redis، TimescaleDB، ClickHouse، Kafka و microservice اضافه نمی‌شوند؛
- provider اصلی و fallback order فریز نمی‌شوند؛
- worker concurrency از 1 بالاتر نمی‌رود؛
- Storage optimization فقط بعد از مشاهدهٔ row/index/WAL growth مجاز است؛
- عبور target به‌تنهایی migration معماری ایجاد نمی‌کند؛ حداقل سه window متوالی و root-cause لازم
  است.

## 12. گیت خروج P0-04

- [x] Freshness، lateness و clock-skew target نسخه‌دار شدند.
- [x] Provider request budget و minimum sample ثبت شد.
- [x] Retention و عدم حذف finalized window ثبت شد.
- [x] Queue، DB، worker و storage guardrail عددی شدند.
- [x] Benchmark/report contract به شکل fail-closed پیاده شد.
- [x] Event microbenchmark تکرارپذیر و sanitized ساخته شد.
- [x] Provider benchmark با sample floor و metricهای تجمیعی ساخته شد.
- [x] PostgreSQL/Queue/Storage runner ایزوله و دارای cleanup ساخته شد.
- [x] Merge gate سازگاری محیط و تعارض evidence ساخته شد.
- [ ] Provider evidence محیط deployment برای adapterهای eligible ثبت شود.
- [ ] PostgreSQL و pool evidence محیط مرجع ثبت شود.
- [ ] Queue/runtime evidence پنج job kind ثبت شود.
- [ ] Storage row/index/WAL evidence ثبت شود.
- [ ] گزارش نهایی `ready_to_freeze=true` شود.

تا بسته شدن پنج مورد آخر، P0-04 **کامل نشده** و P0-05 نباید freeze نهایی Phase 0 را تأیید کند.
