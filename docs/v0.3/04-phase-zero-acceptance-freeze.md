# P0-05 — Acceptance Matrix و Freeze نهایی Phase 0

وضعیت: **گیت پیاده‌سازی شده؛ freeze منتظر evidence محیط مرجع**

تاریخ تصمیم: `2026-10-10`

مبنای کد: `feature/v0.3-market-intelligence`

این مرحله تصمیم‌های Phase 0 را به یک گیت fail-closed متصل می‌کند. وجود سند یا کامل بودن پنج scope
به‌تنهایی برای freeze کافی نیست: providerهای منتخب و تمام targetهای عددی نیز باید با evidence همان
commit و همان محیط قبول شوند. هیچ flag یا مسیر operator override برای تبدیل نتیجهٔ ناموفق به موفق
وجود ندارد.

## 1. ماتریس پذیرش

| شناسه | تصمیم | Owner | مرحله تحویل | گیت |
| --- | --- | --- | --- | --- |
| `P0-A01` | محدوده Crypto Spot، مقیاس و execution boundary صریح است | Product و Architecture | P0 | repository evidence |
| `P0-A02` | Live Execution و credential خصوصی خارج از محدوده است | Security | P0 | repository evidence |
| `P0-A03` | بدهی‌های v0.2 دارای owner و phase هستند | Platform | P1 | repository evidence |
| `P0-A04` | Event، ordering، watermark و window lifecycle فریز است | Market Data | P2 | repository evidence |
| `P0-A05` | SLO، retention، provider budget و targetها نسخه‌دارند | Market Data و Operations | P0 | repository evidence |
| `P0-A06` | provider اصلی و fallbackها budget واقعی را پاس می‌کنند | Market Data | P2 | provider selection |
| `P0-A07` | پنج scope کامل‌اند و targetهای ظرفیت را پاس می‌کنند | Platform و Operations | P2/P6 | capacity targets |
| `P0-A08` | بستن بدهی‌های P1 پیش‌نیاز P2 باقی می‌ماند | Platform | P1 | repository evidence |

ماتریس از `default_phase_zero_acceptance_matrix()` ساخته می‌شود. هر ردیف owner، phase و حداقل یک
reference داخل repository دارد. حذف یک فایل شاهد، ناقص بودن report، نبود metric یا عبور نکردن از
target، همان ردیف را ناموفق می‌کند و `ready_to_freeze=false` باقی می‌ماند.

## 2. ارزیابی provider order

Primary و حداقل یک fallback باید صریحاً در زمان ساخت freeze record اعلام شوند. برای هر provider:

- شناسه باید در `market-data-service-level-policy-v1` budget داشته باشد؛
- حداقل 30 probe در report موجود باشد؛
- failure fraction حداکثر 1% باشد؛
- HTTP latency p95 حداکثر 3 ثانیه باشد؛
- scope مربوط به Provider باید از live probe یا production telemetry کامل شده باشد.

ترتیب providerها از latency به‌صورت پنهان حدس زده نمی‌شود. انتخاب انسان ثبت می‌شود، اما eligibility
آن با evidence کنترل می‌شود. تکرار یک provider در primary و fallback مجاز نیست.

## 3. ارزیابی targetهای ظرفیت

گیت `P0-A07` این موارد را مستقیماً از report نهایی می‌خواند:

- Event contract latency p95 و throughput؛
- سه query p95 PostgreSQL و pool utilization؛
- queue wait p95؛
- runtime p95 هر پنج `BackgroundJobKind`؛
- projection رشد 30روزه با استفاده از اندازهٔ واقعی PostgreSQL و event count.

Merge اکنون metricهای مکمل یک scope را حفظ می‌کند. بنابراین projection تعداد Event از event runner
در کنار row/index evidence گزارش PostgreSQL باقی می‌ماند. اگر دو report برای یک metric هم‌نام مقدار
متفاوت بدهند، merge به‌جای انتخاب دلخواه fail می‌شود.

فرمول storage:

```text
projected_actual_storage_bytes_per_30_days =
  events_total_bytes / measured_event_count * projected_events_per_30_days
```

حد نهایی همان 5 GiB برای یک pair مرجع و چهار timeframe فریز‌شده است. تغییر pair count نیازمند اجرای
مجدد event benchmark با مقدار جدید است.

