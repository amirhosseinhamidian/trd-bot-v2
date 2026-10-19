# P5-03 — ارزیابی Strategy آگاه از Market Context

وضعیت: **پیاده‌سازی‌شده برای ورود به P5-04**

این مرحله نخستین runtime قطعی Decision Intelligence را روی Intent ذخیره‌شده اجرا می‌کند. خروجی شامل
Outcome مرحلهٔ `strategy_evaluation`، سیگنال‌های immutable و evidence نسخه‌دار سیاست سازگاری است.
هیچ worker، API، UI، Candidate، Risk decision، تغییر Portfolio یا اجرای سفارش واقعی در P5-03 وجود
ندارد.

## 1. سیاست سازگاری نسخهٔ اول

`strategy-context-compatibility-v1` یک ماتریس ثابت و tamper-evident است:

| Strategy | Trend مجاز | Volatility مجاز | حداقل Confidence |
| --- | --- | --- | --- |
| EMA Crossover 1.0.0 | Trending Up / Trending Down | Low / Normal / High | 0.60 |
| SMA Crossover 1.0.0 | Trending Up / Trending Down | Low / Normal / High | 0.60 |
| RSI Threshold 1.0.0 | Ranging | Low / Normal | 0.60 |

این سیاست دربارهٔ سودآوری پیش‌بینی نمی‌کند. تنها مشخص می‌کند اجرای یک خانوادهٔ Strategy در Context
فعلی از نظر محصول قابل پذیرش است یا باید پیش از تولید Signal متوقف شود. ریسک Position و Portfolio در
Stageهای بعدی بررسی خواهد شد.

## 2. ترتیب fail-closed

Evaluator به‌ترتیب زیر عمل می‌کند:

1. Dataset کامل را با reference ثبت‌شده در Intent تطبیق می‌دهد؛ mismatch یک integrity error است، نه
   تصمیم تجاری؛
2. Policy غیرفعال، Strategy deprecated و Context غیرقابل‌مصرف را با disposition برابر
   `unavailable` ثبت می‌کند؛
3. Confidence پایین یا ناسازگاری Strategy/Regime را با disposition برابر `rejected` ثبت می‌کند؛
4. metadata و behavior fingerprint رجیستری اجرایی را با Strategy reference تطبیق می‌دهد؛
5. Strategy را فقط پس از عبور از gateها اجرا می‌کند؛
6. نبود Signal جهت‌دار را به `deferred / signal_neutral` تبدیل می‌کند؛
7. وجود حداقل یک Signal معتبر را به outcome برابر `accepted` تبدیل می‌کند.

Signal خنثی به‌صورت رکورد ساختگی ایجاد نمی‌شود. مجموعهٔ خالی Signal evidence صریح حالت neutral است.
خطای رجیستری، fingerprint، Dataset یا lineage نیز به outcome تجاری جعلی تبدیل نمی‌شود و برای مدیریت
در worker آینده بالا می‌آید.

## 3. Determinism و idempotency

- زمان معنایی Evaluation همان `intent.requested_at` است؛ زمان wall-clock یا retry وارد checksum
  نمی‌شود؛
- Signalها بر اساس `(candle_close_time, signal_id)` مرتب و یکتا می‌شوند؛
- Outcome، Signalها، نسخه و checksum سیاست سازگاری داخل `StrategyEvaluationRecord` checksum می‌شوند؛
- اجرای دوبارهٔ همان Intent همان Record را برمی‌گرداند؛
- Dataset بعد از مرز Context، Signal با lineage متفاوت یا Signal آینده پذیرفته نمی‌شود.

## 4. Persistence

جدول append-only جدید `decision_strategy_evaluations` evidence کامل را ذخیره می‌کند و با foreign key
به Intent و Outcome مرحله متصل است. ستون‌های disposition، تعداد Signal، آخرین Signal، Policy checksum
و evaluated_at برای Monitoring قابل query هستند. Repository تنها داخل transaction متعلق به caller
flush می‌کند و commit مستقل انجام نمی‌دهد.

Migration `20261019_0032` علاوه بر foreign keyها، consistency میان disposition و Signal count، مرز
offline-only، ممنوعیت external order و طول checksumها را در دیتابیس enforce می‌کند.
Migration `20261019_0033` نیز نام check constraintهای بلند Decision Intelligence را برای سازگاری
یکسان Alembic با PostgreSQL و SQLite کوتاه و نرمال می‌کند.

## 5. مرز امنیتی و عدم دامنه

- فقط Dataset immutable و Market Context ثبت‌شده خوانده می‌شوند؛
- هیچ credential، account، wallet، deposit، withdrawal یا live-order field وجود ندارد؛
- `offline_only=true` و `external_order_submission_allowed=false` در Contract، ORM و DB ثابت‌اند؛
- enqueue، lease، retry و recovery به P5-04 تعلق دارند؛
- Candidate ranking و Risk/Portfolio هنوز اجرا نمی‌شوند.

## 6. گیت خروج P5-03

- [x] سیاست Strategy/Regime نسخه‌دار، deterministic و tamper-evident است.
- [x] Context نامعتبر، Policy disabled و Strategy inactive به‌صورت fail-closed ثبت می‌شوند.
- [x] Context ناسازگار و uncertainty بالا پیش از اجرای Strategy رد می‌شوند.
- [x] metadata و behavior fingerprint رجیستری با Intent pin‌شده تطبیق داده می‌شوند.
- [x] Signalهای معتبر با lineage و boundary check تولید می‌شوند.
- [x] neutral، accepted، rejected و unavailable semantics تست شده‌اند.
- [x] Evaluation record و Stage outcome اتمیک، append-only و idempotent ذخیره می‌شوند.
- [x] migration و محدودیت‌های offline-only پوشش داده شده‌اند.

گام مجاز بعدی `P5-04 — Durable Decision Evaluation Jobs` است: enqueue idempotent، worker lease، retry،
reclaim، cancellation و monitoring برای همین evaluator، بدون تغییر semantics قطعی P5-03.
