# P2-04 — Window Lifecycle and Watermark Finalization

وضعیت: **پیاده‌سازی‌شده؛ evidence نهایی PostgreSQL و CI در انتظار اجرای مالک مخزن**

تاریخ تصمیم: `2026-10-14`

مبنای کد: P2-03 در commit
`0e8fc022c95c94941ab88a2d72e49d9474bc49ae`

این مرحله lifecycle فریز‌شدهٔ Window را از قرارداد domain به مسیر ماندگار runtime متصل می‌کند.
هر Window فقط وقتی نهایی می‌شود که آخرین Watermark همان stream از انتهای آن عبور کرده باشد؛
نسخهٔ provisional تغییر نمی‌کند و یک نسخهٔ finalized تازه همراه evidence دقیق Watermark و freshness
ساخته می‌شود.

## 1. مرز قابلیت

- stream دقیق با `source + pair + timeframe` ایزوله می‌شود؛
- فقط آخرین نسخهٔ provisional هر Window کاندید finalization است؛
- شرط eligibility برابر `window_end <= watermark_time` است؛
- candle باز حتی در صورت عبور Watermark نهایی نمی‌شود؛
- finalization نسخه را دقیقاً یک واحد افزایش می‌دهد؛
- snapshot، Watermark revision و freshness evidence در یک transaction ثبت می‌شوند؛
- فراخوانی تکراری نتیجهٔ تازه نمی‌سازد و اجرای هم‌زمان به یک نسخهٔ نهایی همگرا می‌شود.

Replay/Revision دادهٔ دیررس یا correction پس از finalization در این مرحله انجام نمی‌شود و محدودهٔ
صریح P2-05 باقی می‌ماند.

## 2. Persistence جدید

جدول `market_data_window_finalizations` evidence append-only هر transition را نگه می‌دارد:

| فیلد | نقش |
| --- | --- |
| `window_id + finalized_version` | یکتایی transition نهایی |
| `provisional_version → finalized_version` | اثبات افزایش دقیق یک نسخه |
| `event_id + payload_checksum` | حفظ lineage محتوای snapshot |
| `watermark_id + watermark_version` | اتصال به revision دقیق تصمیم |
| `window_end + watermark_time` | اثبات عبور boundary |
| `freshness_seconds` | فاصلهٔ finalization تا پایان Window |
| `freshness_target_seconds` | هدف policy همان timeframe |
| `freshness_outcome` | `within_target` یا `missed_target` |

Migration جدید `20261014_0022` فقط جدول evidence و indexهای عملیاتی را اضافه می‌کند و migration
P2-03 را بازنویسی نمی‌کند.

## 3. الگوریتم finalization

`SqlAlchemyMarketDataWindowFinalizer` در یک transaction:

1. آخرین Watermark revision stream را با lock می‌خواند؛
2. سازگاری policy version و allowed lateness را fail-closed بررسی می‌کند؛
3. Window IDهای دارای آخرین نسخهٔ provisional و عبورکرده از Watermark را مرتب می‌کند؛
4. آخرین نسخهٔ هر Window را مجدداً با lock می‌خواند؛
5. Window بسته را با متد domain به نسخهٔ finalized تازه تبدیل می‌کند؛
6. freshness outcome را از policy فریز‌شده محاسبه می‌کند؛
7. snapshot و evidence را با هم commit می‌کند.

در race دو finalizer، constraint مرکب `window_id + finalized_version` و retry تراکنش مانع ایجاد
دو نسخهٔ نهایی می‌شوند. finalizer بازنده پس از reload، Window نهایی را می‌بیند و بدون mutation
خاتمه می‌یابد.

## 4. اتصال به Polling

پس از ingestion موفق batch و advance ماندگار Watermark، Poll Job همان stream را finalize می‌کند.
در نتیجه:

- Watermark تازه قبل از تصمیم finalization persist شده است؛
- فقط Windowهای provider انتخاب‌شده بررسی می‌شوند؛
- crash پس از ingestion با retry امن job تکمیل می‌شود؛
- failure finalization با کد `market_data_finalization_failed` از failure ingestion تفکیک می‌شود؛
- benchmark واقعی `market_data_poll` هم ingestion و هم حداقل یک transition نهایی را اجرا می‌کند.

Finalization موفق یا missed SLO هر دو snapshot را نهایی می‌کنند؛ missed target یک نتیجهٔ قابل
اندازه‌گیری است، نه دلیلی برای نگه‌داشتن داده در state provisional.

## 5. Invariantهای حفظ‌شده

- Watermark هیچ‌گاه توسط finalizer تغییر نمی‌کند یا عقب نمی‌رود؛
- نسخهٔ provisional overwrite نمی‌شود؛
- Window نهایی event ID، checksum و candle نسخهٔ provisional را حفظ می‌کند؛
- Window و Watermark باید دقیقاً متعلق به یک stream باشند؛
- هیچ Window آینده، باز یا نارس نهایی نمی‌شود؛
- اجرای عادی late arrival یا conflict با Window نهایی را mutate نمی‌کند؛
- دادهٔ تاریخی v0.2 و Historical Import بدون backfill ساختگی باقی می‌مانند.

## 6. گیت خروج P2-04

- [x] transition از provisional به finalized نسخهٔ immutable تازه می‌سازد.
- [x] eligibility بر اساس Watermark revision ماندگار و همان stream اعمال می‌شود.
- [x] open، future و stream دیگر نهایی نمی‌شوند.
- [x] finalization تکراری idempotent است.
- [x] race هم‌زمان PostgreSQL فقط یک نسخه و یک evidence می‌سازد.
- [x] freshness target و outcome برای هر transition ماندگار می‌شوند.
- [x] Polling پس از advance Watermark finalizer را اجرا می‌کند.
- [x] failure finalization retryable و دارای error code امن است.
- [x] migration upgrade/downgrade و metadata coverage اضافه شده است.
- [ ] full backend و PostgreSQL CI روی SHA نهایی سبز شود.

گام بعدی `P2-05 — Late Data and Correction Replay/Revision` است؛ در آن تصمیم‌های
`revision_required` با workflow صریح، audit trail و نسخهٔ اصلاحی پردازش می‌شوند، بدون mutation
پنهان snapshot نهایی.
