# TB2-003.5A — ماتریس قابلیت و آزمون دسترسی providerها

هدف این مرحله انتخاب صرافی با حدس یا شهرت نیست. ابتدا قرارداد رسمی endpoint و سپس دسترسی واقعی
از اینترنت مستقیم ایران سنجیده می‌شود. هیچ provider در این سند هنوز «مناسب ایران» اعلام نشده است؛
این تصمیم فقط پس از سه گزارش واقعی، کنترل عمق تاریخچه و بررسی شرایط استفاده گرفته می‌شود.

این مرحله فقط endpoint عمومی و read-only را می‌سنجد. API key، حساب کاربری، سفارش، معامله و برداشت
در ابزار probe پشتیبانی نمی‌شوند.

## ماتریس نامزدها

| نامزد | نوع داده و credential | محدودیت مستند مؤثر بر v0.2 | کندل باز و معنای داده | probe این مرحله | تصمیم فعلی |
| --- | --- | --- | --- | --- | --- |
| `binance-public` | tape صرافی، endpoint عمومی | adapter فعلی پروژه؛ دسترسی مستقیم ایران باید جداگانه سنجیده شود. | adapter فعلی فقط کندل بسته را وارد می‌کند. | در این ابزار تکرار نشده؛ benchmark موجود پروژه است. | fallback موجود، نه انتخاب قطعی |
| `bitstamp-public` | tape صرافی، OHLC عمومی بدون credential | `limit` بین ۱ تا ۱۰۰۰؛ stepهای ۱۵m/۱h/۴h/۱d پشتیبانی می‌شوند. | پارامتر `exclude_current_candle=true` کندل باز را حذف می‌کند؛ volume مربوط به همان بازار است. | BTC/USD، دو کندل ۱h بسته | نامزد adapter |
| `kraken-public` | tape صرافی، OHLC عمومی بدون credential | حداکثر ۷۲۰ کندل اخیر و دادهٔ قدیمی‌تر با `since` قابل دریافت نیست؛ timeframeهای لازم موجودند. | آخرین ردیف همیشه کندل جاری و نهایی‌نشده است؛ adapter باید آن را حذف کند. | XBT/USD، ۱h | نامزد محدود؛ عمق تاریخچه احتمالاً مانع است |
| `coinbase-exchange-public` | tape صرافی، candles عمومی | حداکثر ۳۰۰ کندل در هر درخواست؛ ۱۵m/۱h/۱d موجود است اما ۴h مستقیم نیست و باید با قرارداد روشن resample شود. | پاسخ `[time, low, high, open, close, volume]` است؛ مرتب‌سازی و بسته‌بودن آخرین bucket باید در adapter قطعی شود. | BTC/USD، ۱h | نامزد adapter مشروط به ۴h و دسترسی |
| `nobitex-public` | tape صرافی داخلی، OHLC عمومی و بدون token روی host رسمی `apiv2.nobitex.ir` | حداکثر ۵۰۰ کندل در هر درخواست، pagination با `page`، دادهٔ دقیقه‌ای از آغاز ۱۴۰۱ و سقف ۶۰ درخواست در دقیقه طبق مستند رسمی. | پاسخ TradingView UDF با ستون‌های `t/o/h/l/c/v`؛ قرارداد کندل آخر باید با گزارش واقعی و fixture تثبیت شود. | BTC/USDT، سه ساعت اخیر در ۱h | نامزد adapter داخلی |
| `coinpaprika-free` | قیمت تجمیعی VWAP، نه tape یک صرافی | پلن Free فقط ۲۴ ساعت اخیر و interval برابر ۲۴h دارد. | کندل روز جاری تا پایان روز تغییر می‌کند و volume تجمیعی است. | OHLC روز جاری BTC/USD فقط برای connectivity | fallback اضطراری؛ برای منبع اصلی تحقیق رد می‌شود |
| CoinGecko Demo | aggregator و نیازمند API key | granularity خودکار و محدودیت‌های پلن؛ با قرارداد timeframe ثابت پروژه هم‌راستا نیست. | OHLC تجمیعی است. | عمداً ندارد؛ probe بدون secret است. | تحقیق تکمیلی، نه adapter این مرحله |

منابع رسمی مبنای ماتریس:

