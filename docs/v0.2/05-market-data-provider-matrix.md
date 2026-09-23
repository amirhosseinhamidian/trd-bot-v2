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
| `bitstamp-public` | tape صرافی، OHLC عمومی بدون credential | `limit` بین ۱ تا ۱۰۰۰؛ stepهای ۱۵m/۱h/۴h/۱d پشتیبانی می‌شوند. | پارامتر `exclude_current_candle=true` کندل باز را حذف می‌کند؛ volume مربوط به همان بازار است. | BTC/USD، دو کندل ۱h بسته | فعلاً deferred؛ مزیت کافی نسبت به دو انتخاب ندارد |
| `kraken-public` | tape صرافی، OHLC عمومی بدون credential | حداکثر ۷۲۰ کندل اخیر و دادهٔ قدیمی‌تر با `since` قابل دریافت نیست؛ timeframeهای لازم موجودند. | آخرین ردیف همیشه کندل جاری و نهایی‌نشده است؛ adapter آن را حذف می‌کند. | XBT/USD، ۱h | adapter دوم؛ نیازمند VPN و محدود به recent window |
| `coinbase-exchange-public` | tape صرافی، candles عمومی | حداکثر ۳۰۰ کندل در هر درخواست؛ ۱۵m/۱h/۱d موجود است اما ۴h مستقیم نیست و باید با قرارداد روشن resample شود. | پاسخ `[time, low, high, open, close, volume]` است؛ مرتب‌سازی و بسته‌بودن آخرین bucket باید در adapter قطعی شود. | BTC/USD، ۱h | deferred؛ وابستگی VPN و نبود ۴h مستقیم |
| `nobitex-public` | tape صرافی داخلی، OHLC عمومی و بدون token روی host رسمی `apiv2.nobitex.ir` | حداکثر ۵۰۰ کندل در هر درخواست، pagination با `page`، دادهٔ دقیقه‌ای از آغاز ۱۴۰۱ و سقف ۶۰ درخواست در دقیقه طبق مستند رسمی. | پاسخ TradingView UDF با ستون‌های `t/o/h/l/c/v`؛ adapter ستون‌ها را هم‌طول می‌خواهد و کندل باز را حذف می‌کند. | BTC/USDT، سه ساعت اخیر در ۱h | adapter اصلی مستقیم |
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

## شواهد دسترسی و تصمیم انتخاب

در ۲۳ سپتامبر ۲۰۲۶ اجرای اتصال مستقیم ایران برای Nobitex پس از اصلاح host رسمی و برای
CoinPaprika موفق بود؛ Bitstamp و Kraken پاسخ ۴۰۳ و Coinbase خطای TLS داشتند. اجرای دوم که در
فایل با label قدیمی `iran-direct-run-2` ذخیره شده، در واقع با VPN انجام شده و نباید شاهد اتصال
مستقیم تلقی شود. هر پنج نامزد در مسیر VPN payload معتبر برگرداندند.

با تصمیم عملیاتی صاحب پروژه، VPN برای منبع بین‌المللی قابل قبول است. بنابراین:

- `nobitex-public` adapter اصلی مستقیم برای تاریخچهٔ موردنیاز پژوهش است؛
- `kraken-public` adapter دوم و وابسته به VPN است و به علت سقف رسمی ۷۲۰ entry، fallback تاریخچهٔ
  بلندمدت نیست؛
- `coinpaprika-free` فقط connectivity/validation کمکی است و به catalog import اضافه نمی‌شود؛
- Bitstamp و Coinbase در این مرحله adapter نمی‌شوند تا پیچیدگی بدون مزیت عملی اضافه نشود؛
- Binance فعلی برای سازگاری باقی می‌ماند ولی انتخاب اصلی محیط ایران نیست.

این تصمیم، الزام سه اجرای مستقیم قبلی را با یک تصمیم ثبت‌شدهٔ عملیاتی جایگزین می‌کند؛ گزارش VPN
عمداً direct معرفی نمی‌شود. اگر اجرای خودکار روی server انجام شود، همان server باید مسیر خروجی VPN
یا proxy پایدار داشته باشد؛ VPN لپ‌تاپ به‌تنهایی دسترسی server را تضمین نمی‌کند.

## gate انتخاب برای TB2-003.5B

یک provider فقط وقتی وارد مرحلهٔ adapter می‌شود که همهٔ شرط‌های سخت زیر برقرار باشند:

1. provider مستقیم باید DNS، TLS و payload معتبر داشته باشد. provider وابسته به VPN فقط با ثبت
   صریح این وابستگی و فراهم‌بودن همان مسیر در محیط اجرا پذیرفته می‌شود.
2. endpoint OHLCV عمومی بدون کارت بانکی، حساب یا credential کار کند.
3. حداقل ۱h و ۱d مستقیم و ۱۵m/۴h مستقیم یا با resample کاملاً deterministic تأمین شوند.
4. provider اصلی باید pagination و حداقل ۹۰ روز دادهٔ ۱h داشته باشد. provider دوم می‌تواند پنجرهٔ
   کوتاه‌تری داشته باشد، به شرط اینکه محدودیت را صریح رد کند و دادهٔ ناقص را کامل جلوه ندهد.
5. کندل باز، timezone، ترتیب، volume، gap و rate-limit قرارداد مستند و fixture داشته باشند.
6. شرایط استفاده و مجوز استفاده از داده برای نوع انتشار پروژه بررسی و نتیجه ثبت شود.

بعد از عبور gate، امتیازدهی برای انتخاب دو adapter انجام می‌شود: پایداری دسترسی ۳۰، پوشش تاریخچه
۲۵، انطباق داده ۲۰، هزینه/rate-limit برابر ۱۵ و نگهداری/شرایط استفاده برابر ۱۰. provider داخلی و
بین‌المللی می‌توانند هم‌زمان انتخاب شوند؛ aggregator فقط fallback است و نباید بی‌صدا جای tape
صرافی را بگیرد.

## معیار خروج TB2-003.5A

- parser هر پنج payload با fixture آفلاین تست شود؛
- report schema و invariantهای success/failure بدون شبکه تست شوند؛
- گزارش مستقیم و گزارش VPN با environment واقعی و بدون جابه‌جایی label تفسیر شوند؛
- عمق تاریخچه و محدودیت رسمی دو نامزد منتخب در adapter به‌صورت enforceشده ثبت شود؛
- دو provider منتخب و علت رد یا تعویق بقیه در همین سند ثبت شوند.

انتخاب ثبت شد: Nobitex اصلی و Kraken ثانویهٔ وابسته به VPN. پذیرش نهایی به اجرای تست‌ها و smoke
test روی محیط واقعی صاحب پروژه وابسته است.
