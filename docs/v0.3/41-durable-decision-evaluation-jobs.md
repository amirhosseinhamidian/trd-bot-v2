# P5-04 — اجرای پایدار Decision Evaluation

وضعیت: **پیاده‌سازی‌شده برای ورود به P5-05**

این مرحله evaluator قطعی P5-03 را به صف عمومی و پایدار `background_jobs` متصل می‌کند. اجرای Strategy
همچنان کاملاً offline است و هیچ API صرافی، credential، حساب، کیف پول یا مسیر ارسال سفارش به آن اضافه
نشده است.

## 1. قرارداد Job

نوع مجاز جدید `decision_evaluation` فقط payload نسخه‌دار
`decision-evaluation-job-v1` را می‌پذیرد. Payload موارد زیر را pin می‌کند:

- شناسه و checksum دقیق `DecisionEvaluationIntent`؛
- نسخه و checksum سیاست `strategy-context-compatibility-v1`؛
- زمان نخستین درخواست enqueue؛
- مرزهای ثابت `offline_only=true` و `external_order_submission_allowed=false`؛
- checksum کامل payload برای تشخیص دست‌کاری.

کلید ایدمپوتنسی از هویت منطقی Intent ساخته می‌شود. enqueue دوبارهٔ همان Intent رکورد جدید نمی‌سازد و
زمان درخواست اول را حفظ می‌کند.

## 2. چرخهٔ Worker

این workload از policy مرکزی صف استفاده می‌کند:

- حداکثر سه attempt؛
- backoff برابر ۵ و ۳۰ ثانیه؛
- lease پیش‌فرض پنج‌دقیقه‌ای و heartbeat در ابتدا و انتهای evaluator؛
- reclaim خودکار lease منقضی‌شده؛
- cancellation مشارکتی پیش از load، پیش از evaluate و پیش از commit؛
- retry خطاهای گذرای دیتابیس و fail-closed برای payload یا lineage نامعتبر.

Runner، Intent ذخیره‌شده و checksumهای payload را دوباره بررسی می‌کند و Outcome و
`StrategyEvaluationRecord` را در یک transaction ثبت می‌کند. اگر worker بعد از commit و پیش از ثبت
موفقیت job متوقف شود، attempt بعدی همان evidence ثبت‌شده را بدون ساخت duplicate بازیابی می‌کند.

## 3. خطاهای پایدار و امن

| کد | Retry | معنا |
| --- | --- | --- |
| `invalid_decision_evaluation_job_payload` | خیر | payload با schema یا checksum معتبر نیست |
| `decision_evaluation_intent_not_found` | خیر | Intent پایدار وجود ندارد |
| `decision_evaluation_integrity_error` | خیر | dataset، strategy registry یا lineage با Intent pin‌شده ناسازگار است |
| `decision_evaluation_rejected` | خیر | validation قطعی نتیجه شکست خورده است |
| `job_handler_failed` | بله | خطای گذرای داخلی، از جمله failure دیتابیس |

جزئیات exception داخلی یا payload در پاسخ monitoring منتشر نمی‌شوند.

## 4. Persistence و Monitoring

Migration جدیدی لازم نیست؛ جدول `background_jobs` از P2 تمام stateهای queue، lease، attempt،
cancellation و نتیجه را به‌صورت durable ذخیره می‌کند و ستون `kind` نیز برای workloadهای allowlisted
طراحی شده است. ساخت جدول موازی باعث دو منبع حقیقت برای lifecycle می‌شد.

خلاصهٔ عملیاتی موجود، job جدید را با kind، status، attempt، زمان‌بندی، lease expiry و error code نشان
می‌دهد، اما payload، idempotency key و worker ID را افشا نمی‌کند.

## 5. گیت خروج P5-04

- [x] نوع job و policy آن در allowlist مرکزی ثبت شده‌اند.
- [x] enqueue برای یک Intent ایدمپوتنت و tamper-evident است.
- [x] اجرای موفق، Outcome و Strategy Evaluation را اتمیک ثبت می‌کند.
- [x] خطای گذرا با backoff retry می‌شود.
- [x] lease منقضی‌شده بدون duplicate evidence reclaim می‌شود.
- [x] cancellation پیش از commit تمام evidence جزئی را rollback می‌کند.
- [x] payload نامعتبر بدون retry و با کد پایدار fail می‌شود.
- [x] job در monitoring امن عمومی قابل مشاهده است.
- [x] مرز offline-only در Contract، Runner و persisted result حفظ شده است.

گام مجاز بعدی `P5-05 — Candidate Construction and Ranking` است؛ تنها Evaluationهای accepted اجازهٔ
ورود به آن مرحله را خواهند داشت.
