# P2-05 — Late Data and Correction Replay/Revision

وضعیت: **پیاده‌سازی‌شده؛ evidence نهایی PostgreSQL و CI در انتظار اجرای مالک مخزن**

تاریخ تصمیم: `2026-10-14`

مبنای کد: P2-04 در commit
`1f7a8cb9063b649fed59df46a74733e803e5a2d9`

این مرحله تصمیم‌های ماندگار `revision_required` را به یک workflow صریح، durable و قابل ممیزی
متصل می‌کند. ingest عادی همچنان هیچ snapshot تاریخی را تغییر نمی‌دهد؛ فقط یک درخواست replay مجاز
می‌تواند event ثبت‌شده را به نسخهٔ finalized تازه تبدیل کند.

## 1. قرارداد workflow

1. ingestion دادهٔ دیررس یا correction روی Window نهایی را همراه decision و Watermark دقیق ثبت
   می‌کند؛
2. `SqlAlchemyMarketDataReplayEnqueuer` فقط decision دارای `requires_replay=true` را می‌پذیرد؛
3. درخواست immutable و Background Job از نوع `market_data_replay` در یک transaction ثبت می‌شوند؛
4. worker درخواست، decision، event، observation lineage، Watermark و آخرین Window را دوباره
   اعتبارسنجی می‌کند؛
5. نسخهٔ finalized تازه و revision evidence در یک transaction append می‌شوند؛
6. job موفق `revision_id` را به‌عنوان `result_reference` منتشر می‌کند.

هیچ تماس دوباره‌ای با provider انجام نمی‌شود؛ replay فقط از Raw/Event/Decision ثبت‌شده استفاده
می‌کند.

## 2. دو نوع Revision

| ورودی | شرط نسخه | خروجی |
| --- | --- | --- |
| late arrival برای Window فاقد snapshot | `existing_window_version=null` | `late_insert` و نسخهٔ finalized شماره 1 |
| correction برای Window موجود | نسخهٔ فعلی دقیقاً برابر نسخهٔ ثبت‌شده در decision | `correction` و نسخهٔ finalized بعدی |

نسخهٔ قبلی overwrite یا delete نمی‌شود. correction علاوه بر نسخهٔ قبلی، event ID و checksum قبلی
را در evidence نگه می‌دارد. اگر Window بعد از decision تغییر کرده باشد، replay به‌صورت fail-closed
با `market_data_replay_rejected` متوقف می‌شود و دادهٔ جدیدتر را بازنویسی نمی‌کند.

## 3. Idempotency و race

- `replay_id` فقط از `decision_id` ساخته می‌شود؛
- idempotency key صف برابر `market-data-replay:{decision_id}` است؛
- هر decision فقط یک replay request و هر replay فقط یک revision دارد؛
- `window_id + revised_version` یکتاست؛
- retry worker پس از commit همان revision قبلی را برمی‌گرداند؛
- race برای یک replay به یک نتیجه همگرا می‌شود؛
- دو decision رقیب روی یک source version نمی‌توانند هر دو commit شوند و بازنده stale رد می‌شود.

## 4. Persistence و migration

Migration `20261014_0023` دو جدول append-only اضافه می‌کند:

- `market_data_replay_requests`: مجوز صریح، requester، decision/event/window و زمان درخواست؛
- `market_data_window_revisions`: lineage قبل/بعد، reason/kind، Watermark revision و زمان اعمال.

جدول `market_data_window_versions` همان snapshot finalized تازه را نگه می‌دارد. Watermark و تمام
نسخه‌های قبلی بدون mutation باقی می‌مانند.

## 5. مرز خطا و امنیت

- payload نامعتبر job بدون retry رد می‌شود؛
- lineage ناقص، decision غیرمجاز یا source version منقضی خطای non-retryable است؛
- failure تراکنشی با پیام sanitize شده retryable است؛
- هیچ credential، wallet، deposit، withdrawal، order یا endpoint معامله وارد workflow نشده است؛
- قابلیت فقط در مرز read-only بازار و research/shadow باقی می‌ماند.

## 6. ظرفیت و عملیات

`market_data_replay` به allowlist، policy retry سه‌مرحله‌ای و registry production اضافه شده است.
fixture واقعی capacity یک late event را ingest، enqueue و به revision finalized تبدیل می‌کند؛ هدف
runtime p95 آن 30 ثانیه است و هیچ شبکه یا secret مصرف نمی‌کند.

## 7. گیت خروج P2-05

- [x] فقط decision صریح `revision_required` قابل enqueue است.
- [x] درخواست و job به‌صورت اتمیک و idempotent ثبت می‌شوند.
- [x] late insert نسخهٔ finalized شماره 1 می‌سازد.
- [x] correction نسخهٔ finalized تازه می‌سازد و تمام نسخه‌های قبلی immutable می‌مانند.
- [x] replay به event، observation، decision و Watermark revision دقیق متصل است.
- [x] Watermark در replay تغییر نمی‌کند و عقب نمی‌رود.
- [x] retry worker نتیجهٔ تکراری ایجاد نمی‌کند.
- [x] source version منقضی fail-closed رد می‌شود.
- [x] migration، metadata، policy/handler allowlist و capacity fixture به‌روزرسانی شده‌اند.
- [ ] full backend و PostgreSQL CI روی SHA نهایی سبز شود.

گام بعدی `P2-06 — Market Data Freshness/Health API and UI` است؛ در آن وضعیت Watchlist، provider،
freshness، lag، backlog و replay/revision evidence از مسیر read-only در API و رابط کاربری نمایش
داده می‌شود.
