# P3-07 — Market Context Monitoring and Freshness

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P3-08**

تاریخ تصمیم: `2026-10-16`

مبنای کد: P3-06 در commit محلی `8ba03a0`

این مرحله یک read-model عملیاتی فقط‌خواندنی برای assessmentهای market context و jobهای durable آن‌ها
اضافه می‌کند. هدف تشخیص سریع نبود داده، عقب‌ماندگی boundary، انقضای assessment، retry و failure است؛
نه ارائهٔ API محصولی برای مصرف regime در تصمیم معاملاتی. آن مرز در P3-08 باقی می‌ماند.

## 1. واحد پایش و کشف stream

هر stream با کلید قطعی `source + pair + market_type` شناخته می‌شود. reader کلیدها را از اجتماع دو
منبع durable می‌سازد:

- آخرین `MarketRegimeAssessment` هر stream؛
- آخرین job معتبر `market_context_evaluation` هر stream.

خواندن bounded است: حداکثر 1000 assessment و 1000 job بررسی و حداکثر 200 stream با ترتیب قطعی
برگردانده می‌شود. payload نامعتبر job از projection حذف می‌شود و endpoint هیچ repair یا mutation
انجام نمی‌دهد.

## 2. قرارداد freshness

`expected_as_of` برابر floor زمان تولید گزارش روی boundary ساعتی UTC است. یک stream فقط وقتی `fresh`
است که هر سه شرط زیر برقرار باشند:

1. آخرین assessment وضعیت `ready` داشته باشد؛
2. `assessment.as_of` دقیقاً با `expected_as_of` برابر باشد؛
3. `assessment.expires_at` بعد از زمان تولید گزارش باشد.

نبود assessment به `no_data` و هر assessment موجود که شروط بالا را نداشته باشد به `stale` تبدیل
می‌شود. دو عدد قابل پایش نیز بدون مقدار منفی منتشر می‌شوند:

- `assessment_age_seconds = max(0, generated_at - assessed_at)`؛
- `boundary_lag_seconds = max(0, expected_as_of - assessment.as_of)`.

## 3. reason codeهای پایدار

هر stream مجموعه‌ای مرتب و بدون تکرار از signalهای زیر دارد:

| Code | معنی عملیاتی |
| --- | --- |
| `assessment_missing` | هنوز assessment durable وجود ندارد |
| `assessment_expired` | TTL assessment گذشته است |
| `assessment_not_ready` | آخرین assessment قابل مصرف نیست |
| `boundary_lagging` | assessment با boundary فعلی هم‌تراز نیست |
| `evaluation_pending` | اولین attempt در صف یا در حال اجرا است |
| `evaluation_retrying` | job فعال حداقل یک attempt ناموفق داشته است |
| `evaluation_failed` | آخرین job stream به failure نهایی رسیده است |

خطای retry و freshness stale سلامت stream را `degraded` می‌کند. نبود assessment بدون failure یا retry
به‌صورت `no_data` گزارش می‌شود. assessment تازه و قابل مصرف `healthy` است؛ job pending جدید می‌تواند
هم‌زمان signal عملیاتی داشته باشد ولی assessment موجود را نامعتبر نمی‌کند.

## 4. backlog و وضعیت کلی

خلاصه backlog شامل تعداد کل jobهای queued و running، jobهای retrying و تعداد streamهای failed،
expired، lagging و missing است. شمارش queued/running از کل صف durable انجام می‌شود؛ failure بر اساس
آخرین job هر stream محاسبه می‌شود تا failure تاریخی رفع‌شده هشدار دائمی نسازد.

وضعیت کلی با این اولویت ساخته می‌شود:

- بدون stream: `no_data`؛
- queue در حد overload یا degraded بودن همه streamها: `critical`؛
- فقط streamهای بدون assessment و بدون failure نهایی: `no_data`؛
- وجود stale، degraded، missing یا job فعال: `warning`؛
- در غیر این صورت: `healthy`.

حد overload از همان `market-data-service-level-policy-v1` و budget مرکزی صف خوانده می‌شود.

## 5. API و UI

endpoint جدید `GET /api/v1/monitoring/market-context` قرارداد
`market-context-monitoring-v1` را برمی‌گرداند. `POST` روی آن مجاز نیست.

صفحه Monitoring گزارش را هم‌زمان با summaryهای موجود دریافت می‌کند و یک پنل responsive دارد:

- summary کارت‌محور برای stream، freshness، job فعال و retry/failure؛
- کارت مستقل برای هر source/pair؛
- badgeهای health، freshness، job status و reason code؛
- نمایش boundary مورد انتظار و ثبت‌شده، age/lag، TTL و نسخه‌های feature/algorithm؛
- شکستن امن identifierهای طولانی و layout تک‌ستونه در موبایل.

پنل هیچ دکمهٔ retry، evaluate، order یا trade ندارد. عملیات recovery همچنان خارج از این read-model و
تحت مسیرهای صریح اپراتوری انجام می‌شود.

## 6. مرز امنیتی

projection فقط شناسه‌های عمومی artifact/job، source/pair، زمان‌ها، نسخه‌ها، وضعیت‌ها و error code امن
را منتشر می‌کند. موارد زیر عمداً خارج از response هستند:

- payload job و idempotency key؛
- worker ID، lease owner و error message خام؛
- feature valueها و شواهد خام window؛
- credential، account، wallet، deposit، withdrawal و live order.

## 7. معیار خروج P3-07

- [x] freshness بر اساس boundary ساعتی و TTL به‌صورت قطعی محاسبه می‌شود.
- [x] assessmentهای missing، expired، non-ready و lagging reason code پایدار دارند.
- [x] lifecycle jobهای pending، retrying و failed بدون payload یا worker قابل مشاهده است.
- [x] backlog و overall status از state durable ساخته می‌شوند.
- [x] queryها bounded و endpoint فقط‌خواندنی است.
- [x] پنل دو‌زبانه و responsive به Monitoring اضافه شده است.
- [x] قرارداد frontend و backend برای endpoint جدید ثبت شده است.
- [x] تست‌های reader، API، sanitation، client و render وضعیت‌ها را پوشش می‌دهند.
- [x] محدودهٔ `crypto-spot-public-read-only` حفظ شده است.

گام بعدی `P3-08 — Market Context Product API and UI` است.
