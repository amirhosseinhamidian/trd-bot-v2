# اصلاح grid زمانی Nobitex

## علت اصلی

endpoint رسمی UDF نوبیتکس فیلد `t` را «شروع زمان» کندل اعلام می‌کند و timestamp را Unix UTC
می‌فرستد. با این حال boundary تجمیع provider برای timeframeهای بزرگ‌تر بر ساعت محلی بازار
قرار دارد، نه grid مبتنی بر Unix epoch که Datasetهای TRD BOT استفاده می‌کنند.

مشاهدهٔ مستقیم `BTC/USDT` در بازهٔ
`2026-09-27T00:00:00Z` تا `2026-09-28T00:00:00Z` این الگو را نشان داد:

| resolution | grid خام مشاهده‌شده |
| --- | --- |
| `15` | `00:00`, `00:15`, `00:30`, ... UTC |
| `60` | `00:30`, `01:30`, ... UTC |
| `240` | `00:30`, `04:30`, ... UTC |
| `D` | `20:30` UTC، معادل نیمه‌شب تهران در تاریخ نمونه |

OHLCV کندل خام `60` در `00:30` دقیقاً از چهار کندل `15` در بازهٔ نیمه‌باز
`[00:30, 01:30)` ساخته شده است. بنابراین کم‌کردن ۳۰ دقیقه از timestamp، interval را canonical
نمی‌کند و فقط برچسب نادرست `[00:00, 01:00)` روی دادهٔ بازه‌ای دیگر می‌گذارد. این تبدیل برای daily
هم به‌دلیل تغییر تاریخی offset تهران ثابت نیست.

منابع قرارداد:

- مستند OHLC نوبیتکس: <https://apidocs.nobitex.ir/market_data/دریافت-داده-های-ohlc>
- قرارداد UDF TradingView: <https://www.tradingview.com/charting-library-docs/latest/connecting_data/UDF/>

## تصمیم normalization

نسخهٔ `nobitex-utc-grid-v1` از کندل‌های native و UTC-aligned پانزده‌دقیقه‌ای به‌عنوان منبع استفاده
می‌کند و داخل adapter آن‌ها را روی boundaryهای canonical UTC بازتجمیع می‌کند:

- `15m`: بدون تغییر OHLCV و timestamp؛
- `1h`: چهار کندل کامل 15m؛
- `4h`: شانزده کندل کامل 15m؛
- `1d`: نودوشش کندل کامل 15m.

برای هر bucket، `open` از اولین کندل، `close` از آخرین کندل، `high/low` از extrema و `volume` از
جمع Decimal ساخته می‌شود. bucket ناقص یا هنوز باز منتشر نمی‌شود تا Quality Checker نبود آن را
به‌عنوان coverage ناقص گزارش کند. timestamp خام جابه‌جا یا با timezone سیستم عامل تفسیر نمی‌شود.

adapter timestamp پانزده‌دقیقه‌ای خارج از grid و duplicate متعارض را response نامعتبر می‌داند.
duplicate یکسان در مرز صفحه‌بندی idempotent باقی می‌ماند.

## Provenance و سازگاری

`normalization_version` به metadata عمومی provider و provenance ذخیره‌شدهٔ Dataset اضافه شده است.
این فیلد optional است؛ snapshotهای قدیمی و providerهای دیگر بدون migration قابل خواندن می‌مانند،
زیرا Dataset کامل در `payload_json` ذخیره می‌شود. checksum همچنان فقط از محتوای canonical candle و
بدون `received_at` ساخته می‌شود.

Quality Checker عمومی و قرارداد alignment آن تغییر نکرده‌اند. Kraken و providerهای دیگر نیز هیچ
normalization تازه‌ای دریافت نمی‌کنند.

## محدودیت عملیاتی

Nobitex در مستندات اعلام کرده دادهٔ دقیقه‌ای از ابتدای سال ۱۴۰۱ در دسترس است. در نتیجه timeframeهای
بازتجمیع‌شده نمی‌توانند پیش از محدودهٔ واقعی دادهٔ 15m پوشش مصنوعی بسازند؛ چنین درخواست‌هایی باید با
coverage ناقص یا no-data رد شوند. همچنین سقف صفحه‌بندی adapter روی تعداد candleهای منبع 15m اعمال
می‌شود، نه تعداد bucketهای نهایی.
