# TRD-V031-05 — Alert Snapshot Resources

وضعیت: **Acceptance candidate**
تاریخ تصمیم: ۲۰۲۶-۱۱-۰۷
پیش‌نیاز: Freeze تاریخی `TRD-V031-04` در commit
`250d84ebd93b9999230ac316b1cb919e66be7bc5`

## هدف

این مرحله منابع read-only و immutable مربوط به انتشار Alert و نتیجهٔ ارزیابی آفلاین آن را روی
snapshot protocol موجود منتشر می‌کند. این مرحله نخستین stage با مدل یکپارچهٔ
Implementation + Acceptance است و Freeze task مستقل ندارد.

## Endpoint و resourceها

```text
GET /api/v1/integration/nexora/snapshots/{resource_type}
```

allowlist افزوده‌شده دقیقاً `alert` و `alert_outcome` است. `alert` فقط publication و lineage
تغییرناپذیر را از جدول `alerts` می‌خواند؛ acknowledgement، snooze و سایر stateهای mutable اینباکس
صادر نمی‌شوند. `alert_outcome` فقط evidence نتیجهٔ Paper/Shadow را با checksum و مقادیر decimal
به‌شکل string منتشر می‌کند.

تمام payloadها `offline_only=true` و `external_order_submission_allowed=false` دارند. service
token، credential، review command، wallet action یا مسیر ارسال سفارش در payload و cursor وجود
ندارد.

## Persistence و مرز مرحله

- جدول و migration جدیدی اضافه نشده و head همان `20261106_0037` است؛
- scan boundary، stable paging، cursor persistence و source checksum از protocol موجود استفاده می‌شود؛
- event feed، review commands و export به مراحل بعد موکول هستند؛
- provider روی `0.3.0` و ناسازگار باقی می‌ماند؛
- `NEX-P3-03` تا پایان `TRD-V031-10` و Real Local Provider Smoke بسته است؛
- live trading، external order و fund transfer ممنوع باقی می‌مانند.

## پذیرش خودکار

```bash
python3 scripts/verify_v0_3_1_alert_snapshot_resources.py
python3 -m unittest tests/test_v0_3_1_alert_snapshot_resources.py -v
python3 -m pytest \
  tests/test_nexora_alert_snapshots.py \
  tests/test_nexora_decision_snapshots.py \
  tests/test_nexora_snapshot_protocol.py \
  tests/test_nexora_snapshot_persistence.py -v
python3 -m ruff format --check .
python3 -m ruff check .
python3 -m mypy
python3 -m pytest -m "not integration"
git diff --check
```

workflow `v0-3-1-alert-snapshots.yml` workflow پذیرش reusable را برای همان commit اجرا می‌کند.
تنها artifact دارای `overall_result=accepted` و commit SHA یکسان، `TRD-V031-06` را باز می‌کند؛
failed، cancelled، skipped یا evidence ناقص اجازهٔ transition نمی‌دهد.

```text
TRD_V031_05_ALERT_RESOURCE_ALLOWLIST=PASS
TRD_V031_05_IMMUTABLE_ALERT_EVIDENCE=PASS
TRD_V031_05_STABLE_PAGING=PASS
TRD_V031_05_SOURCE_REFERENCE_CHECKSUM=PASS
TRD_V031_05_AUTHENTICATED_ENDPOINT=PASS
TRD_V031_05_DATABASE_MIGRATION=NONE
TRD_V031_05_ACCEPTANCE_CANDIDATE=PASS
TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE
NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE
TRD_BOT_LIVE_EXECUTION=DISABLED
NEXT_ALLOWED_STAGE=TRD-V031-06_AFTER_CI_ACCEPTANCE
```
