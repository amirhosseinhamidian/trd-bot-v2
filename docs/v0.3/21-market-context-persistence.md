# P3-02 — Persistence و Migration برای Market Context

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P3-03**

تاریخ تصمیم: `2026-10-16`

مبنای کد: P3-01 در commit ریموت
`11616d5675bcbc0df49180c789c1f26ad29086c0`

این مرحله قراردادهای pure در P3-01 را به persistence ماندگار و append-only متصل می‌کند. انتخاب
window، alignment، محاسبهٔ feature، الگوریتم regime، worker و API هنوز در محدودهٔ مراحل بعد هستند.

## 1. مدل ذخیره‌سازی

Migration `20261016_0025` چهار جدول ایجاد می‌کند:

| جدول | مسئولیت |
| --- | --- |
| `market_context_input_manifests` | snapshot کامل ورودی در یک `as_of` مشخص |
| `market_context_input_windows` | lineage نرمال‌شدهٔ هر window و نسخهٔ دقیق آن |
| `market_context_feature_snapshots` | feature values قطعی برای manifest و feature-set مشخص |
| `market_regime_assessments` | خروجی آماده یا وضعیت صریح غیرآماده |

هر رکورد علاوه بر ستون‌های queryable، payload نسخه‌دار کامل را ذخیره می‌کند. ستون‌های checksum،
تعداد، status، زمان و stream identity امکان index و audit را بدون parse کردن JSON فراهم می‌کنند؛
اما مدل domain هنگام read دوباره payload را اعتبارسنجی می‌کند.

## 2. Window lineage واقعی

هر ردیف `market_context_input_windows` دارای foreign key مرکب زیر است:

```text
(window_id, window_version)
    -> market_data_window_versions(window_id, version)
```

Repository پیش از insert نیز snapshot ذخیره‌شده را parse و از آن
`MarketContextWindowReference` تازه می‌سازد. reference ورودی باید با آن دقیقاً برابر باشد. بنابراین:

- window ساختگی یا حذف‌شده پذیرفته نمی‌شود؛
- نسخهٔ provisional نمی‌تواند وارد context شود؛
- تغییر source، event، bounds، payload checksum یا finalization time رد می‌شود؛
- همان lineage در JSON و جدول رابطه‌ای قابل audit است.

ترتیب `ordinal` همان ترتیب deterministic قرارداد P3-01 را حفظ می‌کند و uniqueness اجازهٔ تکرار یک
نسخهٔ window در manifest را نمی‌دهد.

## 3. Feature snapshot کامل

`MarketContextFeatureSnapshot` در این مرحله به قراردادهای domain اضافه شده است. factory آن پیش از
ساخت snapshot بررسی می‌کند:

1. هر requirement دقیقاً یک feature value داشته باشد؛
2. timeframe و calculation version برابر definition باشد؛
3. تعداد evidence windowها با lookback برابر باشد؛
4. checksumها دقیقاً به آخرین windowهای مرتب همان timeframe در manifest اشاره کنند؛
5. featureها با ترتیب کلید ذخیره و snapshot ID/checksum به‌صورت deterministic ساخته شوند.

جدول feature snapshot روی ترکیب manifest و feature-set uniqueness دارد. اجرای دوبارهٔ همان محاسبه
به همان رکورد اشاره می‌کند؛ نتیجهٔ متفاوت با همان نسخه به‌عنوان conflict رد می‌شود.

## 4. Regime assessment lineage

Assessment آماده باید به feature snapshot موجود اشاره کند. Repository انطباق این موارد را کنترل
می‌کند:

- manifest و input checksum؛
- source، pair و `as_of`؛
- feature-set version و checksum؛
- feature snapshot ID و checksum؛
- evidence assessment و تمام feature values ذخیره‌شده.

Assessment غیرآماده طبق قرارداد P3-01 هیچ feature snapshot، evidence یا تصمیم جزئی ندارد. check
constraint دیتابیس نیز ready/non-ready semantics، confidence و expiry را مستقل از کد enforce
می‌کند.

## 5. Transaction و idempotency

`SqlAlchemyMarketContextStore` عمداً `commit` انجام نمی‌دهد. caller می‌تواند manifest، feature
snapshot و assessment را در یک transaction ثبت کند. failure هر بخش کل bundle را rollback می‌کند.

متدهای stage:

- تکرار دقیق همان identity را با `created=false` برمی‌گردانند؛
- محتوای متفاوت با همان ID/checksum/version را رد می‌کنند؛
- قبل از insert تمام lineage بالادستی را بررسی می‌کنند؛
- با `flush` خطای constraint را داخل transaction caller آشکار می‌کنند.

این boundary برای P3-06 مناسب است؛ worker آینده مالک retry، commit و ثبت failure خواهد بود.

## 6. Query contract

Store این مسیرهای read را فراهم می‌کند:

- manifest با ID یا input checksum؛
- feature snapshot با ID یا manifest + feature-set؛
- assessment با ID یا manifest + algorithm؛
- آخرین assessment یک stream با cutoff اختیاری `as_of`.

هیچ projection mutable یا cache در این مرحله ایجاد نشده است. Monitoring و API در P3-07/P3-08 روی
همین رکوردهای immutable projectionهای خود را می‌سازند.

## 7. Migration و rollback

ترتیب upgrade:

1. input manifests؛
2. input windows؛
3. feature snapshots؛
4. regime assessments.

Downgrade ترتیب معکوس را رعایت می‌کند. migration هیچ جدول یا دادهٔ P0 تا P2 را تغییر نمی‌دهد و
backfill ساختگی نیز ندارد. Alembic `upgrade head`، drift check و `downgrade base` در تست migration
پوشش داده شده‌اند.

## 8. مرز امنیتی

تمام جداول فقط دادهٔ عمومی بازار، نسخه‌ها، checksumها و evidence محاسباتی را نگه می‌دارند. هیچ
credential، exchange account، wallet، deposit، withdrawal یا live-order field اضافه نشده است.

## 9. معیار خروج P3-02

- [x] schema چهارگانه و migration برگشت‌پذیر اضافه شده است.
- [x] manifest فقط به finalized window ذخیره‌شده متصل می‌شود.
- [x] feature snapshot کامل، نسخه‌دار و deterministic است.
- [x] assessment آماده به feature snapshot دقیق متصل است.
- [x] DB constraintهای checksum، status، confidence، expiry و uniqueness فعال‌اند.
- [x] stageها idempotent و conflictها fail-closed هستند.
- [x] transaction caller می‌تواند کل bundle را rollback کند.
- [x] readها payload را با قرارداد domain دوباره اعتبارسنجی می‌کنند.
- [x] migration و repository با تست پوشش داده شده‌اند.
- [x] محدودهٔ public read-only حفظ شده است.

گام بعدی `P3-03 — Multi-timeframe Alignment and Dataset Assembly` است.
