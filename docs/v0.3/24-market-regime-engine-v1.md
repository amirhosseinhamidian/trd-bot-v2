# P3-05 — Deterministic Regime Engine v1

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P3-06**

تاریخ تصمیم: `2026-10-16`

مبنای کد: P3-04 در commit محلی
`e382b9cccdd1b1851bc029c28f2905f780ab110a`

این مرحله feature snapshot قطعی P3-04 را به assessment نسخه‌دار trend و volatility تبدیل می‌کند.
الگوریتم rule-based، قابل توضیح و قابل replay است؛ هیچ ML، prediction قیمت یا قابلیت معاملاتی در
این مرحله وجود ندارد.

## 1. Policy فریز‌شده

نسخهٔ الگوریتم `market-regime-v1` و checksum policy برابر است با:

```text
b8ace4b9c2a53c79f15b2f9da6689aae3dc344c35a178a00a4dd8e7acff153db
```

`MarketRegimePolicyV1` thresholdها، وزن‌ها، حداقل consensus، precision confidence و TTL را به‌صورت
immutable و tamper-evident نگه می‌دارد. تغییر هر مقدار نیازمند algorithm version جدید است.

## 2. Trend policy

هر slope با dead-band مخصوص timeframe به یکی از رأی‌های `-1`، `0` یا `+1` تبدیل می‌شود. دو سر
بازه inclusive هستند.

| Feature | Down | Neutral | Up | Weight |
| --- | ---: | ---: | ---: | ---: |
| `trend_slope_1h` | `≤ -0.0005` | بین دو حد | `≥ 0.0005` | `0.20` |
| `trend_slope_4h` | `≤ -0.0010` | بین دو حد | `≥ 0.0010` | `0.30` |
| `trend_slope_1d` | `≤ -0.0020` | بین دو حد | `≥ 0.0020` | `0.50` |

امتیاز trend برابر مجموع `vote × weight` است:

- `trending_up`: امتیاز حداقل `+0.50` و حداقل دو رأی مثبت؛
- `trending_down`: امتیاز حداکثر `-0.50` و حداقل دو رأی منفی؛
- در سایر حالت‌ها: `ranging`.

الزام دو رأی اجازه نمی‌دهد تنها تایم‌فریم روزانه با وزن 0.50 به‌تنهایی trend بسازد. تضاد timeframeها
نیز به‌جای تصمیم جهت‌دار ضعیف، به `ranging` ختم می‌شود.

## 3. Volatility policy

| Feature | Low | Normal | High | Weight |
| --- | ---: | ---: | ---: | ---: |
| `realized_volatility_1h` | `≤ 0.0030` | `(0.0030, 0.0120)` | `≥ 0.0120` | `0.60` |
| `realized_volatility_1d` | `≤ 0.0120` | `(0.0120, 0.0400)` | `≥ 0.0400` | `0.40` |

امتیاز volatility برابر `high_weight - low_weight` است:

- امتیاز حداقل `+0.50`: `high`؛
- امتیاز حداکثر `-0.50`: `low`؛
- در سایر حالت‌ها: `normal`.

وزن بیشتر `1h` تغییر اخیر volatility را زودتر منعکس می‌کند. تضاد low/high بین دو افق به `normal`
با confidence پایین‌تر منجر می‌شود و به‌صورت جهت‌دار overstate نمی‌شود.

## 4. Confidence

confidence تصمیم trend:

- برای trend جهت‌دار: قدر مطلق امتیاز trend؛
- برای ranging: `1 - abs(trend_score)`.

confidence volatility:

- برای low/high: وزن رأی‌های همان کلاس؛
- برای normal: بیشینهٔ `0.50` و وزن رأی‌های مستقیم normal.

confidence نهایی میانگین این دو مقدار و با `ROUND_HALF_EVEN` تا چهار رقم اعشار است. در نتیجه
agreement کامل مقدار `1.0000`، مرز consensus معمولاً `0.7500` و تضادها مقدار پایین‌تری می‌سازند.

این confidence احتمال آماری یا تضمین سود نیست؛ فقط میزان توافق قواعد deterministic همین policy را
نشان می‌دهد.

## 5. Lineage و expiry

Engine فقط feature snapshot canonical P3-04 را می‌پذیرد و این موارد را fail-closed کنترل می‌کند:

- feature-set version و checksum؛
- وجود دقیق هر پنج feature؛
- timeframe، calculation version و تعداد referenceهای هر evidence؛
- finite بودن همهٔ مقادیر؛
- غیرمنفی بودن volatilityها.

assessment تمام evidenceهای snapshot و ID/checksum آن را نگه می‌دارد. `assessed_at` برابر زمان
منطقی feature snapshot و `expires_at` دقیقاً یک ساعت بعد است. بنابراین retry همان input و algorithm
همان assessment ID و محتوای دقیق را تولید می‌کند.

Golden ID سناریوی unanimous-up/low-volatility این مرحله:

```text
market-regime-f616222a1a45b5da
```

## 6. Persistence boundary

`SqlAlchemyMarketRegimeEvaluator` feature snapshot canonical یک manifest را می‌خواند، assessment را
محاسبه و با `SqlAlchemyMarketContextStore` stage می‌کند. این سرویس:

- commit انجام نمی‌دهد؛
- در نبود feature snapshot خروجی ناقص ثبت نمی‌کند؛
- retry را به assessment موجود متصل می‌کند؛
- اگر نتیجهٔ ذخیره‌شده با replay همان ورودی برابر نباشد، خطای reproducibility می‌دهد.

transaction، retry job و ثبت failure در P3-06 اضافه می‌شوند.

## 7. مرز وضعیت‌های غیرآماده

`stale` و `insufficient_data` همچنان پیش از ساخت manifest در alignment P3-03 متوقف می‌شوند و نباید
به regime ناقص تبدیل شوند. Engine تنها snapshot کامل را ارزیابی می‌کند. نبود artifact بالادستی خطای
صریح orchestration است، نه مجوز ساخت تصمیم جزئی یا استفاده از دادهٔ قدیمی.

## 8. مرز امنیتی

Engine فقط featureهای مشتق از public market data را می‌خواند. هیچ credential، exchange account،
wallet، deposit، withdrawal، live order یا مسیر write به صرافی اضافه نشده است.

## 9. معیار خروج P3-05

- [x] algorithm version و policy checksum فریز شده‌اند.
- [x] threshold و وزن هر timeframe صریح و تست‌شده است.
- [x] trend به consensus حداقل دو timeframe نیاز دارد.
- [x] تضادها محافظه‌کارانه به ranging/normal تبدیل می‌شوند.
- [x] confidence قطعی، محدود و دارای precision ثابت است.
- [x] assessment به feature snapshot و تمام evidence متصل است.
- [x] expiry یک‌ساعته و event-time deterministic است.
- [x] golden cases برای up/down/range و low/normal/high ثبت شده‌اند.
- [x] persistence idempotent و replay mismatch به‌صورت fail-closed است.
- [x] محدودهٔ public read-only حفظ شده است.

گام بعدی `P3-06 — Durable Market Context Jobs` است.
