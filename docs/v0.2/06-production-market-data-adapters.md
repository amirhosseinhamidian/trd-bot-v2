# TB2-003.5B — adapterهای عملیاتی Nobitex و Kraken

این مرحله دو منبع عمومی read-only را به `MarketDataProviderCatalog` اضافه می‌کند. هیچ مسیر معامله،
credential یا URL قابل‌کنترل توسط کاربر اضافه نشده است.

## قرارداد مشترک

- خروجی `OHLCVCandle` با Decimal، زمان UTC و ترتیب صعودی است.
- بازهٔ درخواست نیمه‌باز `[start_time, end_time)` است.
- کندلی که `close_time` آن پس از زمان مشاهده باشد وارد Dataset نمی‌شود.
- timeout، retry، exponential backoff، `Retry-After` محدود و error mapping همان قرارداد Binance را
  استفاده می‌کنند.
- health check خود endpoint OHLC عمومی را می‌سنجد تا موفقیت شبکه بدون payload قابل‌استفاده healthy
  ثبت نشود.
- تست‌های adapter فقط fixture و fetcher تزریق‌شده دارند و به اینترنت CI وابسته نیستند.

## Nobitex

- host ثابت: `apiv2.nobitex.ir`؛ مسیر `/market/udf/history`؛
- timeframeهای `15m/1h/4h/1d` به `15/60/240/D` نگاشت می‌شوند؛
- ستون‌های UDF یعنی `t/o/h/l/c/v` باید همگی لیست و هم‌طول باشند؛
- status برابر `no_data` نتیجهٔ خالی معتبر است؛ status دیگر به‌جز `ok` خطای payload است؛
- صفحه‌ها حداکثر ۵۰۰ ردیف دارند، open time تکراری deduplicate می‌شود، بین صفحه‌های کامل فاصلهٔ
  پیش‌فرض یک ثانیه وجود دارد و بودجهٔ پیش‌فرض ۱۰۰ صفحه است.

## Kraken

- host ثابت: `api.kraken.com`؛ مسیر `/0/public/OHLC`؛
- timeframeها به intervalهای رسمی `15/60/240/1440` دقیقه نگاشت می‌شوند؛
- aliasهای `BTC -> XBT` و `DOGE -> XDG` برای request اعمال می‌شوند؛
- envelope باید error خالی و دقیقاً یک series غیر از کلید `last` داشته باشد؛
- آخرین کندل جاری بر اساس `close_time` حذف می‌شود؛
- API فقط ۷۲۰ entry اخیر را می‌دهد. start قدیمی‌تر پیش از تماس شبکه رد می‌شود تا import ناقص
  بی‌صدا ساخته نشود.

## پذیرش محلی

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest tests/test_nobitex_market_data_provider.py -q
python -m pytest tests/test_kraken_market_data_provider.py -q
python -m pytest tests/test_market_data_provider.py \
  tests/test_market_data_provider_reliability.py \
  tests/test_market_data_connections.py -q
python -m pytest -m "not integration"
```

Smoke test شبکه جزو CI نیست. Nobitex باید بدون VPN و Kraken روی مسیر VPN محیط اجرای واقعی تست شود.
پذیرش Kraken فقط برای پنجرهٔ اخیر است و نباید به‌عنوان پوشش ۹۰ روز ۱h معرفی شود.

نمایش مسیر اتصال، بازار پیش‌فرض، محدودیت عمق و سناریوی پذیرش API/UI در
`07-provider-ui-and-e2e.md` مستند شده است.
