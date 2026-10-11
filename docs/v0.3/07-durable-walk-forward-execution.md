# P1-03 — Durable Walk-Forward Execution

وضعیت: **تکمیل‌شده در کد؛ آمادهٔ CI روی PostgreSQL مرجع**

تاریخ تصمیم: `2026-10-10`

این مرحله مسیر Walk-Forward را از `FastAPI BackgroundTasks` خارج می‌کند. ثبت execution و job صف
اکنون اتمیک است و اجرای foldها فقط در worker allowlisted انجام می‌شود.

## قرارداد submission

1. Dataset، Strategy، windowها و تعداد foldها پیش از enqueue اعتبارسنجی می‌شوند.
2. `WalkForwardExecution` و `BackgroundJob` در یک transaction ثبت می‌شوند.
3. payload صف فقط `execution_id` معتبر و نسخه‌پذیر را حمل می‌کند.
4. idempotency key از Dataset، Strategy، پارامترهای اجرا، تنظیمات Walk-Forward و تعداد foldها ساخته
   می‌شود.
5. intent تکراری همان execution و job را با `created=false` برمی‌گرداند.

پاسخ `202 Accepted` همهٔ فیلدهای قبلی execution را در سطح اول نگه می‌دارد و دو فیلد `job` و
`created` را اضافه می‌کند؛ بنابراین polling موجود بدون تغییر رفتاری ادامه دارد.

## checkpoint و recovery در سطح fold

پس از اتمام هر fold، نتیجهٔ کامل همان fold همراه lifecycle execution در `payload_json` ذخیره
می‌شود. checkpointها در پاسخ عمومی API نمایش داده نمی‌شوند. اگر lease منقضی شود یا worker با خطای
موقت متوقف شود، attempt بعدی execution با وضعیت `running` را بارگذاری می‌کند، checkpointها را با
plan فعلی تطبیق می‌دهد و از اولین fold ناقص ادامه می‌دهد.

این قرارداد مانع عقب‌رفتن progress می‌شود و پس از reclaim شدن lease، درصد job نیز با مقدار قبلی
به‌صورت monotonic نگه داشته می‌شود. نتیجهٔ نهایی Walk-Forward deterministic و ثبت run idempotent
است.

| وضعیت | نتیجهٔ domain | نتیجهٔ job |
| --- | --- | --- |
| موفق | `succeeded` با `walk_forward_run_id` | `succeeded` با `result_reference=execution_id` |
| Dataset حذف‌شده | `failed / dataset_not_found` | failure دائمی |
| plan یا محاسبهٔ نامعتبر | `failed / execution_failed` | failure دائمی |
| cancellation | `failed / walk_forward_cancelled` | terminal طبق flag صف |
| خطای موقت runtime | `running` با checkpointهای ثبت‌شده | retry تا سقف 3 attempt |
| پایان retry budget | `failed / walk_forward_attempts_exhausted` | failure دائمی |

## Storage و migration

schema تازه‌ای لازم نیست. checkpointها در `payload_json` جدول موجود `walk_forward_executions`
ذخیره می‌شوند و ستون‌های indexشدهٔ lifecycle بدون تغییر باقی می‌مانند. repository اکنون `stage()`
دارد تا enqueuer مالک transaction مشترک execution و job باشد.

## معیار خروج P1-03

- [x] `BackgroundTasks` از route ساخت Walk-Forward حذف شد.
- [x] execution و job اتمیک و idempotent ثبت می‌شوند.
- [x] payload صف strict و allowlisted است.
- [x] progress و lease در پایان هر fold تمدید می‌شوند.
- [x] execution در وضعیت `running` از اولین fold ناقص ادامه می‌یابد.
- [x] cancellation و پایان retry budget وضعیت دامنه را terminal می‌کنند.
- [x] پاسخ API سازگار مانده و job identity را expose می‌کند.
- [x] قرارداد TypeScript و polling frontend به‌روزرسانی شده‌اند.
- [x] تست‌های rollback، idempotency، recovery، payload نامعتبر و worker end-to-end وجود دارند.
- [ ] CI مالک مخزن تست PostgreSQL را روی commit نهایی سبز کند.

پس از پذیرش CI، مرحلهٔ بعد `P1-04` است: محدودکردن و حذف مسیرهای synchronous legacy برای عملیات
سنگین Research.
