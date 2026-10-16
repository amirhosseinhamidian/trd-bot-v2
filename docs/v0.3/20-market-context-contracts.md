# P3-01 — قراردادهای Market Context

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P3-02**

تاریخ تصمیم: `2026-10-16`

مبنای کد: freeze پذیرفته‌شدهٔ P2 در commit
`211bdd49c7f59e77eaaae009feb3e97ae2c7a620`

این مرحله مرز دامنه و قراردادهای pure مربوط به Market Context را تثبیت می‌کند. هیچ migration،
repository، worker، endpoint، UI، محاسبهٔ feature یا الگوریتم regime در P3-01 اضافه نمی‌شود.

## 1. محدودهٔ ثابت v1

| تصمیم | مقدار فریز‌شده |
| --- | --- |
| دامنه | `crypto-spot-public-read-only` |
| anchor timeframe | `1h` |
| context timeframes | `4h` سپس `1d` |
| timezone | `UTC` |
| مرز window | `[start, end)` یا `left_closed_right_open` |
| ورودی مجاز | فقط نسخهٔ `finalized` از Market Data Window |
| provider lineage | تمام windowهای یک manifest از یک source واحد |
| زمان مبنا | `event-time` در فیلد `as_of`، نه processing time |
| خروجی regime | trend + volatility + confidence + evidence + expiry |
| ML/prediction | خارج از v1 و خارج از P3 |

`15m` همچنان در قرارداد عمومی Market Data معتبر است، اما در Market Context v1 مصرف نمی‌شود. افزودن
آن به context به policy version تازه نیاز دارد و نباید با تغییر پنهانی v1 انجام شود.

## 2. Alignment policy

`MarketContextAlignmentPolicy` با schema و policy version یکسان
`market-context-alignment-policy-v1`، تصمیم‌های بالا را به contract قابل تست تبدیل می‌کند.

قواعد هم‌ترازی:

1. `as_of` باید دقیقاً روی مرز ساعتی UTC باشد.
2. آخرین `1h` باید در `as_of` تمام شده باشد.
3. آخرین `4h` و `1d` فقط آخرین window کاملاً بسته‌شده در یا پیش از `as_of` هستند.
4. window ناقص آینده، حتی اگر provider آن را برگرداند، وارد manifest نمی‌شود.
5. history هر timeframe باید مرتب و بدون gap باشد.
6. ترکیب sourceها در یک manifest ممنوع است؛ fallback در لایهٔ ingestion ثبت می‌شود، نه اینکه lineage
   محاسبه پنهان شود.

برای نمونه در `as_of=2026-10-16T12:00:00Z`، انتهای آخرین windowهای قابل مصرف به‌ترتیب عبارت‌اند
از `12:00` برای `1h`، `12:00` برای `4h` و `00:00` برای `1d`.

## 3. Finalized window reference

`MarketContextWindowReference` فقط از `MarketDataWindowSnapshot` نهایی ساخته می‌شود و این lineage
را نگه می‌دارد:

- `window_id` و version؛
- source، pair، timeframe و event-time bounds؛
- `event_id` و payload checksum؛
- زمان finalization؛
- checksum مستقل reference.

تغییر هر فیلد lineage بدون محاسبهٔ دوبارهٔ checksum هنگام parse رد می‌شود. استفاده از provisional
window نیز fail-closed است؛ snapshot پژوهشی نباید بعداً بی‌صدا با بسته‌شدن candle تغییر کند.

## 4. Input manifest

`MarketContextInputManifest` مجموعهٔ مرتب و کامل windowهایی است که یک اجرای feature/regime دقیقاً
مصرف می‌کند. `input_checksum` و `manifest_id` از policy، stream identity، `as_of` و تمام referenceها
به‌صورت deterministic ساخته می‌شوند.

این manifest خود نتیجهٔ alignment موفق است. وضعیت‌های incomplete یا stale نباید با جعل window در
آن نمایش داده شوند؛ P3-03 نتیجهٔ alignment و reason codeهای آن وضعیت‌ها را روی همین مرز اضافه می‌کند.

## 5. Feature contract

`MarketContextFeatureRequirement` فقط interface هر feature را تثبیت می‌کند:

- کلید پایدار؛
- timeframe؛
- تعداد window موردنیاز؛
- calculation version؛
- الزام finalized input.

`MarketContextFeatureSetDefinition` requirements را با ترتیب کلید و checksum تغییرناپذیر نگه
می‌دارد. فهرست واقعی featureهای v1، فرمول‌ها، precision و golden values در P3-04 فریز می‌شوند؛
بنابراین P3-01 هیچ threshold یا lookback محصولی را حدس نمی‌زند.

## 6. Regime assessment contract

`MarketRegimeAssessment` قرارداد خروجی آیندهٔ P3-05 است:

- status یکی از `ready`، `insufficient_data` یا `stale`؛
- trend یکی از `trending_up`، `trending_down`، `ranging` یا `undetermined`؛
- volatility یکی از `low`، `normal`، `high` یا `undetermined`؛
- confidence در بازهٔ صفر تا یک؛
- evidence نسخه‌دار متصل به checksum windowها؛
- feature-set version/checksum، algorithm version، event-time `as_of` و expiry.

برای status آماده، regime مشخص، confidence مثبت، evidence و expiry آینده الزامی است. برای status
غیرآماده، هیچ تصمیم ناقص قابل انتشار نیست: هر دو regime باید `undetermined`، confidence صفر، evidence
خالی، expiry فوری و حداقل یک issue code موجود باشد.

شناسهٔ assessment از stream، `as_of`، input checksum، feature-set version و algorithm version ساخته
می‌شود. در نتیجه replay همان ورودی و نسخه‌ها همان identity را دارد؛ تغییر داده یا الگوریتم identity
تازه می‌سازد.

## 7. مرز مراحل بعد

| مرحله | مسئولیت |
| --- | --- |
| P3-02 | persistence و migration برای manifest، feature snapshot و assessment |
| P3-03 | انتخاب window، alignment، gap/stale reason و multi-timeframe dataset |
| P3-04 | feature set واقعی v1، precision، formulas و golden values |
| P3-05 | الگوریتم deterministic regime، thresholdها و calibration |
| P3-06+ | job، monitoring، API/UI، benchmark و freeze |

P3-01 هیچ داده‌ای persist نمی‌کند و route یا worker جدید ندارد؛ در نتیجه rollback آن فقط حذف package،
سند و تست‌های contract است و به schema دیتابیس اثر ندارد.

## 8. معیار خروج P3-01

- [x] محدوده و matrix تایم‌فریم v1 فریز شده است.
- [x] UTC، event-time و window boundary صریح‌اند.
- [x] فقط finalized window و lineage تک-source پذیرفته می‌شود.
- [x] manifest deterministic و tamper-evident است.
- [x] interface feature set نسخه‌دار و checksum شده است.
- [x] status و evidence/expiry خروجی regime فریز شده‌اند.
- [x] insufficient/stale نمی‌تواند تصمیم جزئی منتشر کند.
- [x] قراردادها immutable، extra-forbid و دارای تست‌اند.
- [x] هیچ قابلیت معاملاتی، credential یا write به exchange اضافه نشده است.

گام بعدی `P3-02 — Persistence and Migration for Market Context` است.
