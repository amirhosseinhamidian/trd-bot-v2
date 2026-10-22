# P4-06 — ارزیابی آفلاین Paper / Shadow هشدارها

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P4-07**

## هدف

یک Alert منتشرشده می‌تواند برای یک افق زمانی مشخص وارد مشاهدهٔ `paper` یا `shadow` شود تا
در مرحلهٔ بعد نتیجهٔ آن سنجیده شود. این enrollment فقط evidence پژوهشی می‌سازد و هیچ سفارش،
اتصال معاملاتی، credential، wallet یا exposure واقعی ایجاد نمی‌کند.

## قرارداد و مرز ایمنی

`AlertSimulationRecord` یک رکورد immutable و checksum‌شده است که موارد زیر را pin می‌کند:

- شناسه و checksum دقیق Alert؛
- reference و checksum منبع Market Context؛
- نسخه و checksum دقیق Rule؛
- mode برابر `paper` یا `shadow`؛
- trend مورد انتظار در لحظهٔ انتشار؛
- افق ارزیابی، زمان شروع و پایان و actor؛
- `offline_only=true`؛
- `external_order_submission_allowed=false`.

شروع ارزیابی برای Alert منقضی fail-closed است. identity از `(alert_id, mode,
horizon_seconds)` ساخته می‌شود؛ بنابراین retry همان درخواست رکورد دیگری تولید نمی‌کند.

## Lifecycle

وضعیت از زمان و بدون mutation رکورد اصلی محاسبه می‌شود:

| وضعیت | معنا |
| --- | --- |
| `observing` | افق ارزیابی هنوز تمام نشده است |
| `awaiting_outcome` | افق تمام شده و P4-07 باید outcome را ثبت کند |

P4-06 هیچ سود/زیان، fill، quantity یا position مصنوعی نمی‌سازد؛ این مرحله فقط enrollment و
lineage لازم برای Outcome Journal را فراهم می‌کند.

## Persistence

جدول `alert_simulations` append-only است و با FK به `alerts` متصل می‌شود. constraintهای دیتابیس
نیز offline-only بودن، ممنوعیت submission خارجی، بازهٔ horizon و checksum را enforce می‌کنند.

## API

| Method | Route | کاربرد |
| --- | --- | --- |
| `GET` | `/api/v1/alerts/simulations` | فهرست و فیلتر ارزیابی‌ها |
| `GET` | `/api/v1/alerts/simulations/summary` | شمارش mode و lifecycle |
| `GET` | `/api/v1/alerts/simulations/{simulation_id}` | جزئیات و lineage |
| `POST` | `/api/v1/alerts/{alert_id}/simulations` | شروع idempotent مشاهدهٔ آفلاین |

## UI

Alert Center تعداد Paper، Shadow، observing و awaiting outcome را نشان می‌دهد. برای هر Alert
غیرمنقضی می‌توان افق `۱ ساعت`، `۴ ساعت`، `۲۴ ساعت` یا `۷ روز` را انتخاب و Paper یا Shadow را
شروع کرد. UI صریحاً برچسب «بدون سفارش واقعی» دارد.

## معیار خروج

- [x] قرارداد immutable و tamper-evident است.
- [x] retry همان mode/horizon idempotent است.
- [x] Alert منقضی fail-closed است.
- [x] lifecycle بدون تغییر رکورد اصلی محاسبه می‌شود.
- [x] API و UI فقط observation آفلاین ارائه می‌کنند.
- [x] هیچ route، credential یا capability اجرای زنده اضافه نشده است.

گام بعدی `P4-07 — Outcome Journal، performance، drift و false-positive` است.
