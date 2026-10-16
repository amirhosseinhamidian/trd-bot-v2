# P3-04 — Deterministic Feature Set v1

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P3-05**

تاریخ تصمیم: `2026-10-16`

مبنای کد: P3-03 در commit ریموت
`e7a93fbf694393bbe9eb3645f0d317c961abde5b`

این مرحله feature-set واقعی Market Context را فریز می‌کند. هر feature فقط از windowهای دقیق manifest
P3-03 محاسبه می‌شود و همراه با checksum تمام windowهای مصرف‌شده در feature snapshot ثبت می‌گردد.
thresholdها و تبدیل featureها به regime هنوز در محدودهٔ P3-05 هستند.

## 1. تعریف فریز‌شده

نسخهٔ feature-set برابر `market-context-features-v1` و checksum تعریف آن برابر است با:

```text
50b734675aa69382002e87e0d2a512d28182dc24048d708874936715c70ac683
```

| Feature key | Timeframe | Lookback | Formula version |
| --- | --- | ---: | --- |
| `realized_volatility_1d` | `1d` | 14 | `close-return-volatility-v1` |
| `realized_volatility_1h` | `1h` | 24 | `close-return-volatility-v1` |
| `trend_slope_1d` | `1d` | 14 | `normalized-close-slope-v1` |
| `trend_slope_1h` | `1h` | 24 | `normalized-close-slope-v1` |
| `trend_slope_4h` | `4h` | 18 | `normalized-close-slope-v1` |

این مجموعه سه افق trend و دو افق volatility را پوشش می‌دهد. تعداد featureها عمداً کوچک است تا
regime v1 قابل توضیح، قابل calibration و قابل replay باقی بماند.

## 2. فرمول trend slope

برای closeهای مثبت `C₀ ... Cₙ₋₁` ابتدا سری نسبت به قیمت اول نرمال می‌شود:

```text
yᵢ = Cᵢ / C₀
xᵢ = i
```

سپس شیب OLS بر حسب «تغییر نرمال‌شده به ازای هر window» محاسبه می‌شود:

```text
slope = Σ((xᵢ - x̄)(yᵢ - ȳ)) / Σ((xᵢ - x̄)²)
```

نرمال‌سازی باعث می‌شود مقدار بین دارایی‌هایی با مقیاس قیمت متفاوت قابل مقایسه باشد. استفاده از همهٔ
نقاط lookback نیز نسبت به مقایسهٔ صرفاً ابتدا و انتهای بازه، نویز تک‌نقطه‌ای کمتری دارد.

## 3. فرمول realized volatility

ابتدا simple close returnهای متوالی محاسبه می‌شوند:

```text
rᵢ = Cᵢ / Cᵢ₋₁ - 1
```

خروجی، انحراف معیار population همین returnها است:

```text
σ = sqrt(Σ(rᵢ - r̄)² / count(r))
```

مقدار annualize نمی‌شود؛ بنابراین regime engine در P3-05 آن را با threshold مختص timeframe مصرف
می‌کند و هیچ فرض تقویمی پنهان وارد قرارداد نمی‌شود.

## 4. Precision و rounding

- تمام ورودی‌ها و عملیات با `Decimal` انجام می‌شوند؛
- precision میانی برابر 50 رقم است؛
- خروجی با 12 رقم اعشار quantize می‌شود؛
- rounding برابر `ROUND_HALF_EVEN` است؛
- close صفر، منفی، NaN یا infinity به‌صورت fail-closed رد می‌شود.

این قواعد بخشی از formula version هستند. تغییر precision، rounding، نوع return یا population/sample
deviation نیازمند calculation version و feature-set version جدید است.

## 5. Lineage دقیق

محاسبه‌گر pure مجموعهٔ snapshotها را با تمام identityهای manifest مقایسه می‌کند:

1. هیچ window مفقود، اضافه یا تکراری پذیرفته نمی‌شود؛
2. هر snapshot باید finalized باشد؛
3. reference بازسازی‌شده باید از نظر ID، version، event، checksum، bounds و finalization time با
   manifest یکسان باشد؛
4. هر feature فقط suffix دقیق lookback خود را مصرف می‌کند؛
5. evidence همان reference checksumها را با ترتیب event-time ثبت می‌کند.

در نتیجه تغییر حتی یک candle، revision یا ترتیب lineage به snapshot identity/checksum متفاوت منجر
می‌شود.

## 6. زمان منطقی و replay

`calculated_at` در snapshot برابر بیشینهٔ `manifest.created_at` و آخرین finalization time ورودی است.
زمان واقعی اجرای worker بعداً در job P3-06 ثبت می‌شود. جدا کردن زمان منطقی artifact از processing
time باعث می‌شود retry همان manifest در ساعت دیگری دقیقاً همان snapshot، ID و checksum را بسازد.

Golden fixture این مرحله علاوه بر مقادیر feature، snapshot زیر را فریز می‌کند:

```text
market-context-features-da0510397d66162a
da0510397d66162a14cadb604ca7b51b6478f105849e12923637ace37fdc515a
```

## 7. Persistence boundary

`SqlAlchemyMarketContextFeatureCalculator` manifest ذخیره‌شده و نسخه‌های دقیق window آن را بارگیری
می‌کند، محاسبهٔ pure را اجرا و نتیجه را با `SqlAlchemyMarketContextStore` stage می‌کند. این کلاس:

- commit انجام نمی‌دهد؛
- manifest یا window مفقود را رد می‌کند؛
- اجرای دوباره را به همان feature snapshot موجود متصل می‌کند؛
- محاسبهٔ جزئی یا feature ناقص persist نمی‌کند.

transaction، retry و failure handling در P3-06 به worker واگذار می‌شوند.

## 8. مرز امنیتی

feature-set فقط closeهای finalized public market data و lineage آن‌ها را مصرف می‌کند. هیچ credential،
exchange account، wallet، deposit، withdrawal، order یا مسیر write به صرافی اضافه نشده است.

## 9. معیار خروج P3-04

- [x] feature-set نسخهٔ ۱ و checksum آن فریز شده است.
- [x] lookback هر feature و formula version صریح است.
- [x] فرمول‌های trend و volatility با Decimal قطعی پیاده شده‌اند.
- [x] precision و rounding قرارداد تست‌شده دارند.
- [x] snapshot فقط از lineage دقیق manifest ساخته می‌شود.
- [x] evidence هر feature به windowهای واقعی مصرف‌شده متصل است.
- [x] retry همان snapshot ID/checksum را تولید می‌کند.
- [x] golden vectors و golden snapshot در تست ثبت شده‌اند.
- [x] persistence idempotent و تحت transaction caller است.
- [x] محدودهٔ public read-only حفظ شده است.

گام بعدی `P3-05 — Deterministic Regime Engine v1` است.