## 4. اجرای کامل روی Mac مرجع

همهٔ فرمان‌ها باید بعد از checkout شدن commit نهایی P0-05 اجرا شوند. label محیط در چهار گزارش باید
دقیقاً یکسان باشد و هیچ فایل خروجی موجودی overwrite نمی‌شود.

```bash
mkdir -p artifacts/p0-04 artifacts/p0-05

PYTHONPATH=src python scripts/benchmark_market_data_capacity.py \
  --iterations 20000 \
  --warmup-iterations 1000 \
  --pair-count 1 \
  --environment-label macbook-pro-reference \
  --output artifacts/p0-04/event-capacity.json

PYTHONPATH=src python scripts/benchmark_market_data_providers.py \
  --provider nobitex-public \
  --provider kraken-public \
  --samples-per-provider 30 \
  --interval-seconds 10 \
  --environment-label macbook-pro-reference \
  --output artifacts/p0-04/provider-capacity.json

export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://.../trd_bot_benchmark'

PYTHONPATH=src python scripts/benchmark_postgresql_capacity.py \
  --event-count 100000 \
  --job-count 250 \
  --query-samples 200 \
  --environment-label macbook-pro-reference \
  --output artifacts/p0-04/postgresql-capacity.json

PYTHONPATH=src python scripts/benchmark_background_job_workloads.py \
  --queue-report artifacts/p0-04/postgresql-capacity.json \
  --samples-per-kind 20 \
  --warmup-iterations 2 \
  --output artifacts/p0-04/background-jobs-capacity.json

PYTHONPATH=src python scripts/merge_market_data_capacity_reports.py \
  artifacts/p0-04/event-capacity.json \
  artifacts/p0-04/provider-capacity.json \
  artifacts/p0-04/postgresql-capacity.json \
  artifacts/p0-04/background-jobs-capacity.json \
  --output artifacts/p0-04/reference-capacity.json
```

سپس provider order انتخاب‌شده به گیت نهایی داده می‌شود:

```bash
PYTHONPATH=src python scripts/freeze_v0_3_phase_zero.py \
  --capacity-report artifacts/p0-04/reference-capacity.json \
  --primary-provider nobitex-public \
  --fallback-provider kraken-public \
  --output artifacts/p0-05/phase-zero-freeze.json
```

انتخاب بالا فقط نمونهٔ دستور است و recommendation محسوب نمی‌شود. Primary/fallback باید بعد از دیدن
اعداد واقعی report انتخاب شوند.

## 5. قرارداد خروجی و exit code

خروجی `phase-zero-freeze-record-v1` شامل commit SHA، checksum گزارش capacity، محیط، زمان، provider
order، نتیجهٔ هشت ردیف، observationهای عددی و failure reasonهای sanitized است. checksum، freeze
record را به همان محتوای report ورودی متصل می‌کند. دو فیلد derived نیز ثبت می‌شوند:

- `ready_to_freeze`؛
- `missing_requirements`.

Parser هرگونه تغییر دستی ناسازگار در این دو فیلد را رد می‌کند. CLI با نتیجهٔ کامل exit code `0` و
با هر requirement ناموفق exit code `2` می‌دهد. خطای ورودی، mismatch commit یا فایل نامعتبر نیز بدون
ساخت freeze record متوقف می‌شود.

## 6. گیت خروج P0-05

- [x] همهٔ تصمیم‌های Phase 0 دارای owner، delivery phase و evidence reference شدند.
- [x] provider order به budget و live evidence متصل شد.
- [x] targetهای Event، DB، Queue، Job و Storage قابل ارزیابی شدند.
- [x] merge از حذف metricهای مکمل جلوگیری می‌کند.
- [x] freeze record نسخه‌دار، قابل parse و tamper-evident ساخته شد.
- [ ] چهار benchmark روی commit نهایی و محیط Mac مرجع اجرا شوند.
- [ ] provider order بر اساس report واقعی انتخاب شود.
- [ ] `phase-zero-freeze.json` با `ready_to_freeze=true` ثبت شود.
- [ ] CI همان commit برای backend، PostgreSQL و frontend سبز باشد.

تا بسته شدن چهار مورد آخر، وضعیت Phase 0 **evidence pending** است و شروع P1 مجاز نیست.
