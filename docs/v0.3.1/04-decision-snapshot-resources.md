# TRD-V031-04 — Decision Snapshot Resources

وضعیت: **Candidate**
تاریخ تصمیم: ۲۰۲۶-۱۱-۰۷
پیش‌نیاز فریز‌شده: commit `7069a554d603d492434f8bf0f5d33ecca8798f71`

## هدف

این مرحله چهار منبع read-only زنجیرهٔ تصمیم را روی snapshot protocol فریز‌شده منتشر می‌کند.
Nexora می‌تواند Market Context، ورودی ارزیابی تصمیم، evidence رتبه‌بندی Candidate و نتیجهٔ Risk
Gate را با lineage، checksum و paging پایدار دریافت کند.

## Endpoint و resourceها

```text
GET /api/v1/integration/nexora/snapshots/{resource_type}
```

allowlist این مرحله دقیقاً شامل موارد زیر است:

- `market_context`
- `decision_evaluation`
- `candidate`
- `risk_gate`

منبع `candidate` از `DecisionCandidateRankingRow` تغییرناپذیر خوانده می‌شود. projection قابل‌تغییر
`CandidateProjectionRow` عمداً وارد snapshot نمی‌شود تا داده در میانهٔ scan تغییر نکند. تمام payloadها
دارای `offline_only=true` و `external_order_submission_allowed=false` هستند.

## رفتار fail-closed

- service token، `Accept: application/json` و correlation ID معتبر الزامی‌اند؛
- resource خارج از allowlist و cursor ناشناخته با `400` رد می‌شوند؛
- cursor متعلق به resource یا limit دیگر با `409` رد می‌شود؛
- cursor منقضی `410` می‌دهد و full snapshot resync لازم است؛
- پاسخ موفق `private, no-store` است؛
- token، credential، review command و مجوز ارسال سفارش در payload یا cursor وجود ندارد.

## مرز مرحله

- Alert snapshotها به `TRD-V031-05` موکول می‌شوند؛
- event feed، human review command و export هنوز اضافه نشده‌اند؛
- migration تازه‌ای وجود ندارد و head همان `20261106_0037` است؛
- نسخه provider همچنان `0.3.0` و برای Nexora ناسازگار است؛
- `NEX-P3-03`، production readiness و live execution بسته می‌مانند.

## معیار پذیرش

```bash
python3 scripts/verify_v0_3_1_decision_snapshot_resources.py
python3 -m unittest tests/test_v0_3_1_decision_snapshot_resources.py -v
python3 -m pytest \
  tests/test_nexora_decision_snapshots.py \
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
TRD_V031_04_DECISION_RESOURCE_ALLOWLIST=PASS
TRD_V031_04_IMMUTABLE_EVIDENCE=PASS
TRD_V031_04_STABLE_PAGING=PASS
TRD_V031_04_SOURCE_REFERENCE_CHECKSUM=PASS
TRD_V031_04_AUTHENTICATED_ENDPOINT=PASS
TRD_V031_04_DATABASE_MIGRATION=NONE
TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE
NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE
TRD_BOT_LIVE_EXECUTION=DISABLED
NEXT_ALLOWED_STAGE=TRD-V031-04-FREEZE
```

پس از CI موفق روی همان candidate SHA، فقط `TRD-V031-04-FREEZE` مجاز است.
