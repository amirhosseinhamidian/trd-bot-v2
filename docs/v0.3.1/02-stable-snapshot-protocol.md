# TRD-V031-02 — Stable Snapshot Protocol and Source References

وضعیت: **Frozen**
تاریخ تصمیم: ۲۰۲۶-۱۱-۰۶
پیش‌نیاز فریز‌شده: commit `ef45640c5bb4b1458668635404c610d776b882f7`

## هدف

این مرحله زیرساخت مشترک snapshotهای Nexora را پیش از اضافه‌شدن resourceهای واقعی
Portfolio، Decision و Alert تثبیت می‌کند. خروجی این مرحله endpoint نیمه‌کاره یا دادهٔ
ساختگی منتشر نمی‌کند؛ فقط قرارداد page و source reference، موتور paging و persistence
لازم برای boundary و cursor را می‌سازد.

## اسکن پایدار

اولین صفحه بدون cursor زمان UTC و high-watermark را ثابت می‌کند. تمام صفحه‌های ادامه
همان boundary و limit را مصرف می‌کنند. reader باید رکوردها را با sort key یکتا و کاملاً
صعودی برگرداند و برای تشخیص `has_more` یک ردیف اضافی بخواند.

cursor با پیشوند `snp_` opaque و بدون credential است. retry همان صفحه، همان cursor بعدی
را تولید می‌کند. تغییر resource یا limit رد می‌شود؛ cursor منقضی باید به `410` و full
snapshot resync تبدیل شود و reset خاموش ممنوع است.

## Source reference و Persistence

هر item یک `nexora-source-reference-v1` دارد. SHA-256 روی identity، schema version،
`observed_at` UTC و payload قطعی محاسبه می‌شود. migration `20261106_0037` جدول‌های
`nexora_snapshot_scans` و `nexora_snapshot_cursors` را اضافه می‌کند؛ هیچ secret یا
service token در آنها ذخیره نمی‌شود.

## مرز مرحله

- endpoint عمومی و resource adapterها به `TRD-V031-03` تا `05` موکول شده‌اند؛
- event feed، command و export هنوز اضافه نشده‌اند؛
- نسخه provider همچنان `0.3.0` و ناسازگار است؛
- `NEX-P3-03`، live execution و production readiness بسته می‌مانند.

## معیار پذیرش

```bash
python scripts/verify_v0_3_1_snapshot_protocol.py
python -m unittest tests/test_v0_3_1_snapshot_protocol.py -v
python -m pytest tests/test_nexora_snapshot_protocol.py tests/test_nexora_snapshot_persistence.py -v
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
python -m alembic upgrade head
python -m alembic check
git diff --check
```

```text
TRD_V031_02_STABLE_SCAN_BOUNDARY=PASS
TRD_V031_02_OPAQUE_CURSOR=PASS
TRD_V031_02_DETERMINISTIC_PAGING=PASS
TRD_V031_02_SOURCE_REFERENCE_CHECKSUM=PASS
TRD_V031_02_DATABASE_MIGRATION=20261106_0037
TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE
NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE
TRD_BOT_LIVE_EXECUTION=DISABLED
NEXT_ALLOWED_STAGE=TRD-V031-02-FREEZE
```

## شواهد Freeze

candidate با SHA `8666b879600c06f376602c1f672ea570bf87f7ab` و tree
`7cc5e8386f599badbdc9b0746d42d73e918ffdba` روی هر چهار workflow موردنیاز موفق شد:
roadmap، service auth/capabilities، snapshot protocol و CI کامل شامل backend، frontend و
PostgreSQL migrations/integration tests. شناسه‌های دقیق run/job و checksum فایل‌های پذیرفته‌شده
در
[`trd-v031-02-snapshot-protocol-freeze.json`](../../artifacts/v0.3.1/trd-v031-02-snapshot-protocol-freeze.json)
ثبت شده‌اند.

```text
TRD_V031_02_FREEZE=PASS
NEXT_ALLOWED_STAGE=TRD-V031-03
```

این Freeze فقط `TRD-V031-03` (Portfolio snapshot resources) را باز می‌کند. Decision و Alert
resourceها، `NEX-P3-03`، ادعای compatibility و live execution همچنان بسته‌اند.
