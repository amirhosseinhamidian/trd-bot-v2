# P1-05 — Unified Background Worker Policies

وضعیت: **تکمیل‌شده در کد؛ آمادهٔ پذیرش CI**

تاریخ تصمیم: `2026-10-11`

این مرحله بدهی `V3-D05` را می‌بندد. پنج workload بادوام اکنون از یک policy catalog مرکزی برای
allowlist، payload version، retry، cancellation و lease استفاده می‌کنند. ساخت job در routeها دیگر
بودجهٔ attempt را تکرار نمی‌کند و worker نیز lease متفاوتی برای claim و heartbeat ندارد.

## allowlist تولید

فقط این kindها در worker تولیدی ثبت می‌شوند:

| kind | payload v1 | attempt خودکار | backoff | lease |
| --- | --- | ---: | --- | --- |
| `market_data_import` | درخواست Import/Refresh نسخه‌دار | 1 | ندارد | 5 دقیقه |
| `dataset_file_import` | `stage_id` و checksum | 3 | 5s، سپس 30s | 5 دقیقه |
| `experiment_execution` | `execution_id` | 3 | 5s، سپس 30s | 5 دقیقه |
| `walk_forward_execution` | `execution_id` | 3 | 5s، سپس 30s | 5 دقیقه |
| `optimization_execution` | `execution_id` | 3 | 5s، سپس 30s | 5 دقیقه |

Import شبکه یک attempt صف دارد، چون adapter Provider داخل همان attempt retry محدود و طبقه‌بندی‌شده
انجام می‌دهد. retry دوبارهٔ کل Import می‌تواند درخواست شبکه و رکورد history تکراری بسازد. چهار
workload دیگر checkpoint/idempotency مناسب برای سه attempt دارند.

هر kind تازه باید هم‌زمان policy و handler داشته باشد. registry تولید هنگام startup تطابق دقیق
allowlist با policy catalog را کنترل می‌کند؛ بنابراین اضافه‌شدن enum بدون handler یا policy پنهان
نمی‌ماند. فقط payload version `1` پذیرفته می‌شود و version ناشناخته پیش از dispatch با
`unsupported_job_payload_version` به‌صورت دائمی fail می‌شود.

## retry و خطا

- خطای transient ناشناخته با پیام عمومی `job_handler_failed` ثبت می‌شود و جزئیات exception به API
  نشت نمی‌کند.
- attempt دوم پس از 5 ثانیه و attempt سوم پس از 30 ثانیه قابل claim است.
- payload نامعتبر برای هر پنج handler خطای ثابت `invalid_*_job_payload` می‌دهد و retry نمی‌شود.
- خطای domain غیرقابل retry همان code کنترل‌شدهٔ handler را حفظ می‌کند.
- retry دستی فقط برای job شکست‌خورده مجاز است و سقف سخت 10 attempt موجود را حفظ می‌کند.

## cancellation و lease

تمام workloadها cancellation تعاونی دارند. job صف‌شده فوراً لغو می‌شود؛ job در حال اجرا flag را در
checkpointهای امن می‌بیند و حتی اگر handler نتیجه برگرداند، repository نتیجه را publish نمی‌کند و
وضعیت نهایی `cancelled` می‌ماند.

lease claim و heartbeat هر دو به‌طور پیش‌فرض 5 دقیقه‌اند. handler دیگر duration مستقل دریافت
نمی‌کند و heartbeat همیشه lease همان worker را تمدید می‌کند. override عملیاتی CLI همچنان باید
مثبت باشد و برای claim و heartbeat با هم اعمال می‌شود.

## Storage و migration

تغییر schema یا migration دیتابیس لازم نیست. `run_after`، `max_attempts`، `payload_version`،
`cancel_requested` و leaseهای موجود قرارداد جدید را پوشش می‌دهند.

## معیار خروج P1-05

- [x] policy catalog دقیقاً هر پنج `BackgroundJobKind` را پوشش می‌دهد.
- [x] registry تولید دقیقاً با allowlist policy برابر است.
- [x] enqueueهای محصول budget را از policy مرکزی می‌گیرند.
- [x] backoff برابر 5 و 30 ثانیه است و پایان budget terminal می‌شود.
- [x] payload و payload version نامعتبر بدون retry رد می‌شوند.
- [x] cancellation بر success/retry اولویت دارد و result منتشر نمی‌شود.
- [x] claim و heartbeat از یک lease پنج‌دقیقه‌ای استفاده می‌کنند.
- [x] schema دیتابیس بدون تغییر است.

مرحلهٔ بعد `P1-06` است: تثبیت minimum Export و baseline پذیرفته‌شدهٔ v0.2 برای ورود به v0.3.
