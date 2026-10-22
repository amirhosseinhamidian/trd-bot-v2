# P4-03 — اجرای پایدار ارزیابی هشدارها

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P4-04**

تاریخ تصمیم: `2026-10-17`

مبنای کد: P4-02 در commit
`c3b223081dc8373555d0ad7308066f00302e1636`

این مرحله قراردادها و persistence دو مرحلهٔ قبل را به صف durable متصل می‌کند. هر assessment موفق
Market Context برای آخرین نسخهٔ فعال Ruleها job ارزیابی می‌سازد و worker نتیجهٔ publish یا suppress
را به‌صورت deterministic و قابل audit ثبت می‌کند. endpoint، صفحهٔ Alert Center، acknowledgement،
snooze یا کانال بیرونی در این مرحله اضافه نمی‌شود.

## 1. قرارداد job

`AlertEvaluationJobPayload` با schema نسخهٔ `alert-evaluation-job-v1` این lineage دقیق را نگه می‌دارد:

- reference نسخهٔ دقیق Rule شامل ID، version و checksum؛
- reference assessment منبع شامل ID، checksum، regime، confidence و freshness؛
- `requested_at` ثابت که زمان منطقی ارزیابی و source view نیز هست.

payload با دادهٔ persisted دوباره ساخته و مقایسه می‌شود. Rule حذف‌شده، assessment ناموجود یا هر mismatch
در checksum و lineage به‌صورت fail-closed و با خطای sanitized رد می‌شود.

## 2. enqueue و fan-out

پس از commit موفق assessment، handler مربوط به Market Context آخرین نسخهٔ هر Rule را پیدا می‌کند و فقط
Ruleهای `enabled` را enqueue می‌کند. نسخهٔ غیرفعال جدید باعث نمی‌شود نسخهٔ فعال قدیمی دوباره مصرف شود.

کلید idempotency از `rule_id + rule_version + source kind + source event` ساخته می‌شود و عمداً
`requested_at` را در hash ندارد. درخواست دوباره برای همان intent به job قبلی متصل می‌شود و زمان اولین
درخواست را حفظ می‌کند.

## 3. ارزیابی deterministic

worker ترتیب زیر را اجرا می‌کند:

1. نسخهٔ دقیق Rule و assessment منبع را از دیتابیس می‌خواند؛
2. source view را در `requested_at` ثابت بازسازی و با payload تطبیق می‌دهد؛
3. حالت Rule، consumability و expiry را به‌ترتیب fail-closed بررسی می‌کند؛
4. condition نسخه‌دار Rule را روی context اجرا می‌کند؛
5. نتیجه را به‌صورت Evaluation منتشرشده یا suppression دارای reason ثبت می‌کند.

Rule غیرفعال، source غیرقابل مصرف، source منقضی یا condition نامنطبق Alert منتشر نمی‌کنند، اما outcome
آن‌ها برای audit در `alert_evaluations` باقی می‌ماند.

## 4. transaction، retry و reclaim

Evaluation و Alert متناظر در یک transaction ثبت می‌شوند. cancellation قبل و حین اجرای حساس transaction
را rollback می‌کند. policy صف برای `alert_evaluation` سه attempt با backoff عمومی worker و runtime p95
هدف ۳۰ ثانیه دارد.

اگر worker پس از commit outcome و پیش از ثبت success صف crash کند، lease منقضی reclaim می‌شود. اجرای
دوباره به همان Evaluation و Alert immutable متصل می‌شود و job همان `evaluation_id` را به‌عنوان
`result_reference` برمی‌گرداند؛ رکورد تکراری ساخته نمی‌شود.

## 5. benchmark و مرز امنیتی

workload جدید `alert_evaluation` به پوشش کامل benchmark jobها افزوده شده و مسیر pure evaluation را با
یک Rule و یک assessment synthetic اجرا می‌کند. این مرحله فقط market data عمومی و artifactهای مشتق‌شده
را می‌خواند و در Inbox داخلی می‌نویسد. هیچ credential، حساب صرافی، wallet، واریز/برداشت، سفارش واقعی یا
delivery بیرونی اضافه نشده است.

## 6. معیار خروج P4-03

- [x] payload نسخه‌دار به Rule و assessment دقیق متصل است.
- [x] enqueue برای intent یکسان idempotent و زمان اولین درخواست ثابت است.
- [x] assessment موفق به آخرین نسخهٔ فعال Ruleها fan-out می‌شود.
- [x] publish و suppression deterministic و durable هستند.
- [x] cancellation هیچ outcome ناقصی باقی نمی‌گذارد.
- [x] retry و lease reclaim Evaluation یا Alert تکراری نمی‌سازند.
- [x] allowlist، policy، handler registry و benchmark kind جدید را پوشش می‌دهند.
- [x] محدودهٔ public read-only و بدون live execution حفظ شده است.

گام بعدی `P4-04 — Alert Center API/UI و Acknowledge/Snooze` است.
