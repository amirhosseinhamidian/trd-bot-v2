# TB2-013 — اجرای durable Optimization

## مرز مرحله

این مرحله اجرای plan محدود TB2-012 را به صف PostgreSQL موجود متصل می‌کند. API فقط intent را
اعتبارسنجی و execution/job را enqueue می‌کند؛ اجرای Strategy، Backtest، ساخت Experiment و ranking
فقط در worker مستقل و handler allowlisted انجام می‌شوند. از TB2-014 هر execution تازه علاوه بر
Experiment کامل، validation خارج‌ازنمونه و ranking robustness را نیز در همین worker انجام می‌دهد.

## قرارداد submission

`POST /api/v1/research/optimization-executions` با HTTP 202 پاسخ می‌دهد و سه مقدار دارد:

- `execution`: snapshot کامل execution؛
- `job`: خلاصهٔ امن job برای polling؛
- `created`: برای enqueue تازه `true` و برای intent تکراری `false`.

کلید idempotency از Dataset، Strategy name/version، objective، plan canonical، horizon و
BacktestConfig ساخته می‌شود. execution و job در یک transaction ثبت می‌شوند؛ شکست هر نیمه کل
submission را rollback می‌کند.

## lifecycle worker

handler نوع `optimization_execution` فقط payload نسخه‌دار شامل `execution_id` را می‌پذیرد. worker:

1. execution queued را running می‌کند و progress را heartbeat می‌زند؛
2. Dataset immutable و StrategyVersion دقیق را resolve می‌کند؛
3. فقط trialهای بعد از `completed_trials` را اجرا می‌کند؛
4. هر نتیجه را به Experiment immutable تبدیل و سپس ID آن را در execution ثبت می‌کند؛
5. برای execution جدید Walk-Forward run و evidence نسخه‌دار می‌سازد؛ رکورد legacy را با objective خام
   و رکورد جدید را با robustness score رتبه‌بندی می‌کند؛
6. execution و job را succeeded می‌کند و `execution_id` را result reference می‌گذارد.

پس از crash یا خطای زیرساختی، lease/retry صف اجرای دوباره را ممکن می‌کند و runner از trialهای ثبت‌شده
ادامه می‌دهد. خطاهای دامنه مانند Dataset مفقود یا trial نامعتبر fail-closed هستند. خطای موقت تا سقف
سه attempt retry می‌شود؛ پس از اتمام بودجه، execution با `optimization_attempts_exhausted` شکست می‌خورد.

## شواهد آزمون

پوشش این مرحله شامل enqueue اتمیک و rollback تزریقی، idempotency API، registry allowlist، سیاست خطای
retryable/non-retryable، اجرای end-to-end worker روی repositoryهای SQLAlchemy، progress/ranking،
Dataset مفقود و resume شدن پس از ذخیرهٔ اولین Experiment است. migration تازه‌ای لازم نیست.
