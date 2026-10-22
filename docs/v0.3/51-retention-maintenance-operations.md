# P6-04 - Retention and Maintenance Operations

وضعیت: **پیاده سازی شده؛ اجرای plan و عملیات مرجع روی PostgreSQL و SHA نهایی باقی است**

این مرحله عملیات نگهداری پراکندهٔ نسخه را در یک plan تجمیعی و commit-bound قابل مشاهده می کند.
ساخت plan هیچ purge، cleanup، rebuild یا سفارش معاملاتی اجرا نمی کند؛ فقط dry-run مربوط به Market Data
را به عنوان audit ماندگار ثبت می کند و سه حوزهٔ دیگر را با queryهای aggregate بررسی می کند.

## دامنهٔ plan

| Action | منبع Evidence | رفتار plan |
| --- | --- | --- |
| Market Data retention | policy و manager فریز شدهٔ P2 | dry-run ممیزی شده با batch 100 |
| Dataset stage cleanup | فایل های موقت upload منقضی | فقط count؛ اجرای واقعی جدا و batch-limited |
| Alert expiry | Alertهای منقضی فاقد expiry record | فقط count؛ materialization غیرمخرب و جدا |
| Candidate Projection | زمان آخرین Journal و Projection | تشخیص lag و پیشنهاد rebuild از Journal |

Dataset، Experiment، Walk-Forward، Decision evidence، Candidate Journal، Alert و Position حذف نمی شوند.
Candidate Projection یک read model قابل بازسازی است و Alert expiry نیز evidence جدید append-only می سازد.

## Policy عملیاتی

نسخه policy برابر `release-maintenance-policy-v1` و checksum فریز شدهٔ آن برابر است با:

```text
37b921b7dc27e7a0cd95f66d4b5276679a5e8a07adae6b07ea0cc810119a4ade
```

| عملیات | سقف هر batch |
| --- | ---: |
| Market Data retention | 100 |
| Dataset stage cleanup | 100 |
| Alert expiry materialization | 100 |

Policy به صورت صریح `automatic_execution_allowed=false` و
`immutable_evidence_deletion_allowed=false` دارد. وجود legal/incident hold، action مربوط به Market
Data retention را `blocked` می کند. Alert expiry چون حذف انجام نمی دهد می تواند مستقل باقی بماند.

## تولید plan مرجع

Database باید PostgreSQL و دقیقاً در migration head باشد. output موجود overwrite نمی شود:

```bash
export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://trd_p6:trd_p6_password@localhost:55441/trd_bot_test'

PYTHONPATH=src python scripts/plan_v0_3_maintenance.py \
  --database-url "$TRD_BOT_TEST_DATABASE_URL" \
  --environment-label macbook-pro-reference \
  --requested-by operator:amir \
  --output /tmp/trd-bot-p6-04-maintenance-plan.json
```

Artifact شامل commit SHA، زمان UTC، policy checksum، report checksum، retention dry-run، snapshot
تجمیعی و actionهای مشتق شده است. تغییر action، count یا checksum هنگام parse رد می شود.

## اجرای کنترل شدهٔ Actionها

ابتدا artifact را بازبینی کنید. فقط actionهایی را که `required` هستند جداگانه اجرا کنید.

### Market Data retention

```bash
PYTHONPATH=src python scripts/manage_market_data_retention.py execute \
  --requested-by operator:amir \
  --batch-limit 100 \
  --confirm-policy-version market-data-service-level-policy-v1
```

حالت `blocked` باید با بررسی hold و بدون دور زدن آن حل شود. اگر backlog بیشتر از یک batch بود، پس از
هر batch دوباره plan بگیرید.

### Dataset stage cleanup

```bash
PYTHONPATH=src python -m trd_bot.maintenance cleanup-expired-dataset-stages \
  --requested-by operator:amir \
  --batch-limit 100 \
  --confirm-policy-version release-maintenance-policy-v1
```

cleanup فقط content موقت منقضی را با ترتیب ثابت `expires_at, stage_id` حذف می کند. limit خارج از
بازهٔ 1 تا 500 رد می شود و فایل stage فعال حذف نمی شود.

### Alert expiry materialization

```bash
PYTHONPATH=src python scripts/manage_alert_expiry.py execute \
  --requested-by operator:amir \
  --batch-limit 100
```

این action Alert را حذف یا بازنویسی نمی کند و فقط expiry evidence یکتا و append-only می سازد.

### Candidate Projection rebuild

```bash
PYTHONPATH=src python -m trd_bot.maintenance rebuild-candidate-projections
```

Journal منبع حقیقت immutable باقی می ماند و Projection از روی آن بازسازی می شود. وضعیت `review`
برای Projection بدون Journal باید قبل از rebuild دستی بررسی شود.

## چرخهٔ پایان عملیات

پس از اجرای batchهای تأییدشده، plan را با output جدید تکرار کنید. هدف این است که actionهای لازم به
`not_required` برسند؛ هر `blocked` یا `review` باید با evidence و تصمیم انسانی بسته شود. artifactهای
قبل و بعد همراه SHA و خروجی CI نگهداری شوند.

## مرز ایمنی

- plan هیچ maintenance واقعی را خودکار اجرا نمی کند؛
- dry-run Market Data تنها write خود plan و یک audit sanitizeشده است؛
- هیچ secret، DSN، payload فایل یا محتوای Journal در artifact نوشته نمی شود؛
- هیچ API خصوصی صرافی، account، wallet یا live order اضافه نشده است؛
- هیچ migration، endpoint یا UI جدیدی در این مرحله وجود ندارد.

## گیت های کد

```bash
python -m pytest \
  tests/test_release_maintenance.py \
  tests/test_maintenance.py \
  tests/test_dataset_file_stage_repository.py \
  tests/test_dataset_file_jobs.py \
  -q

python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
python -m pytest -m integration -q
```

## معیار خروج P6-04

- [x] تمام scopeهای نگهداری نسخه در یک plan commit-bound دیده می شوند.
- [x] plan در برابر action/checksum دست کاری شده fail-closed است.
- [x] Market Data dry-run ممیزی شده و purge واقعی جدا و نیازمند تأیید است.
- [x] cleanup فایل stage محدود، deterministic و دارای تأیید policy است.
- [x] Alert و Journal immutable باقی می مانند و Projection فقط از Journal rebuild می شود.
- [x] اجرای خودکار maintenance و حذف evidence immutable ممنوع است.
- [ ] plan و actionهای مرجع روی PostgreSQL و SHA نهایی ثبت شوند.
- [ ] تست integration و GitHub Actions روی همان SHA سبز شوند.

پس از بستن این گیت، مرحله مجاز بعدی `P6-05 - Documentation and Migration Guide` است.
