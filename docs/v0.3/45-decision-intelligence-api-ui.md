# P5-08 — API و رابط کاربری Decision Intelligence

وضعیت: **پیاده‌سازی‌شده برای پذیرش فاز پنج**

## 1. هدف و مرز

این مرحله evidence تغییرناپذیر P5-01 تا P5-07 را از مسیر فقط‌خواندنی در محصول موجود نمایش
می‌دهد. هیچ صفحهٔ موازی با Strategy، Signal، Candidate، Risk یا Portfolio ساخته نشده است و API نیز
هیچ عملیات اجرا، پذیرش، رد، مدیریت دارایی یا ارسال سفارش ارائه نمی‌کند.

مرزهای ثابت پاسخ و UI:

- `offline_only = true`
- `external_order_submission_allowed = false`
- حالت‌های مجاز فقط `research`، `shadow` و `paper`
- پیشنهاد Portfolio صرفاً advisory است و aggregate شبیه‌سازی‌شده را تغییر نمی‌دهد.
- نبود stage یا evidence با `null`، `pending` یا پاسخ `404` بیان می‌شود و مقدار ساختگی ندارد.

## 2. API فقط‌خواندنی

سه endpoint زیر زیر prefix نسخه‌دار `/api/v1` ثبت شده‌اند:

| روش | مسیر | کاربرد |
|---|---|---|
| `GET` | `/decision-intelligence/evaluations` | فهرست صفحه‌بندی‌شدهٔ summaryها |
| `GET` | `/decision-intelligence/evaluations/latest` | جدیدترین evidence منطبق با lineage صفحه |
| `GET` | `/decision-intelligence/evaluations/{evaluation_id}` | envelope کامل یک evaluation |

Collection و latest از فیلترهای `strategy_name`، `strategy_version`، `signal_id`، `candidate_id`،
`portfolio_id`، `stage` و `mode` پشتیبانی می‌کنند. `strategy_version` بدون `strategy_name` و ترکیب
بیش از یک identity از Signal/Candidate/Portfolio با `422` رد می‌شود. collection همچنین `limit`
بین ۱ تا ۱۰۰ و `offset` نامنفی دارد.

Summary فقط دادهٔ لازم برای catalog/status را برمی‌گرداند: identity، mode، strategy، dataset، آخرین
stage و disposition، تعداد stageهای کامل، تعداد signal، Candidate برتر، تصمیم risk و پیشنهاد
Portfolio. Detail قراردادهای اصلی و checksumدار زیر را بدون بازسازی یا تفسیر مجدد کنار هم قرار
می‌دهد:

- `DecisionEvaluationIntent`
- `StrategyEvaluationRecord | null`
- `DecisionCandidateRankingRecord | null`
- `DecisionRiskGateRecord | null`
- `DecisionPortfolioIntelligenceRecord | null`
- stage outcomeهای مرتب‌شده

API فقط از evidence ذخیره‌شده می‌خواند؛ مشاهدهٔ صفحه job جدیدی enqueue یا stage جدیدی evaluate
نمی‌کند. برای Signal و Candidate، عضویت در آرایهٔ immutable مربوطه بررسی می‌شود و فقط latest/top
بودن به‌عنوان جایگزین lineage استفاده نمی‌شود.

## 3. اتصال به صفحات موجود

یک presentation مشترک و دو‌زبانه به‌صورت progressive disclosure در صفحات فعلی قرار گرفته است:

| صفحه موجود | کلید اتصال | evidence برجسته |
|---|---|---|
| Strategy detail | نام و نسخه strategy | context، confidence و signal count |
| Signal detail | `signal_id` | stage outcome و context تثبیت‌شده |
| Candidate detail | `signal_id` مبدأ | rank، score و trade plan Candidate تصمیمی |
| Risk dashboard | جدیدترین evaluation دارای `risk_gate` | checkها و sizing شبیه‌سازی‌شده |
| Portfolio detail | `portfolio_id` snapshot | exposure، concentration، correlation، scenario و exit recommendation |

در تمام این صفحات badgeهای «فقط آفلاین» و «بدون ارسال سفارش» ثابت‌اند. چهار stage به‌ترتیب نمایش
داده می‌شوند و stage تولیدنشده به‌صورت pending باقی می‌ماند. checksumهای Intent، Dataset، Strategy،
Market Context و Policy داخل بخش پیشرفته قابل مشاهده‌اند تا صفحهٔ اصلی متراکم نشود.

## 4. رفتار خطا و نبود داده

- evaluation ناشناخته یا latest بدون match: `404`
- query نامعتبر: `422` با handler پاک‌سازی‌شدهٔ عمومی پروژه
- method نوشتنی روی collection: `405`
- evidence لینک‌نشده در UI: empty state خنثی؛ صفحهٔ اصلی همچنان قابل استفاده است.
- خطای غیرمنتظرهٔ transport یا schema پنهان نمی‌شود و به error boundary موجود می‌رسد.

## 5. سازگاری Next.js 16

داده در Server Componentهای route و با `params` ناهمگام دریافت می‌شود. Client Componentهای موجود
فقط evidence سریال‌پذیر را به‌عنوان prop می‌گیرند. درخواست‌ها `cache: no-store` دارند؛ بنابراین UI
هیچ تصمیم stale را به‌عنوان evidence جاری cache نمی‌کند. پیش از پیاده‌سازی، راهنماهای bundled
Next.js 16 برای Server/Client Components، data fetching، layouts/pages و error handling مبنا قرار
گرفتند.

## 6. گیت پذیرش

- [x] endpointهای collection، latest و detail فقط‌خواندنی‌اند.
- [x] فیلترها lineage کامل Signal/Candidate/Portfolio را بررسی می‌کنند.
- [x] stage ناقص جعل نمی‌شود.
- [x] پنج صفحهٔ موجود evidence مرتبط خود را نمایش می‌دهند.
- [x] exposure، concentration، correlation، scenario و exit recommendation روی Portfolio قابل رؤیت‌اند.
- [x] UI دو‌زبانه، responsive و دارای boundary صریح offline/no-order است.
- [x] قرارداد OpenAPI مصرف‌شده توسط frontend تست شده است.
- [x] unit/API/component/critical-journey tests پوشش دارند.
- [x] هیچ migration، مدیریت دارایی واقعی یا ارسال سفارش اضافه نشده است.

پس از سبز شدن backend، PostgreSQL migration checks و frontend quality/build، فاز پنج قابل freeze
است؛ گام بعدی باید acceptance/freeze صریح P5 باشد و نه گسترش Portfolio Intelligence به عملیات واقعی.
