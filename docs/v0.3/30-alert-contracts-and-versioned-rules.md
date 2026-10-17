# P4-01 — قراردادهای Alert و Ruleهای نسخه‌دار

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P4-02**

تاریخ تصمیم: `2026-10-17`

مبنای کد: freeze پذیرفته‌شدهٔ P3 در commit
`10394a4cb34ce0daccd0a49d87a16914d95122a6`

این مرحله مرز pure دامنهٔ Alert را برای v0.3 تثبیت می‌کند. هیچ migration، repository، worker،
endpoint، صفحهٔ UI یا کانال بیرونی در P4-01 اضافه نمی‌شود.

## 1. محدودهٔ ثابت v1

| تصمیم | مقدار فریز‌شده |
| --- | --- |
| source اولیه | فقط `market_context` پذیرفته‌شدهٔ P3 |
| delivery | فقط Notification Inbox داخلی با مقدار `in_app` |
| severity | `info`، `warning` یا `critical` |
| rule | immutable، نسخه‌دار، checksum‌شده و دارای lineage نسخهٔ قبلی |
| source event | assessment دقیق Market Context با checksum و expiry |
| identity | deterministic برای rule، source reference، alert و deduplication key |
| freshness | context ناقص، stale، expired یا boundary-mismatch قابل انتشار نیست |
| معاملهٔ واقعی | کاملاً خارج از محدوده |

این قرارداد عمداً email، SMS، push، webhook و credential را اضافه نمی‌کند. افزودن هر delivery
channel تازه به schema/policy version تازه و گیت امنیت مستقل نیاز دارد.

## 2. Rule definition

`AlertRuleDefinition` یک نسخهٔ تغییرناپذیر از rule کاربر است و این موارد را نگه می‌دارد:

- `rule_key` و `rule_id` پایدار در تمام نسخه‌ها؛
- `rule_version` و `supersedes_version` پیوسته؛
- state، severity و شرط typed مربوط به Market Context؛
- TTL، بازهٔ deduplication و cooldown؛
- delivery داخلی و checksum کل تعریف.

نسخهٔ اول predecessor ندارد و هر نسخهٔ بعدی باید دقیقاً نسخهٔ قبلی را supersede کند. تغییر state،
severity، threshold یا TTL با mutation رکورد قبلی انجام نمی‌شود؛ یک definition تازه با version تازه
ساخته می‌شود.

## 3. شرط Market Context

`MarketContextAlertCondition` فقط روی سه مقدار صریح کار می‌کند:

- مجموعهٔ trendهای مجاز؛
- مجموعهٔ volatilityهای مجاز؛
- حداقل confidence.

مقادیر `undetermined` قابل هدف‌گیری نیستند و مجموعه‌ها باید مرتب و بدون تکرار باشند. v1 از expression
متنی یا کد قابل اجرا استفاده نمی‌کند؛ در نتیجه rule نمی‌تواند query یا منطق arbitrary وارد runtime
کند.

## 4. Source reference و fail-closed

`MarketContextAlertSourceReference` از `MarketContextProductView` ساخته می‌شود و assessment ID،
stream، pair، event-time، expiry، regime، confidence و نتیجهٔ consumption را همراه checksum نگه
می‌دارد.

یک source فقط زمانی قابل انتشار است که:

1. assessment دارای status برابر `ready` باشد؛
2. در زمان ارزیابی منقضی نشده باشد؛
3. `as_of` آن با boundary مورد انتظار برابر باشد؛
4. هیچ unavailable reason نداشته باشد.

Source نامعتبر همچنان می‌تواند برای ثبت suppression در مراحل بعد reference شود، اما
`AlertDraft.build` اجازهٔ ساخت خروجی publishable از آن را نمی‌دهد.

## 5. Alert draft و identity

`AlertDraft` خروجی publishable پیش از persistence است. این مدل rule reference و source reference
دقیق، severity، متن، creation time و expiry را حمل می‌کند.

- `alert_id` برای یک rule version و source event ثابت است؛
- `deduplication_key` نیز برای همان زوج deterministic است؛
- `draft_checksum` تمام متن و lineage خروجی را در برابر تغییر ناسازگار محافظت می‌کند؛
- expiry از کمینهٔ TTL rule و expiry منبع محاسبه می‌شود؛
- rule غیرفعال، source غیرقابل مصرف، source منقضی یا condition نامنطبق fail-closed می‌شود؛
- severity خروجی نمی‌تواند با rule version اختلاف داشته باشد.

P4-01 فقط identity و invariant را تعریف می‌کند. تصمیم durable دربارهٔ duplicate، cooldown، quiet
hours و snooze در مراحل بعد ثبت و قابل audit می‌شود.

## 6. Suppression reason contract

Reason codeهای ثابت v1 عبارت‌اند از:

- `rule_disabled`؛
- `source_not_consumable`؛
- `source_expired`؛
- `condition_not_matched`؛
- `duplicate`؛
- `cooldown_active`؛
- `quiet_hours`؛
- `snoozed`.

چهار مورد نخست در contract فعلی enforce می‌شوند. موارد durable/user-preference در P4-02 تا P4-05
پیاده‌سازی خواهند شد.

## 7. مرز مراحل بعد

| مرحله | مسئولیت |
| --- | --- |
| P4-02 | persistence و migration برای rule version، evaluation، alert و suppression |
| P4-03 | jobهای durable ارزیابی Alert و مصرف idempotent Market Context |
| P4-04 | Alert Center API/UI، acknowledgement و snooze |
| P4-05 | quiet hours، expiry و سیاست انتشار |
| P4-06 | Shadow/Paper evaluation بدون سفارش واقعی |
| P4-07 | Outcome Journal، performance، drift و false-positive |
| P4-08 | benchmark، acceptance و freeze نهایی P4 |

## 8. معیار خروج P4-01

- [x] schema و source domain v1 صریح و versioned است.
- [x] ruleها immutable، checksum‌شده و دارای lineage نسخه هستند.
- [x] conditionها typed و deterministic هستند.
- [x] source event و expiry کامل و tamper-evident است.
- [x] identity alert و deduplication key deterministic است.
- [x] context stale، ناقص یا boundary-mismatch قابل انتشار نیست.
- [x] delivery فقط in-app و بدون credential است.
- [x] هیچ persistence، route، worker، UI یا قابلیت live execution اضافه نشده است.

گام بعدی `P4-02 — Durable Alert Persistence and Deduplication` است.
