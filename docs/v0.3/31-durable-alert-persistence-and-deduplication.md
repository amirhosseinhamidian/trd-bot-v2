# P4-02 — ذخیره‌سازی پایدار Alert و Deduplication

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P4-03**

تاریخ تصمیم: `2026-10-17`

مبنای کد: P4-01 در commit
`45b3ef79250b873f2a3d6ecd635c0feb5c4a0ce2`

این مرحله قراردادهای P4-01 را به persistence اتمیک و قابل audit متصل می‌کند. هیچ worker، endpoint،
صفحهٔ UI، کانال بیرونی یا قابلیت معاملهٔ واقعی در P4-02 اضافه نمی‌شود.

## 1. مدل ذخیره‌سازی

| جدول | مسئولیت | قید اصلی |
| --- | --- | --- |
| `alert_rule_definitions` | نسخه‌های immutable هر Rule | کلید مرکب `rule_id + rule_version` و checksum یکتا |
| `alert_evaluations` | ثبت هر تصمیم publish یا suppress | یک نتیجه برای هر rule version و source event |
| `alerts` | Alertهای واقعاً منتشرشده در Inbox داخلی | `deduplication_key`، `evaluation_id` و checksum یکتا |

هر سه جدول payload کامل و versioned دامنه را نگه می‌دارند و هم‌زمان ستون‌های لازم برای query و
index را جداگانه ثبت می‌کنند. Alert منتشرشده به Evaluation، نسخهٔ دقیق Rule و assessment منبع
Market Context وصل است.

## 2. Evaluation پایدار

`AlertEvaluationRecord` نتیجهٔ تغییرناپذیر ارزیابی یک Rule version روی یک assessment دقیق است:

- `published`: بدون suppression reason و با `alert_id` و checksum همان Draft؛
- `suppressed`: حداقل یک reason پایدار و بدون Alert؛
- `evaluation_id`: deterministic از rule version، source kind و source event؛
- `evaluation_checksum`: checksum کل outcome و lineage؛
- timestamp ارزیابی با source reference یکسان است.

در حالت disabled، non-consumable یا expired، reason متناظر اجباری است. بنابراین مسیر fail-closed
فقط خطای runtime نیست و به‌صورت evidence قابل audit ذخیره می‌شود.

## 3. Lineage و کنترل دست‌کاری

پیش از write، repository این تطابق‌ها را بررسی می‌کند:

1. Rule reference با نسخهٔ persisted و checksum آن دقیقاً برابر باشد؛
2. assessment منبع وجود داشته باشد؛
3. source reference با بازسازی view در همان `evaluated_at` برابر باشد؛
4. Evaluation منتشرشده از همان Draft بازسازی شود؛
5. نسخهٔ تازهٔ Rule دقیقاً نسخهٔ persisted قبلی را supersede کند.

در نتیجه payload دست‌کاری‌شده، source ساختگی، version gap یا draft ناسازگار پیش از persistence رد
می‌شود.

## 4. Idempotency و deduplication

Retry دقیق همان Rule، Evaluation یا Alert رکورد جدید نمی‌سازد و نتیجهٔ persisted قبلی را برمی‌گرداند.
اگر همان identity با محتوای متفاوت دیده شود، operation با conflict بسته می‌شود.

Deduplication در دو سطح enforce می‌شود:

- unique constraint روی زوج `rule version + source event` در evaluation؛
- unique constraint روی `deduplication_key` در alert منتشرشده.

این قیود علاوه بر کنترل repository، raceهای concurrent را نیز در مرز دیتابیس متوقف می‌کنند.

## 5. مرز تراکنش

`SqlAlchemyAlertStore` هیچ commit داخلی انجام نمی‌دهد. caller مالک تراکنش است و Evaluation منتشرشده
و Alert متناظر در همان transaction نوشته می‌شوند. rollback بعد از stage کردن، هر دو رکورد را حذف
می‌کند و حالت نیمه‌ثبت‌شده باقی نمی‌ماند.

در P4-03 worker همین مرز را برای claim، ارزیابی deterministic و terminal job result مصرف خواهد کرد.

## 6. معیار خروج P4-02

- [x] migration برگشت‌پذیر برای Rule، Evaluation و Alert وجود دارد.
- [x] version lineage Rule در domain و repository enforce می‌شود.
- [x] source assessment و checksum آن پیش از write راستی‌آزمایی می‌شود.
- [x] publish و suppression هر دو durable و قابل audit هستند.
- [x] retry دقیق idempotent است و duplicate ایجاد نمی‌کند.
- [x] deduplication در خود دیتابیس constraint دارد.
- [x] Evaluation و Alert در transaction واحد ثبت یا rollback می‌شوند.
- [x] scope همچنان read-only، in-app و بدون credential یا live execution است.

گام بعدی `P4-03 — Durable Alert Evaluation Jobs` است.
