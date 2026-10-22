# P3-09 — Golden Market Context Benchmark and Acceptance Evidence

وضعیت: **پیاده‌سازی‌شده و آمادهٔ اجرای evidence روی SHA مالک مخزن**

تاریخ تصمیم: `2026-10-17`

مبنای کد: P3-08 در commit محلی
`35fe6d6`

این مرحله یک benchmark کاملاً synthetic، deterministic و بدون شبکه برای مسیر واقعی Market Context
می‌سازد. خروجی آن evidence لازم P3-10 است؛ خودش Phase 3 را freeze نمی‌کند. هر گزارش فقط زمانی قابل
پذیرش است که از worktree تمیز، روی commit دقیق کاندیدا و با حداقل sample فریز‌شده تولید شده باشد.

## 1. fixture طلایی

نسخهٔ fixture برابر `market-context-golden-v1` و checksum تعریف آن برابر است با:

```text
79d082e0a2152032b033fc31d5cbb419d807b6669d93c2d2f5a994b6807ff521
```

هر سناریو 56 Window نهایی‌شدهٔ synthetic می‌سازد:

- `24 × 1h`؛
- `18 × 4h`؛
- `14 × 1d`.

قیمت‌ها از `start_price`، بازده پایه و مؤلفهٔ alternating نسخه‌دار ساخته می‌شوند. دادهٔ provider،
credential، account یا دادهٔ production در fixture وجود ندارد.

| سناریو | Trend طلایی | Volatility طلایی | Confidence | Assessment ID |
| --- | --- | --- | ---: | --- |
| `trending_up_low` | `trending_up` | `low` | `1.0000` | `market-regime-4283301875554310` |
| `trending_down_high` | `trending_down` | `high` | `1.0000` | `market-regime-52eb028d72a89621` |
| `ranging_normal` | `ranging` | `normal` | `0.9500` | `market-regime-b230710db15cef8c` |

Golden output هر سناریو فقط label نیست. manifest ID/checksum، feature snapshot ID/checksum، پنج
feature با precision دوازده رقم، assessment ID و fingerprint نهایی نیز فریز شده‌اند. بنابراین تغییر
ناخواسته در alignment، candle lineage، فرمول feature، threshold یا serialization باعث شکست evidence
می‌شود.

## 2. مسیر اندازه‌گیری

هر sample مسیر محصولی زیر را بدون mock اجرا می‌کند:

1. ساخت Candle/Event/Window نهایی‌شده؛
2. alignment چندتایم‌فریمی و ساخت manifest؛
3. محاسبهٔ feature snapshot v1؛
4. ارزیابی regime v1؛
5. مقایسهٔ خروجی و lineage با golden output.

زمان p50 و p95 هر سناریو ثبت می‌شود. budget از policy فریز‌شدهٔ job
`market_context_evaluation` خوانده می‌شود و برابر `30,000ms` است. runtime فقط aggregate می‌شود و
payload خام بازار وارد report نمی‌شود.

## 3. قرارداد fail-closed

گزارش `market-context-golden-benchmark-v1` برای هر سناریو حداقل 30 sample لازم دارد و در هر یک از
شرایط زیر ناموفق است:

- sample کمتر از حداقل؛
- exception در هر اجرای measured؛
- بیش از یک fingerprint در تکرارها؛
- اختلاف observed با golden output؛
- عبور runtime p95 از budget.

parser derived fieldهای `passed`، `failure_codes`، `failed_scenarios` و
`ready_for_phase_three_acceptance` را دوباره محاسبه می‌کند و report دست‌کاری‌شده را رد می‌کند. همچنین
fixture، feature-set و regime-policy checksumها هنگام parse دوباره با قرارداد canonical مقایسه
می‌شوند.

## 4. اجرای evidence مرجع

ابتدا تغییرات P3-09 را commit و push کنید و مطمئن شوید worktree تمیز است. سپس روی همان commit اجرا
کنید:

```bash
P3_SHA=$(git rev-parse HEAD)

PYTHONPATH=src caffeinate -i python scripts/benchmark_market_context.py \
  --samples-per-scenario 30 \
  --warmup-iterations 2 \
  --environment-label macbook-pro-reference \
  --commit-sha "$P3_SHA" \
  --output /tmp/trd-bot-p3-market-context-golden.json
```

