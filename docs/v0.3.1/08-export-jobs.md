# TRD-V031-08 — Export Jobs, Status, and Complete Manifest

این مرحله خروجی‌های نسخه‌دار `private` و `ai_safe` را به‌صورت job پایدار و idempotent فراهم
می‌کند. سه عملیات منجمدشدهٔ Nexora برای ایجاد export، مشاهدهٔ status و دریافت manifest کامل
پیاده‌سازی شده‌اند. این مرحله هیچ endpoint جدیدی برای دانلود فایل خارج از قرارداد منجمدشده
معرفی نمی‌کند؛ bytes فایل‌ها به‌صورت خصوصی در دیتابیس نگه‌داری و از طریق manifest با SHA-256
قابل ممیزی می‌شوند.

## قرارداد و چرخهٔ اجرا

- `POST /api/v1/integration/nexora/exports` با `Idempotency-Key` یک job پایدار می‌سازد؛
- تکرار دقیق همان درخواست همان `export_id` را برمی‌گرداند و استفادهٔ متفاوت از همان کلید با
  `409 IDEMPOTENCY_CONFLICT` بسته می‌شود؛
- worker فقط job allowlisted از نوع `nexora_export` را اجرا می‌کند؛
- `GET /exports/{export_id}` وضعیت `accepted|running|complete|failed` را برمی‌گرداند؛
- manifest تا زمانی که تمام artifactها، اندازه‌ها و checksumها در یک transaction ثبت نشده‌اند
  با `409 SOURCE_UNAVAILABLE` منتشر نمی‌شود؛
- manifest نهایی همیشه `completion_status=complete`، timezone برابر `UTC`، نسخهٔ منبع، scope،
  فیلترها، source lineage و فهرست فایل‌های checksum‌شده دارد.

فرمت‌های پشتیبانی‌شده `json`، `jsonl`، `csv`، `parquet` و `zip_bundle` هستند. Snapshotهای
منجمدشدهٔ مراحل ۰۳ تا ۰۵ منبع export هستند و همگی در یک boundary زمانی UTC خوانده می‌شوند.

## حریم خصوصی و امنیت

پروفایل `private` دادهٔ مجاز snapshot را با حذف قطعی هر کلید secret-like صادر می‌کند. پروفایل
`ai_safe` علاوه بر آن شناسه‌ها و referenceهای حساب/مالک/مؤسسه را به‌صورت deterministic با
`[REDACTED]` جایگزین می‌کند. credential، token، password، API key و Authorization نه در filters
پذیرفته می‌شوند و نه در artifact مجازند. Service token هرگز وارد payload، manifest یا evidence
نمی‌شود.

این مرحله همچنان فقط Research/Paper/Shadow است: اجرای زنده، سفارش پول واقعی، credential صرافی،
انتقال کیف پول یا وجه و دیتابیس مشترک با Nexora وجود ندارد. Provider هنوز نسخهٔ `0.3.0` و
ناسازگار است؛ `NEX-P3-03` تا تکمیل `TRD-V031-10` و Real Local Provider Smoke مسدود می‌ماند.

## Migration و بازیابی

Migration `20261111_0040` دو جدول `nexora_export_jobs` و `nexora_export_artifacts` را ایجاد
می‌کند. constraint چرخهٔ عمر اجازه نمی‌دهد status کامل بدون manifest یا status ناموفق بدون
error ثبت شود. retryهای worker artifactهای تلاش قبلی را پاک و مجموعهٔ کامل را دوباره در یک
transaction می‌سازند؛ بنابراین خروجی جزئی قابل انتشار نیست.

## پذیرش یکپارچه

```bash
python scripts/verify_v0_3_1_export_jobs.py
python -m unittest tests/test_v0_3_1_export_jobs.py -v
python -m pytest tests/test_nexora_exports.py -v
python -m ruff format --check .
python -m ruff check .
python -m mypy
```

Workflow مرحله، gateهای backend، PostgreSQL fresh-install/upgrade/Alembic check، frontend،
contract و security را اجرا می‌کند و فقط پس از موفقیت همهٔ آن‌ها artifact پذیرش same-SHA
می‌سازد. فقط همین evidence موفق می‌تواند `TRD-V031-09` را باز کند؛ Freeze task مستقل وجود ندارد.