- [Bitstamp OHLC API](https://www.bitstamp.net/api/#ohlc-data)
- [Kraken Get OHLC Data](https://docs.kraken.com/api-reference/market-data/get-ohlc-data)
- [Coinbase Exchange Product Candles](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
- [Nobitex دریافت داده‌های OHLC](https://apidocs.nobitex.ir/market_data/%D8%AF%D8%B1%DB%8C%D8%A7%D9%81%D8%AA-%D8%AF%D8%A7%D8%AF%D9%87-%D9%87%D8%A7%DB%8C-ohlc)
- [CoinPaprika Historical OHLC](https://docs.coinpaprika.com/api-reference/coins/get-historical-ohlc)
- [CoinGecko OHLC](https://docs.coingecko.com/reference/coins-id-ohlc)

محدودیت‌های رسمی ممکن است تغییر کنند؛ هنگام پیاده‌سازی adapter در TB2-003.5B همین منابع باید دوباره
بررسی و تاریخ بررسی ثبت شود.

## قرارداد امنیت و گزارش

`scripts/probe_market_data_providers.py` فقط URLهای ثابت allowlist را فراخوانی می‌کند و URL دلخواه
نمی‌پذیرد. برای Nobitex فقط `from` و `to` بر اساس زمان اجرا ساخته می‌شوند. ابزار این موارد را ثبت
می‌کند:

- نتیجهٔ DNS بدون ذخیرهٔ IP؛ فقط تعداد آدرس‌های resolveشده و latency؛
- نتیجه و نسخهٔ TLS بدون certificate یا اطلاعات شبکهٔ محلی؛
- HTTP status، latency و اندازهٔ پاسخ؛
- معتبر بودن shape و تعداد کندل؛
- outcome پایدار مانند `geo_blocked`، `rate_limited` یا `invalid_response`.

body پاسخ، headerها، query string، IP و credential در گزارش ذخیره نمی‌شوند. statusهای ۴۰۳ و ۴۵۱
به `geo_blocked` نگاشت می‌شوند. فایل نمونه
`docs/v0.2/provider-probe-report.example.json` مصنوعی است و شاهد دسترسی واقعی محسوب نمی‌شود.

## اجرای سه نوبت از اینترنت مستقیم ایران

از ریشهٔ repository، بدون VPN، proxy یا tunnel و در سه زمان جدا اجرا کن. نام فایل‌های زیر نمونه‌اند؛
زمان واقعی اجرا را در نام جایگزین کن:

```bash
mkdir -p artifacts/provider-probes

python scripts/probe_market_data_providers.py \
  --environment-label iran-direct-run-1 \
  --output artifacts/provider-probes/iran-direct-run-1.json

python scripts/probe_market_data_providers.py \
  --environment-label iran-direct-run-2 \
  --output artifacts/provider-probes/iran-direct-run-2.json

python scripts/probe_market_data_providers.py \
  --environment-label iran-direct-run-3 \
  --output artifacts/provider-probes/iran-direct-run-3.json
```

اگر حتی یک provider شکست بخورد، گزارش همچنان نوشته می‌شود ولی exit code ابزار `2` است؛ این رفتار
برای مشاهدهٔ همهٔ شکست‌ها طبیعی است. فایل موجود overwrite نمی‌شود. مسیر
`artifacts/provider-probes/` عمداً در git ignore است تا شواهد محیطی تصادفی commit نشوند.

برای probe یک نامزد مشخص:

```bash
python scripts/probe_market_data_providers.py \
  --provider nobitex-public \
  --environment-label iran-direct-nobitex \
  --output artifacts/provider-probes/iran-direct-nobitex.json
```

## gate انتخاب برای TB2-003.5B

یک provider فقط وقتی وارد مرحلهٔ adapter می‌شود که همهٔ شرط‌های سخت زیر برقرار باشند:

1. هر سه اجرای مستقیم، DNS و TLS و payload معتبر داشته باشند؛ timeout تکراری، ۴۰۳، ۴۵۱ یا نیاز به
   VPN موجب رد provider برای v0.2 است.
2. endpoint OHLCV عمومی بدون کارت بانکی، حساب یا credential کار کند.
3. حداقل ۱h و ۱d مستقیم و ۱۵m/۴h مستقیم یا با resample کاملاً deterministic تأمین شوند.
4. pagination و عمق واقعی تاریخچه برای backtest قابل قبول باشد؛ هدف اولیه حداقل ۹۰ روز ۱h است.
5. کندل باز، timezone، ترتیب، volume، gap و rate-limit قرارداد مستند و fixture داشته باشند.
6. شرایط استفاده و مجوز استفاده از داده برای نوع انتشار پروژه بررسی و نتیجه ثبت شود.

بعد از عبور gate، امتیازدهی برای انتخاب دو adapter انجام می‌شود: پایداری دسترسی ۳۰، پوشش تاریخچه
۲۵، انطباق داده ۲۰، هزینه/rate-limit برابر ۱۵ و نگهداری/شرایط استفاده برابر ۱۰. provider داخلی و
بین‌المللی می‌توانند هم‌زمان انتخاب شوند؛ aggregator فقط fallback است و نباید بی‌صدا جای tape
صرافی را بگیرد.

## معیار خروج TB2-003.5A

- parser هر پنج payload با fixture آفلاین تست شود؛
- report schema و invariantهای success/failure بدون شبکه تست شوند؛
- سه گزارش واقعی مستقیم ایران تولید و outcome هر provider ثبت شود؛
- عمق تاریخچهٔ دو نامزد برتر با requestهای صفحه‌بندی‌شده به‌صورت دستی تأیید شود؛
- دو provider منتخب و علت رد بقیه در انتهای همین سند ثبت شوند.

تا قبل از تکمیل دو مورد آخر، TB2-003.5B شروع نمی‌شود.
