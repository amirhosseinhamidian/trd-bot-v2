# P6-01 - Cross-cutting Hardening و Release Inventory

وضعیت: **پیاده سازی شده؛ اجرای گیت ها روی SHA نهایی باقی است**

این مرحله نخستین گیت Phase 6 است. هدف آن افزودن قابلیت محصولی نیست؛ سطح واقعی انتشار v0.3 را از
روی کد استخراج و به یک inventory قطعی و قابل ممیزی تبدیل می کند تا تغییر ناخواسته در API، UI،
provider، worker، schema، migration یا مرز امنیتی پیش از انتشار پنهان نماند.

## یافته Hardening

تست قدیمی `tests/test_release_security_boundary.py` routeهای FastAPI را مستقیماً با
`isinstance(APIRoute)` از `app.routes` جدا می کرد. نسخه فعلی FastAPI، routerهای includeشده را به شکل
`_IncludedRouter` نگه می دارد؛ در نتیجه مجموعه routeهای بررسی شده خالی بود و بخش path امنیتی تست
به صورت ظاهری سبز می شد.

تست جدید عملیات واقعی را از `app.openapi()["paths"]` استخراج می کند. خالی بودن inventory، method
ناشناخته، segment مربوط به live execution و property مربوط به credential همگی fail-closed هستند.

## اجزای Inventory

`trd_bot.release_hardening` موارد زیر را به صورت مرتب، یکتا و checksummed ثبت می کند:

- تمام operationهای واقعی OpenAPI و propertyهای schema؛
- تمام صفحه های عمومی Frontend؛
- providerهای public، mode دسترسی و market type؛
- تمام Background Jobها، retry budget، payload version و cancellation mode؛
- تمام جدول های SQLAlchemy؛
- تمام revisionهای Alembic و head نهایی؛
- همه منابع نسخه Backend و Frontend؛
- User-Agent کلاینت های شبکه؛
- قابلیت هایی که عمداً تا بعد از v0.3 deferred هستند.

User-Agentهای provider و probe که هنوز suffix تاریخی `0.1` داشتند، اکنون مستقیماً از
`trd_bot.__version__` ساخته می شوند و با `0.3.0` همگرا هستند.

## اجرای Audit

```bash
PYTHONPATH=src python scripts/audit_v0_3_release_inventory.py \
  --output /tmp/trd-bot-v0.3-release-inventory.json
```

فایل موجود overwrite نمی شود. نتیجه موفق باید `passed=true`، `failure_reasons=[]`، یک migration
head و checksum ثابت inventory داشته باشد.

## گیت های مرحله

```bash
python -m pytest \
  tests/test_release_hardening.py \
  tests/test_release_security_boundary.py \
  tests/test_release_version.py \
  -q

python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
```

CI استاندارد repository چرخه کامل PostgreSQL 17 و گیت های Frontend را نیز روی همان SHA اجرا
می کند.

## معیار خروج P6-01

- [x] API inventory از OpenAPI واقعی و غیرخالی ساخته می شود.
- [x] مرز credential و live execution برای API، Frontend، provider و worker fail-closed است.
- [x] نسخه، schema، migration، network identity و deferred capabilityها inventory شده اند.
- [x] report قطعی، checksumدار و در برابر outcome دست کاری شده مقاوم است.
- [x] User-Agentهای شبکه با نسخه runtime همگرا هستند.
- [ ] گیت های محلی روی SHA نهایی موفق شوند.
- [ ] GitHub Actions همان SHA با سه job موفق ثبت شود.

پس از بستن این گیت، مرحله مجاز بعدی `P6-02 - Capacity، Overload و Recovery Benchmark` است.
