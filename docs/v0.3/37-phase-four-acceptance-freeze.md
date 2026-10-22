# P4-08 — benchmark، پذیرش و Freeze نهایی Phase 4

وضعیت: **گیت پیاده‌سازی‌شده؛ ثبت evidence روی SHA نهایی مالک مخزن باقی است**

این مرحله قابلیت محصولی یا migration تازه اضافه نمی‌کند. هدف آن اثبات end-to-end زنجیرهٔ Alert از
Market Context تا Alert Center، سیاست انتشار، Paper/Shadow و Outcome Journal است. مرز نسخه همچنان
`Crypto Spot / public read-only / offline alerts` است و هیچ سفارش واقعی مجاز نیست.

## ماتریس پذیرش

| Gate | شاهد لازم |
| --- | --- |
| prior freeze | record پذیرفته‌شده P3، checksum معتبر و commit آن ancestor کاندیدا باشد |
| alert benchmark | حداقل ۱۰۰ sample، یک fingerprint قطعی و p95 حداکثر ۵ms روی همان SHA |
| repository contract | parserهای tamper-evident، security boundary و freezeهای P3/P4 |
| alert contract | تمام تست‌های contracts، persistence، jobs، inbox، publication، simulation و outcome |
| backend | Ruff format/lint، mypy و تمام تست‌های non-integration |
| migration cycle | `upgrade head → downgrade base → upgrade head → alembic check` |
| PostgreSQL resilience | retry، race، reclaim، dedupe و transactionهای Alert روی PostgreSQL |
| frontend | format، lint، typecheck، test و production build |
| manual smoke | شش مشاهدهٔ end-to-end روی همان SHA |
| GitHub Actions | run موفق با `head_sha` دقیقاً برابر candidate |

## benchmark قطعی

Benchmark هیچ network request و هیچ دادهٔ محرمانه‌ای ندارد. برای هر sample هویت‌های rule، evaluation،
alert، deduplication، Paper/Shadow simulation و outcome ساخته می‌شوند. همهٔ sampleها باید یک fingerprint
یکسان تولید کنند. checksum سیاست انتشار پیش‌فرض و سیاست Outcome نیز در report pin می‌شود.

پس از commit و push کردن P4-08، benchmark را روی SHA نهایی اجرا کنید:

```bash
P4_SHA=$(git rev-parse HEAD)

PYTHONPATH=src python scripts/benchmark_alert_pipeline.py \
  --samples 1000 \
  --commit-sha "$P4_SHA" \
  --environment-label macbook-pro-reference \
  --output /tmp/trd-bot-p4-alert-benchmark-final.json
```

Benchmark فقط روی worktree تمیز اجرا می‌شود، فایل موجود را overwrite نمی‌کند و در صورت شکست با کد ۲
خارج می‌شود.

## دیتابیس یک‌بارمصرف پذیرش

چرخه migration تمام محتوای دیتابیس را پاک می‌کند؛ فقط دیتابیس دقیق `trd_bot_test` پذیرفته می‌شود:

```bash
docker run --name trd-bot-p4-acceptance-db17 \
  -e POSTGRES_USER=trd_p4 \
  -e POSTGRES_PASSWORD=trd_p4_password \
  -e POSTGRES_DB=trd_bot_test \
  -p 55438:5432 \
  -d postgres:17-alpine

export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://trd_p4:trd_p4_password@localhost:55438/trd_bot_test'
export TRD_BOT_DATABASE_URL="$TRD_BOT_TEST_DATABASE_URL"
PYTHONPATH=src python -m alembic upgrade head
```

## Smoke دستی روی candidate

هر شش مورد باید واقعاً مشاهده و سپس با `pass` ثبت شوند:

1. **Alert Center و اکشن‌ها:** صفحهٔ `/fa/alerts` و `/en/alerts`، فیلترها، detail، acknowledge و
   snooze درست کار کنند و audit action ساخته شود.
2. **Publication policy:** quiet hours، critical bypass، cooldown، duplicate، snooze و expiry دلیل
   درست ثبت کنند؛ alert منقضی حذف نشود.
3. **Worker recovery:** یک job با lease منقضی reclaim شود و retry همان evaluation/alert را بدون رکورد
   تکراری برگرداند.
4. **Paper/Shadow و Outcome:** هر دو mode فقط observation بسازند؛ outcome قبل از افق رد و بعد از افق
   immutable ثبت شود؛ summary با journal منطبق باشد.
5. **Monitoring و lineage:** وضعیت queue و آخرین خطا/بازیابی قابل مشاهده و lineage از outcome تا
   simulation، alert، rule و Market Context قابل پیگیری باشد.
6. **Security inventory:** OpenAPI، routeها، network و payloadها فاقد credential، wallet، exchange
   account، deposit/withdrawal و live-order write باشند.

## اجرای verifier نهایی

پس از سبز شدن GitHub Actions همان SHA:

```bash
P4_SHA=$(git rev-parse HEAD)

PYTHONPATH=src python scripts/verify_v0_3_phase_four.py \
  --database-url "$TRD_BOT_TEST_DATABASE_URL" \
  --confirm-destructive-migration-cycle trd_bot_test \
  --alert-benchmark-report /tmp/trd-bot-p4-alert-benchmark-final.json \
  --github-actions-run-url 'https://github.com/OWNER/REPOSITORY/actions/runs/RUN_ID' \
  --github-actions-head-sha "$P4_SHA" \
  --github-actions-conclusion success \
  --alert-center-actions-smoke pass \
  --publication-policy-smoke pass \
  --worker-recovery-smoke pass \
  --outcome-journal-smoke pass \
  --monitoring-lineage-smoke pass \
  --security-network-smoke pass \
  --environment-label macbook-pro-reference \
  --output artifacts/p4-08/phase-four-acceptance.json
```

خروجی پذیرفته‌شده باید این تصمیم مشتق‌شده را داشته باشد:

```json
{
  "failed_gates": [],
  "benchmark": {"passed": true},
  "ready_to_freeze_phase_four": true
}
```

Verifier fail-closed است: detached HEAD، worktree کثیف، دیتابیس غیرمجاز، P3 ردشده، SHA یا محیط
ناسازگار، evidence قدیمی، CI نامنطبق، smoke ناقص، gate شکست‌خورده و derived outcome دست‌کاری‌شده همگی
freeze را متوقف می‌کنند. command evidence هیچ database URL یا credential ذخیره نمی‌کند.

## معیار خروج P4-08

- [x] benchmark قطعی و same-SHA برای alert pipeline وجود دارد.
- [x] policy checksumها و نتیجهٔ benchmark tamper-evident هستند.
- [x] verifier واحد تمام قراردادها، migration، PostgreSQL، frontend و security boundary را پوشش می‌دهد.
- [x] P3 پذیرفته‌شده و ancestry آن دوباره بررسی می‌شود.
- [x] راهنمای smoke دستی و ساخت evidence ثبت شده است.
- [ ] benchmark نهایی روی SHA مالک مخزن پذیرفته شود.
- [ ] GitHub Actions موفق همان SHA ثبت شود.
- [ ] smoke دستی شش‌گانه روی همان SHA ثبت شود.
- [ ] record نهایی با `ready_to_freeze_phase_four=true` تولید و commit شود.

تا بسته‌شدن چهار مورد آخر، Phase 4 از نظر کد آماده است اما freeze عملیاتی آن هنوز انجام نشده است.
