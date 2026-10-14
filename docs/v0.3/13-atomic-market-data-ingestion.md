# P2-02 — Ingestion اتمیک دادهٔ بازار

وضعیت: **پیاده‌سازی‌شده؛ evidence نهایی PostgreSQL و CI در انتظار اجرای مالک مخزن**

تاریخ تصمیم: `2026-10-14`

مبنای کد: P2-01 در commit
`2d84c27b654808f5e8c22c74e4f84d78dac6bd2a`

این مرحله قراردادهای P0-03 و storage مرحلهٔ P2-01 را به یک مرز تراکنشی واحد متصل می‌کند. هیچ
polling loop، scheduler، route عمومی جدید یا integration مربوط به معاملهٔ واقعی در این مرحله
اضافه نشده است.

## 1. مرز تراکنش

`SqlAlchemyMarketDataIngestor` مالک commit/rollback است و برای هر observation این واحد را یکجا
ثبت می‌کند:

1. Raw Observation تغییرناپذیر؛
2. آخرین Watermark revision همان stream به‌عنوان evidence تصمیم؛
3. Event نرمال‌شده و Inbox identity؛
4. Decision journal تغییرناپذیر؛
5. در صورت پذیرش، Window version و Outbox message.

هر خطا پس از شروع عملیات باعث rollback تمام writeهای همان ingestion می‌شود. repositoryهای P2-01
همچنان commit مستقل ندارند و فقط داخل مرز فوق stage می‌کنند.

## 2. Decision journal

جدول `market_data_event_decisions` برای هر Raw Observation دقیقاً یک تصمیم نگه می‌دارد. رکورد شامل
`observation_id`، `event_id`، `watermark_id`، نتیجهٔ classification، دلیل، نسخهٔ فعلی/پیشنهادی
Window و `requires_replay` است.

- شناسهٔ تصمیم از observation و event به‌صورت deterministic ساخته می‌شود؛
- unique index روی `observation_id` اجرای دوبارهٔ همان observation را متوقف می‌کند؛
- decision به revision دقیق Watermark متصل است تا نتیجه بعداً قابل بازسازی و audit باشد؛
- Foreign Key به Raw، Event یا Watermark عمداً اضافه نشده تا retention متفاوت P2-01 lineage را
  نشکند؛ شناسه‌ها همچنان در evidence پایدار می‌مانند.

## 3. رفتار retry، redelivery و correction

| ورودی | نتیجهٔ ماندگار | Window/Outbox |
| --- | --- | --- |
| retry دقیق همان `observation_id` | نتیجهٔ قبلی با `created=false` | بدون write تازه |
| payload یکسان با receipt time و Raw ID تازه | Raw و decision تازه؛ Inbox count افزایش می‌یابد | بدون تکرار |
| correction برای Window provisional | Event/Inbox/decision تازه | نسخهٔ بعدی Window و Outbox تازه |
| late event یا تعارض با Window finalized | Event/Inbox و decision با `revision_required` | ساخته نمی‌شود |
| نبود Watermark همان stream | fail-closed | کل transaction rollback می‌شود |

`IntegrityError` رقابتی یک بار پس از rollback تکرار می‌شود. اگر transaction رقیب همان observation
را ثبت کرده باشد، نتیجهٔ ماندگار بازیابی می‌شود؛ در غیر این صورت خطای domain
`MarketDataIngestionConflictError` برگردانده می‌شود.

## 4. قفل و race

- latest Watermark و latest Window با `SELECT ... FOR UPDATE` خوانده می‌شوند؛
- redelivery شمارندهٔ Inbox را زیر row lock افزایش می‌دهد؛
- unique constraintهای Raw، Event، Inbox، Decision، Window و Outbox آخرین خط دفاع هستند؛
- تست PostgreSQL دو session هم‌زمان را روی یک observation آزاد می‌کند و الزام می‌کند فقط یک واحد
  ماندگار ساخته شود و caller دوم همان decision را با `created=false` دریافت کند.

SQLite فقط برای تست سریع correctness استفاده می‌شود؛ evidence قفل و race باید روی PostgreSQL 17
ثبت شود.

## 5. Migration و سازگاری

- migration جدید `20261014_0020` بعد از `20261014_0019` قرار دارد؛
- migration فقط Decision journal و indexهای audit/query آن را اضافه می‌کند؛
- Dataset، Experiment، Walk-Forward و APIهای موجود بازنویسی نشده‌اند؛
- معماری PostgreSQL modular monolith حفظ شده و Kafka، Redis، TimescaleDB یا ClickHouse اضافه نشده؛
- هیچ live order، credential، wallet، deposit یا withdrawal به schema یا routeها اضافه نشده است.

## 6. گیت خروج P2-02

- [x] یک transaction مالک Raw، Event، Inbox، Decision، Window و Outbox است.
- [x] تصمیم به Watermark revision دقیق متصل و append-only است.
- [x] retry دقیق idempotent و redelivery قابل شمارش است.
- [x] correction عادی فقط Window provisional را نسخه‌بندی می‌کند.
- [x] late/finalized conflict بدون mutation عادی به replay ارجاع می‌شود.
- [x] failure میانی کل واحد را rollback می‌کند.
- [x] تست race واقعی PostgreSQL به integration suite اضافه شده است.
- [ ] full backend و PostgreSQL CI روی SHA نهایی سبز شود.

پس از سبز شدن گیت‌های این مرحله، P2-03 می‌تواند collector/provider orchestration را روی همین مرز
اتمیک سوار کند؛ بدون آنکه semantics dedupe، correction یا audit را دوباره تعریف کند.
