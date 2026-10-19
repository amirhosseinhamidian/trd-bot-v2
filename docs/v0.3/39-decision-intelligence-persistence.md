# P5-02 — Persistence تصمیم و Evidence

وضعیت: **پیاده‌سازی‌شده برای ورود به P5-03**

این مرحله قراردادهای P5-01 را به persistence پایدار، immutable و قابل audit متصل می‌کند. هنوز اجرای
Strategy، تولید Signal، worker، API، UI یا تغییر Portfolio انجام نمی‌شود. مرز سیستم همچنان
`Research / Shadow / Paper` و کاملاً offline-only است.

## 1. هدف

هر تصمیم آینده باید بتواند دقیقاً ثابت کند با کدام Dataset، Strategy، Market Context و Policy ساخته
شده است. retry نباید رکورد تکراری ایجاد کند، lineage ناقص نباید پذیرفته شود و Stageهای بعدی نباید
بدون پذیرش مرحلهٔ قبلی ثبت شوند.

## 2. مدل ذخیره‌سازی

### `decision_policy_definitions`

نسخه‌های Policy به‌صورت append-only نگهداری می‌شوند. کلید اصلی ترکیبی از `policy_id` و
`policy_version` است. نسخهٔ اول predecessor ندارد و هر نسخهٔ بعدی باید نسخهٔ بلافاصله قبل را ادامه
دهد. checksum، تعداد modeهای مجاز، state و مرزهای offline در ستون‌های queryable نیز ثبت می‌شوند.

### `decision_evaluation_intents`

هر Intent یک envelope immutable برای ورودی دقیق زنجیرهٔ تصمیم است و به این lineageها متصل می‌شود:

- `dataset_snapshots.dataset_id`؛
- `market_regime_assessments.assessment_id`؛
- نسخهٔ دقیق `decision_policy_definitions`؛
- Strategy reference نسخه‌دار و دارای behavior fingerprint در payload و ستون‌های queryable.

`evaluation_id`، `intent_checksum` و queue `idempotency_key` یکتا هستند. source، pair، market type،
timeframe، Strategy و زمان درخواست برای جست‌وجو و Monitoring بدون parse کردن JSON ذخیره می‌شوند.

### `decision_stage_outcomes`

برای هر `(evaluation_id, stage)` حداکثر یک Outcome immutable وجود دارد. disposition، تعداد reason
codeها، زمان ارزیابی و checksum قابل query هستند و payload کامل قرارداد برای بازسازی بدون افت اطلاعات
نگهداری می‌شود.

## 3. قواعد Repository

`SqlAlchemyDecisionIntelligenceStore` transaction را commit نمی‌کند؛ caller می‌تواند Policy، Intent
و Outcome را در یک unit of work اتمیک stage کند. قواعد زیر پیش از flush بررسی می‌شوند:

1. نسخهٔ Policy باید lineage پیوسته داشته باشد؛
2. retry همان Policy، Intent یا Outcome نتیجهٔ `created=false` می‌دهد؛
3. محتوای متفاوت با identity یا idempotency یکسان conflict است؛
4. Dataset باید واقعاً وجود داشته باشد و reference آن با snapshot persisted یکسان باشد؛
5. Market Context باید وجود داشته باشد و view آن در `requested_at` دقیقاً همان reference ثبت‌شده باشد؛
6. Policy reference باید با نسخهٔ persisted یکسان باشد؛
7. Outcome نباید قبل از Intent ثبت شده باشد؛
8. هر Stage بعدی فقط پس از Outcome پذیرفته‌شدهٔ predecessor بلافصل قابل ثبت است؛
9. ترتیب زمانی Outcomeها نباید به عقب برگردد.

عدم مصرف‌پذیری Context، disabled بودن Policy یا inactive بودن Strategy در persistence به outcome جعلی
تبدیل نمی‌شود. این داده‌ها عمداً ذخیره می‌شوند تا evaluator در P5-03 یک Outcome صریح، deterministic و
fail-closed تولید کند.

## 4. دفاع در عمق دیتابیس

Migration `20261019_0031` علاوه بر validation قرارداد و Repository، constraintهای دیتابیس را نیز
اضافه می‌کند:

- فقط modeهای `research`، `shadow` و `paper`؛
- فقط چهار Stage فریز‌شده در P5-01؛
- consistency میان disposition و تعداد reason code؛
- `offline_only=true` در تمام سه جدول؛
- `external_order_submission_allowed=false` در تمام سه جدول؛
- checksumهای ۶۴ کاراکتری؛
- foreign keyهای Dataset، Market Context، Policy و Intent؛
- unique constraintهای identity، checksum و idempotency.

## 5. سازگاری و عدم دامنه

- جدول‌های v0.2 و فازهای P1 تا P4 تغییر معنایی نمی‌کنند.
- schema قراردادهای P5-01 بدون تغییر باقی مانده است.
- هیچ credential، account، wallet، deposit، withdrawal یا live-order field افزوده نشده است.
- Strategy registry هنوز منبع metadata اجرایی است؛ P5-02 فقط reference دقیق آن را pin می‌کند.
- durable job و worker به P5-04 تعلق دارند.

## 6. گیت خروج P5-02

- [x] Policy versionها append-only، idempotent و دارای lineage پیوسته هستند.
- [x] Intent به Dataset، Market Context و Policy persisted متصل است.
- [x] queue idempotency key به‌صورت یکتا ذخیره می‌شود.
- [x] Stage outcomeها immutable، مرتب و دارای predecessor guard هستند.
- [x] caller transaction می‌تواند کل unit of work را rollback کند.
- [x] migration upgrade، metadata check و downgrade تست شده‌اند.
- [x] SQLite contract tests و PostgreSQL round-trip در کنار lint و type-check پوشش داده شده‌اند.
- [x] مرز offline-only در قرارداد، ORM و دیتابیس enforce می‌شود.

گام مجاز بعدی `P5-03 — Context-aware Strategy Evaluation` است. آن مرحله evaluator قطعی را روی Intent
persisted پیاده می‌کند و اولین Outcome مرحلهٔ `strategy_evaluation` را تولید خواهد کرد.
