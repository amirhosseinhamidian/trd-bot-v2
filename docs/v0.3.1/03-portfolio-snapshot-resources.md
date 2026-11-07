# TRD-V031-03 — Portfolio Snapshot Resources

وضعیت: **Candidate**
تاریخ تصمیم: ۲۰۲۶-۱۱-۰۷
پیش‌نیاز فریز‌شده: commit `b4d5fb62dabffd8e74257d5b3e10148a191395a3`

## هدف

این مرحله اولین resourceهای واقعی اتصال Nexora را روی snapshot protocol فریز‌شده منتشر
می‌کند. endpoint واحد و احراز هویت‌شده فقط داده‌های شبیه‌سازی‌شده Paper/Shadow را با paging
پایدار، cursor opaque و source reference دارای SHA-256 برمی‌گرداند.

## Endpoint و resourceها

```text
GET /api/v1/integration/nexora/snapshots/{resource_type}
```

allowlist این مرحله دقیقاً شامل موارد زیر است:

- `paper_shadow_portfolio`
- `paper_shadow_position`
- `portfolio_intelligence`
- `simulation_outcome`

هر payload دارای schema version مستقل، `offline_only=true` و
`external_order_submission_allowed=false` است. اعداد مالی به‌صورت decimal string منتقل می‌شوند
تا round-trip قطعی بماند. `simulation_outcome` فقط رویدادهای بسته‌شدن position یا تکمیل portfolio
را منتشر می‌کند.

## رفتار fail-closed

- service token، `Accept: application/json` و correlation ID معتبر الزامی‌اند؛
- resource خارج از allowlist و cursor ناشناخته با `400` رد می‌شوند؛
- cursor متعلق به resource یا limit دیگر با `409` رد می‌شود؛
- cursor منقضی `410` می‌دهد و full snapshot resync لازم است؛
- پاسخ موفق `private, no-store` است؛
- token، credential و مجوز ارسال سفارش در payload یا cursor وجود ندارد.

## مرز مرحله

- Decision snapshotها به `TRD-V031-04` موکول می‌شوند؛
- Alert snapshotها به `TRD-V031-05` موکول می‌شوند؛
- event feed، command و export هنوز اضافه نشده‌اند؛
- migration تازه‌ای وجود ندارد و head همان `20261106_0037` است؛
- نسخه provider همچنان `0.3.0` و برای Nexora ناسازگار است؛
- `NEX-P3-03`، production readiness و live execution بسته می‌مانند.

## معیار پذیرش

```bash
python3 scripts/verify_v0_3_1_portfolio_snapshot_resources.py
python3 -m unittest tests/test_v0_3_1_portfolio_snapshot_resources.py -v
python3 -m pytest \
  tests/test_nexora_portfolio_snapshots.py \
  tests/test_nexora_integration_capabilities.py \
  tests/test_nexora_snapshot_protocol.py \
  tests/test_nexora_snapshot_persistence.py \
  -v
python3 -m ruff format --check .
python3 -m ruff check .
python3 -m mypy
python3 -m pytest -m "not integration"
git diff --check
```

```text
TRD_V031_03_PORTFOLIO_RESOURCE_ALLOWLIST=PASS
TRD_V031_03_STABLE_PAGING=PASS
TRD_V031_03_SOURCE_REFERENCE_CHECKSUM=PASS
TRD_V031_03_AUTHENTICATED_ENDPOINT=PASS
TRD_V031_03_DATABASE_MIGRATION=NONE
TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE
NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE
TRD_BOT_LIVE_EXECUTION=DISABLED
NEXT_ALLOWED_STAGE=TRD-V031-03-FREEZE
```

پس از CI موفق روی همان candidate SHA، فقط `TRD-V031-03-FREEZE` مجاز است.
