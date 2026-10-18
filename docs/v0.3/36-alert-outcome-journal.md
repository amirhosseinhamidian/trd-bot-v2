# P4-07 — Outcome Journal، performance، drift و false-positive

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P4-08**

## هدف

نتیجهٔ یک مشاهدهٔ پایان‌یافتهٔ `paper` یا `shadow` به‌صورت immutable و قابل audit ثبت می‌شود تا
کیفیت هشدارها بدون سفارش واقعی، دارایی، position یا اتصال معاملاتی قابل سنجش باشد.

## قرارداد و lineage

هر `AlertOutcomeRecord` دقیقاً به یک `AlertSimulationRecord` متصل است و موارد زیر را pin می‌کند:

- شناسه و checksum ارزیابی و Alert؛
- mode و trend مورد انتظار؛
- قیمت شروع، پایان، بیشینه و کمینهٔ مشاهده؛
- trend مشاهده‌شده؛
- raw return، directional return، بیشترین حرکت مساعد و نامساعد؛
- classification، drift و false-positive؛
- نسخه، checksum و threshold سیاست محاسبه؛
- زمان مشاهده، زمان ثبت و actor؛
- `offline_only=true` و `external_order_submission_allowed=false`.

شناسه از `simulation_id` ساخته می‌شود و روی `simulation_id` قید unique وجود دارد؛ در نتیجه retry
همان outcome را برمی‌گرداند و رکورد دوم تولید نمی‌کند. API update/delete وجود ندارد.

## سیاست محاسبه v1

`alert-outcome-policy-v1` از آستانهٔ ثابت `0.005` یا ۰٫۵٪ استفاده می‌کند:

| انتظار | directional return | نتیجه |
| --- | --- | --- |
| صعودی | `(end / start) - 1` | حداقل ۰٫۵٪ confirmed؛ حداکثر منفی ۰٫۵٪ false-positive؛ بین این دو neutral |
| نزولی | منفی raw return | همان حدود بالا |
| رنج | منفی قدرمطلق raw return | حرکت حداکثر ۰٫۵٪ confirmed؛ بیشتر از آن false-positive |
| نامشخص | منفی قدرمطلق raw return | neutral |

`drifted` مستقل از performance و وقتی true است که trend مشاهده‌شده با trend مورد انتظار برابر نباشد.
این تفکیک اجازه می‌دهد یک حرکت کوچک neutral باشد ولی هم‌زمان drift نیز ثبت شود.

## Fail-closed

- ثبت outcome پیش از `ends_at` با conflict رد می‌شود؛
- همهٔ قیمت‌ها باید مثبت باشند؛
- high نمی‌تواند از start/end کمتر و low نمی‌تواند از start/end بیشتر باشد؛
- `recorded_at` نمی‌تواند قبل از `observed_at` باشد؛
- هر تغییر در lineage، policy، metric یا فلگ‌های ایمنی checksum را نامعتبر می‌کند؛
- هیچ quantity، fill، P/L حساب، wallet، credential یا order در قرارداد وجود ندارد.

## Persistence و API

جدول `alert_outcomes` append-only است و با FK و unique constraint به `alert_simulations` متصل
می‌شود. endpointها:

| Method | Route | کاربرد |
| --- | --- | --- |
| `GET` | `/api/v1/alerts/outcomes` | فهرست و فیلتر journal |
| `GET` | `/api/v1/alerts/outcomes/summary` | performance، drift و false-positive تجمیعی |
| `GET` | `/api/v1/alerts/outcomes/{outcome_id}` | جزئیات immutable و lineage |
| `POST` | `/api/v1/alerts/simulations/{simulation_id}/outcome` | ثبت idempotent نتیجهٔ آفلاین |

## UI

Alert Center تعداد نتیجه‌های ثبت‌شده و در انتظار، نرخ false-positive، نرخ drift و میانگین بازده
جهت‌دار را نشان می‌دهد. فرم نتیجه فقط برای simulation پایان‌یافته و بدون outcome نمایش داده می‌شود.
ورودی قیمت دستی باید از منبع بازار قابل بازبینی تهیه شود و پس از ثبت قابل ویرایش نیست.

## معیار خروج

- [x] outcome فقط پس از پایان افق ثبت می‌شود.
- [x] lineage و سیاست محاسبه نسخه‌دار و tamper-evident هستند.
- [x] performance، excursion، drift و false-positive deterministic هستند.
- [x] retry idempotent و journal append-only است.
- [x] summary، API و UI نتیجه‌ها را بدون capability معاملاتی ارائه می‌کنند.
- [x] هیچ route، credential یا capability سفارش زنده اضافه نشده است.

گام بعدی `P4-08 — benchmark، acceptance و freeze نهایی P4` است.
