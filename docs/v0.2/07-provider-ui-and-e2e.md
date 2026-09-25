# TB2-003.5C — رابط Provider و پذیرش سرتاسری

این مرحله قابلیت‌های عملیاتی adapterهای عمومی را از قرارداد backend تا صفحهٔ Connection ادامه
می‌دهد. هدف این است که کاربر پیش از ساخت Connection بداند کدام provider بدون VPN کار می‌کند،
بازار پیش‌فرض چیست و آیا عمق تاریخی محدود است.

## قرارداد metadata

خروجی `GET /api/v1/market-data/providers` علاوه بر شناسه، timeframe و market type این فیلدها را
برمی‌گرداند:

| فیلد | معنا |
| --- | --- |
| `default_pair` | بازار اولیهٔ فرم import، شامل base/quote و market type |
| `access_mode` | `direct` برای مسیر مستقیم یا `vpn_required` برای مسیر وابسته به VPN |
| `max_closed_candles` | حداکثر کندل بستهٔ قابل درخواست؛ `null` یعنی adapter بازه را صفحه‌بندی می‌کند |

این metadata فقط راهنمای استقرار فعلی است و تضمین همیشگی دسترسی شبکه نیست. health check هر
Connection همچنان مرجع وضعیت همان محیط اجرا است.

## رفتار UI

- کارت هر provider مسیر اتصال، بازار پیش‌فرض و پوشش تاریخی را نشان می‌دهد.
- فرم ساخت Connection در صورت وجود، نخستین provider با مسیر `direct` را انتخاب می‌کند؛ در کاتالوگ
  فعلی این provider، Nobitex است.
- فرم Historical Import از `default_pair` همان provider مقداردهی می‌شود.
- برای مسیر `vpn_required` هشدار روشن نمایش داده می‌شود.
- فرم Kraken بازه‌ای را که شروع آن قدیمی‌تر از پنجرهٔ ۷۱۹ کندل بسته باشد، پیش از request رد می‌کند.
  backend نیز همان محدودیت را مستقل اعمال و با HTTP 400 گزارش می‌کند؛ بنابراین UI مرز امنیتی نیست.

## پذیرش خودکار آفلاین

`tests/test_market_data_provider_e2e.py` مسیر واقعی زیر را با `TestClient`، repositoryهای in-memory
و transport تزریق‌شده اجرا می‌کند:

1. دریافت provider metadata؛
2. ساخت Connection مربوط به Nobitex؛
3. health check و enable؛
4. preview بازهٔ تاریخی با parser واقعی Nobitex؛
5. import Dataset و بررسی provenance؛
6. بررسی import history؛
7. رد بازهٔ قدیمی Kraken با HTTP 400، پیش از fetch تاریخی.

هیچ request شبکه‌ای در این تست انجام نمی‌شود. آزمون‌های component نیز انتخاب پیش‌فرض مستقیم،
نمایش محدودیت‌ها، مقداردهی بازار Kraken و غیرفعال‌شدن Preview برای بازهٔ نامعتبر را پوشش می‌دهند.

## پذیرش دستی محیط واقعی

1. بدون VPN یک Connection از `nobitex-public` بساز، Test و Enable کن و یک بازهٔ کوچک گذشته را
   Preview و Import کن.
2. Dataset Detail را باز کن و `provider_id`، `connection_id`، requested range، تعداد کندل و quality
   report را کنترل کن.
3. با VPN فعال همین lifecycle را برای `kraken-public` و `BTC/USD` در بازهٔ اخیر انجام بده.
4. شروع Kraken را قدیمی‌تر از ۷۱۹ timeframe انتخاب کن و بررسی کن UI درخواست را غیرفعال می‌کند.
5. همین درخواست قدیمی را مستقیماً به API بفرست و HTTP 400 با پیام retention window بگیر.
6. VPN را قطع کن، Test را تکرار کن و مطمئن شو وضعیت unhealthy بدون افشای URL حساس یا credential
   ذخیره می‌شود.

نتیجهٔ smoke test زنده باید همراه SHA، زمان، environment label و خروجی sanitize‌شده ثبت شود؛ نتیجهٔ
probe مرحلهٔ 003.5A جای پذیرش import واقعی را نمی‌گیرد.