فایل موجود overwrite نمی‌شود. برای اجرای مجدد نام تازه بدهید یا فایل قبلی `/tmp` را آگاهانه حذف
کنید. نتیجه را با این فرمان بررسی کنید:

```bash
python -m json.tool /tmp/trd-bot-p3-market-context-golden.json
```

خروجی قابل قبول باید این تصمیم را داشته باشد:

```json
{
  "failed_scenarios": [],
  "ready_for_phase_three_acceptance": true
}
```

این فایل خارج از repository باقی می‌ماند تا P3-10 بتواند checksum، تازگی، environment و برابری
`commit_sha` آن با candidate نهایی را مستقل بررسی کند.

## 5. evidence ظرفیت job با fixture v2

تعهد P3-06 برای اجرای `background-job-workloads-v2` نیز باید روی همین SHA بسته شود. ابتدا یک
PostgreSQL یک‌بارمصرف با نام شامل `benchmark` بسازید؛ برای نمونه:

```bash
docker run --name trd-bot-p3-benchmark-db17 \
  -e POSTGRES_USER=trd_p3_benchmark \
  -e POSTGRES_PASSWORD=trd_p3_benchmark_password \
  -e POSTGRES_DB=trd_bot_p3_benchmark \
  -p 55436:5432 \
  -d postgres:17-alpine

export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://trd_p3_benchmark:trd_p3_benchmark_password@localhost:55436/trd_bot_p3_benchmark'
```

سپس queue و workload evidence را با همان environment و SHA بسازید:

```bash
PYTHONPATH=src caffeinate -i python scripts/benchmark_postgresql_capacity.py \
  --database-url "$TRD_BOT_TEST_DATABASE_URL" \
  --event-count 100000 \
  --job-count 250 \
  --query-samples 200 \
  --environment-label macbook-pro-reference \
  --commit-sha "$P3_SHA" \
  --output /tmp/trd-bot-p3-postgresql-capacity.json

PYTHONPATH=src caffeinate -i python scripts/benchmark_background_job_workloads.py \
  --queue-report /tmp/trd-bot-p3-postgresql-capacity.json \
  --samples-per-kind 20 \
  --warmup-iterations 2 \
  --output /tmp/trd-bot-p3-background-jobs-capacity.json
```

در evidence دوم باید scope مربوط به background job کامل باشد، reference دقیقاً
`background-job-workloads-v2+postgresql-queue-v1` باقی بماند و metricهای زیر وجود داشته باشند:

```text
market_context_evaluation.samples = 20
market_context_evaluation.success_fraction = 1
market_context_evaluation.failure_count = 0
market_context_evaluation.runtime_within_target = 1
```

P3-10 هر دو فایل golden و background-job را با checksum و same-SHA دریافت خواهد کرد. گزارش‌های
freezeشدهٔ P0/P2 نباید با این اجرای تازه overwrite شوند.

## 6. امنیت evidence

- ورودی‌ها synthetic و public هستند؛ هیچ درخواست شبکه‌ای انجام نمی‌شود.
- report فقط identity قرارداد، outputهای مشتق‌شده و metricهای aggregate دارد.
- exception خام، environment variable، URL دیتابیس، credential و دادهٔ account ثبت نمی‌شود.
- scope همچنان `crypto-spot-public-read-only` است و هیچ مسیر order/trade اضافه نشده است.

## 7. معیار خروج P3-09

- [x] fixture و checksum نسخه‌دار و immutable تعریف شده‌اند.
- [x] سه سناریو تمام کلاس‌های trend و volatility v1 را پوشش می‌دهند.
- [x] golden lineage و feature values علاوه بر labelها فریز شده‌اند.
- [x] مسیر کامل alignment، features و regime در هر sample اجرا می‌شود.
- [x] حداقل sample، determinism و runtime budget fail-closed هستند.
- [x] report با commit، environment، Python و platform متصل است.
- [x] parser derived outcomeهای دست‌کاری‌شده را رد می‌کند.
- [x] benchmark فقط روی worktree تمیز و SHA منطبق اجرا می‌شود.
- [x] evidence فاقد secret و payload خام است.
- [ ] گزارش مرجع بعد از push روی SHA مالک مخزن با نتیجهٔ `true` تولید شود.
- [ ] گزارش `background-job-workloads-v2` روی همان SHA و محیط کامل تولید شود.

گام بعدی `P3-10 — Phase Three Acceptance and Freeze` است.
