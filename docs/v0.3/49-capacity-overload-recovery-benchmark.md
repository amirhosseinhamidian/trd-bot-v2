# P6-02 - Capacity، Overload و Recovery Benchmark

وضعیت: **پیاده سازی شده؛ اجرای PostgreSQL مرجع روی SHA نهایی باقی است**

هدف این مرحله سنجش سرعت یک مسیر مصنوعی و جدا از محصول نیست. benchmark مستقیماً از
`SqlAlchemyBackgroundJobRepository`، `BackgroundJobWorker`، policy واقعی jobها و جدول migration
شده `background_jobs` استفاده می کند تا رفتار release زیر فشار و پس از قطع worker قابل ممیزی باشد.

## قرارداد ظرفیت

`trd_bot.release_capacity` policy مرحله را مستقیماً از
`market-data-service-level-policy-v1` می سازد:

| معیار | Budget |
| --- | ---: |
| Queue warning | 25 job |
| Queue overload | 100 job |
| Worker concurrency | 1 |
| PostgreSQL operation p95 | حداکثر 250ms |
| Queue wait p95 | حداکثر 10s |
| Overload drain throughput | حداقل 10 job/s |
| Concurrent claim/enqueue contenders | حداقل 8 |

Policy checksum فریز شده:

```text
8a6e4210cc88bdeb051fa879399a91baac6d94d4d9a143d3804c8fdf5ebdf76a
```

هر تغییر ناخواسته در thresholdها تست را می شکند و نیازمند تصمیم release جدید است.

## پوشش Benchmark

Runner روی database اختصاصی PostgreSQL که در migration head قرار دارد:

1. دقیقاً 100 job را میان تمام `BackgroundJobKind`های allowlist توزیع می کند؛
2. رسیدن صف به وضعیت `overload` را ثبت می کند؛
3. صف را با یک worker واقعی و handler محدود بدون شبکه یا secret تخلیه می کند؛
4. enqueue p95، queue-wait p95، worker-cycle p95 و throughput را می سنجد؛
5. یک job را هم زمان در اختیار 8 claimer قرار می دهد و دقیقاً یک winner می پذیرد؛
6. 8 enqueue با idempotency key یکسان را به یک job واحد collapse می کند؛
7. lease منقضی شده را با همان job ID و attempt دوم reclaim می کند؛
8. mutation مالک قدیمی lease را با conflict رد می کند؛
9. retry را با حفظ job ID و افزایش attempt اجرا می کند؛
10. تمام rowهای benchmark را در `finally` حذف و نبود residue را بررسی می کند.

گزارش فقط metricهای sanitized، نسخه Python، platform، label محیط، commit SHA، policy checksum و
report checksum را ثبت می کند. DSN، credential و payload محصول در artifact نوشته نمی شوند.

## اجرای مرجع روی PostgreSQL 17

این مرحله باید پس از commit تغییرات اجرا شود تا report به SHA نهایی متصل باشد:

```bash
docker run --name trd-bot-p6-02-db17 \
  -e POSTGRES_DB=trd_bot_test \
  -e POSTGRES_USER=trd_p6 \
  -e POSTGRES_PASSWORD=trd_p6_password \
  -p 55441:5432 \
  -d postgres:17-alpine

export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://trd_p6:trd_p6_password@localhost:55441/trd_bot_test'

python -m alembic upgrade head

PYTHONPATH=src python scripts/benchmark_v0_3_release_capacity.py \
  --environment-label macbook-pro-reference \
  --output /tmp/trd-bot-p6-02-release-capacity.json
```

Database باید اختصاصی باشد، نام آن شامل `test` یا `bench` باشد، دقیقاً در migration head قرار داشته
باشد و پیش از benchmark هیچ job فعال نداشته باشد. runner هیچ migration اجرا نمی کند و database
ناامن، SQLite، schema عقب مانده یا output موجود را fail-closed رد می کند.

خروجی موفق باید این ویژگی ها را داشته باشد:

- `passed=true` و `failure_reasons=[]`؛
- `commit_sha` برابر SHA کامیت P6-02؛
- `overload_depth_observed >= 100`؛
- `succeeded_jobs == requested_jobs` و active/failed برابر صفر؛
- claim winner، unique duplicate enqueue، retry و reclaim همگی مطابق قرارداد؛
- `cleanup_verified=true`.

## گیت های کد

```bash
python -m pytest \
  tests/test_release_capacity.py \
  tests/test_background_jobs.py \
  tests/test_background_job_capacity.py \
  -q

python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
python -m pytest -m integration -q
```

CI استاندارد repository باید روی همان SHA برای backend، PostgreSQL و frontend سبز باشد.

## Cleanup

```bash
docker rm -f trd-bot-p6-02-db17
unset TRD_BOT_TEST_DATABASE_URL

docker ps -a \
  --filter 'name=^/trd-bot-p6-02-db17$' \
  --format '{{.Names}}'
```

دستور آخر نباید نامی برگرداند.

## معیار خروج P6-02

- [x] policy ظرفیت release از SLO فریز شده مشتق و checksumدار است.
- [x] overload، drain، latency و throughput fail-closed ارزیابی می شوند.
- [x] concurrency، idempotency، retry، reclaim و stale-owner fencing پوشش داده شده اند.
- [x] runner فقط PostgreSQL اختصاصی و migration head را می پذیرد.
- [x] artifact در برابر outcome/checksum دست کاری شده مقاوم است.
- [ ] benchmark مرجع روی PostgreSQL 17 و SHA نهایی موفق شود.
- [ ] تست integration و GitHub Actions روی همان SHA سبز شوند.

پس از بستن این گیت، مرحله مجاز بعدی `P6-03 - Outcome/Learning Review` است.
