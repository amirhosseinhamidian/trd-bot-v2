# P1-02 — Durable Experiment Execution

وضعیت: **تکمیل‌شده در کد؛ آمادهٔ CI روی PostgreSQL مرجع**

تاریخ تصمیم: `2026-10-10`

این مرحله بدهی `V3-D02` را می‌بندد. `POST /api/v1/research/experiment-executions` دیگر اجرای
Experiment را با `FastAPI BackgroundTasks` آغاز نمی‌کند. ثبت lifecycle دامنه و job صف در یک
transaction انجام می‌شود و فقط worker مستقل اجازهٔ شروع محاسبه را دارد.

## قرارداد enqueue

1. Dataset و پارامترهای Strategy داخل request اعتبارسنجی می‌شوند.
2. یک `ExperimentExecution` در وضعیت `queued` ساخته می‌شود.
3. payload صف فقط `execution_id` نسخه‌دار و allowlisted را حمل می‌کند.
4. idempotency key از Dataset، Strategy identity و تمام پارامترهای execution ساخته می‌شود.
5. `ExperimentExecution` و `BackgroundJob` در یک transaction ثبت می‌شوند؛ شکست هر بخش کل
   submission را rollback می‌کند.
6. تکرار intent یکسان، execution و job قبلی را با `created=false` برمی‌گرداند.

پاسخ همچنان `202 Accepted` است. همهٔ فیلدهای قبلی `ExperimentExecution` در سطح اول باقی مانده‌اند
تا clientهای v0.2 نشکنند و دو فیلد زیر اضافه شده‌اند:

- `job`: خلاصهٔ job durable برای Monitoring؛
- `created`: تمایز submission جدید از retry idempotent.

## اجرای worker و recovery

handler تولیدی برای هر اجرا lease پنج‌دقیقه‌ای می‌گیرد و progress صف را با lifecycle دامنه هماهنگ
می‌کند. payload پیش از dispatch با مدل strict بررسی می‌شود. runner اکنون علاوه بر `queued` می‌تواند
execution باقی‌مانده در وضعیت `running` را بعد از reclaim شدن lease ادامه دهد.

محاسبهٔ Experiment و شناسهٔ آن deterministic است. بنابراین اگر worker پس از ذخیرهٔ نتیجه و پیش از
ثبت موفقیت job متوقف شود، retry همان Experiment را resolve می‌کند و Candidate handoff نیز با
شناسه‌های deterministic دوباره اجرا می‌شود؛ دادهٔ تکراری ساخته نمی‌شود.

رفتار terminal:

| وضعیت | نتیجهٔ domain | نتیجهٔ job |
| --- | --- | --- |
| موفق | `succeeded` با `experiment_id` | `succeeded` با `result_reference=execution_id` |
| Dataset حذف‌شده | `failed / dataset_not_found` | failure دائمی |
| خطای محاسباتی کنترل‌شده | `failed / execution_failed` | failure دائمی |
| cancellation حین اجرا | `failed / experiment_cancelled` | job لغوشده/ناموفق طبق flag صف |
| خطای موقت runtime | وضعیت قابل بازیابی | retry تا سقف 3 attempt |
| پایان retry budget | `failed / experiment_attempts_exhausted` در صورت non-terminal بودن | failure دائمی |
| پایان retry در Candidate handoff | Experiment موفق باقی می‌ماند | `experiment_handoff_attempts_exhausted` |

## Storage و migration

schema تازه‌ای لازم نیست. P1-02 از جدول‌های موجود `experiment_executions` و `background_jobs`
استفاده می‌کند. repository اجرای Experiment اکنون primitive بدون commit با نام `stage()` دارد تا
مالک transaction، enqueuer اتمیک باشد.

## معیار خروج P1-02

- [x] `BackgroundTasks` از route ساخت Experiment حذف شد.
- [x] execution و job اتمیک و idempotent ثبت می‌شوند.
- [x] payload و idempotency contract strict و تست‌شده‌اند.
- [x] worker progress، lease extension، retry و terminal failure را ثبت می‌کند.
- [x] execution با وضعیت `running` پس از lease recovery قابل ادامه است.
- [x] پاسخ API، job identity را بدون حذف فیلدهای قبلی expose می‌کند.
- [x] Frontend قرارداد جدید را type-check می‌کند و polling قبلی حفظ شده است.
- [x] تست end-to-end API تا worker و Experiment نهایی وجود دارد.
- [x] تست PostgreSQL برای enqueue اتمیک و worker تولیدی آماده شده است.
- [ ] CI مالک مخزن تست PostgreSQL را روی commit نهایی سبز کند.

پس از پذیرش CI، مرحلهٔ بعد `P1-03` است: انتقال Walk-Forward Execution از `BackgroundTasks` به
`BackgroundJob` با progress و recovery در سطح fold.
