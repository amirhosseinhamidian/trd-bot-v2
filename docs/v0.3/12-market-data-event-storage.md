# P2-01 — ذخیره‌سازی Event، Window و Watermark بازار

وضعیت: **پیاده‌سازی‌شده؛ evidence نهایی PostgreSQL و CI در انتظار اجرای مالک مخزن**

تاریخ تصمیم: `2026-10-14`

مبنای کد: Phase 1 freeze در commit
`0f2209dad74d86829b08b59553c86898ca3331b4`

این مرحله قراردادهای pure فریز‌شده در P0-03 را به schema ماندگار تبدیل می‌کند، اما polling،
orchestration اتمیک ingestion، window processing و retention purge را اجرا نمی‌کند. این رفتارها
به‌ترتیب در P2-02 تا P2-07 اضافه می‌شوند.

## 1. تصمیم معماری

- datastore همان PostgreSQL 17 و معماری همان modular monolith باقی می‌ماند؛
- Kafka، Redis، TimescaleDB، ClickHouse و microservice اضافه نمی‌شوند؛
- payloadهای نسخه‌دار به‌شکل canonical JSON در کنار ستون‌های queryable نگه‌داری می‌شوند؛
- Raw Observation، Event، Window version و Watermark revision append-only هستند؛
- Inbox برای deduplication طولانی‌مدت و Outbox برای handoff تراکنشی مرحلهٔ بعد آماده شده‌اند؛
- Stage methodهای repository commit نمی‌کنند تا P2-02 بتواند همهٔ writeها را در یک transaction
  انجام دهد.

## 2. جدول‌های اضافه‌شده

| جدول | نقش | هویت و invariant اصلی |
| --- | --- | --- |
| `market_data_raw_observations` | payload عمومی provider پیش از normalization | `observation_id` deterministic، checksum 64 کاراکتری و window معتبر |
| `market_data_events` | envelope نرمال‌شدهٔ `market-data-event-v1` | `event_id` و `idempotency_key` یکتا، lineage به شناسهٔ raw observation |
| `market_data_event_inbox` | tombstone مربوط به dedupe/redelivery | `idempotency_key` کلید اصلی، `event_id` یکتا و delivery count مثبت |
| `market_data_outbox` | handoff ماندگار Event پذیرفته‌شده | هویت یکتای event/topic/version و lifecycle صریح pending/delivered/failed |
| `market_data_window_versions` | نسخه‌های immutable پنجره | کلید مرکب `window_id + version` و state سازگار با `finalized_at` |
| `market_data_watermarks` | تاریخچهٔ versioned watermark هر stream | stream/version یکتا، policy version و watermark غیرجلوتر از high-water |

## 3. رابطهٔ Retention و Foreign Key

Retention فریز‌شده اجازه می‌دهد raw observation پس از 30 روز حذف شود، درحالی‌که normalized Event
تا 90 روز، Inbox تا 180 روز و finalized window بدون حذف خودکار باقی می‌مانند. بنابراین:

- `raw_observation_id` در Event یک lineage identifier است و عمداً Foreign Key ندارد؛
- `event_id` در Window نیز identifier است و عمداً Foreign Key ندارد؛
- Inbox به Event وابستگی FK ندارد تا tombstone پس از حذف Event باقی بماند؛
- Outbox به Event وابسته است، چون retention آن کوتاه‌تر از Event است و باید پیش از Event پاک شود.

این تصمیم حذف زودهنگام دادهٔ طولانی‌عمر را با cascade یا constraint ناخواسته ناممکن می‌کند، بدون
آنکه lineage قابل audit از بین برود.

## 4. قرارداد Repository

`SqlAlchemyMarketDataEventStore` این عملیات را بدون commit فراهم می‌کند:

- stage/read برای Raw Observation؛
- stage/read و lookup بر اساس idempotency key برای Event؛
- stage/read برای Inbox receipt و Outbox message؛
- append/read و latest lookup برای Window version؛
- append/read و latest-by-stream lookup برای Watermark revision.

ثبت دوبارهٔ همان شناسه و همان محتوا idempotent است و `created=false` برمی‌گرداند. همان شناسه با
محتوای متفاوت fail-closed است. race نهایی همچنان توسط unique constraintهای PostgreSQL متوقف
می‌شود؛ تبدیل IntegrityError رقابتی به نتیجهٔ domain در P2-02 و داخل transaction ingestion انجام
خواهد شد.

## 5. Migration و سازگاری

- migration جدید `20261014_0019` بعد از `20261010_0018` قرار دارد؛
- migration فقط جدول و index تازه می‌سازد و هیچ Dataset یا Snapshot موجود را بازنویسی نمی‌کند؛
- downgrade فقط شش جدول P2-01 را با ترتیب وابستگی معکوس حذف می‌کند؛
- قراردادهای `OHLCVCandle`، Dataset، Experiment، Walk-Forward و routeهای `/api/v1` تغییر نکرده‌اند؛
- هیچ route یا field مربوط به live order، exchange account، wallet یا credential اضافه نشده است.

## 6. گیت خروج P2-01

- [x] مدل‌های versioned و fail-closed برای Raw، Inbox، Outbox و Watermark تعریف شدند.
- [x] شش جدول و indexهای stream/time/status در SQLAlchemy metadata ثبت شدند.
- [x] migration از head فریز P1 و downgrade متناظر ساخته شد.
- [x] repository بدون commit برای transaction اتمیک P2-02 آماده شد.
- [x] round-trip و idempotency روی SQLite پوشش داده شد.
- [x] تست round-trip واقعی PostgreSQL به integration suite اضافه شد.
- [x] metadata، migration drift و downgrade در تست‌های موجود پوشش داده شدند.
- [ ] full backend و PostgreSQL CI روی SHA نهایی سبز شود.

پس از سبز شدن گیت‌های این مرحله، گام بعدی `P2-02 — Atomic Market Data Ingestion` است؛ در آن
Raw Observation، Event، Inbox، تصمیم ingestion، Window و Outbox در یک transaction هماهنگ ثبت
می‌شوند.
