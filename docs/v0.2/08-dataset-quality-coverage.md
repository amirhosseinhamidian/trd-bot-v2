# TB2-004 — پوشش Dataset و ثبات Preview

این مرحله دو ریسک `R-02` و `R-03` مبنای نسخه دوم را می‌بندد: کامل‌نبودن ابتدا یا انتهای
بازه دیگر بدون هشدار معتبر نیست و محتوای ذخیره‌شده باید دقیقاً همان محتوایی باشد که کاربر در
Preview پذیرفته است.

## قرارداد بازه و پوشش

- بازه همچنان نیمه‌باز `[start_time, end_time)` و بر اساس `open_time` کندل است.
- مرزهای مورد انتظار روی grid تایم‌فریم در UTC محاسبه می‌شوند. اگر زمان ورودی بین دو مرز باشد،
  نخستین مرز بعدی مبنا است؛ بنابراین ورودی `10:30–12:30` برای تایم‌فریم یک‌ساعته کندل‌های
  `11:00` و `12:00` را انتظار دارد.
- `DataQualityReport.coverage` این شواهد را ثبت می‌کند:

| فیلد | معنا |
| --- | --- |
| `expected_candles` | تعداد کندل‌های مورد انتظار روی grid UTC |
| `received_candles` | تعداد open time یکتای معتبر داخل بازه |
| `missing_candles` | اختلاف expected و received |
| `coverage_percent` | درصد received نسبت به expected با دو رقم اعشار |
| `complete` | فقط وقتی expected مثبت و missing صفر است |
| `expected_*` / `actual_*` | مرزهای زمانی لازم برای audit و UI |

نبود کندل در ابتدای بازه `incomplete_start`، نبود کندل در انتها `incomplete_end` و gap داخلی
`missing_candle` است. کندل خارج از بازه و کندل ناسازگار با مرز UTC نیز مستقل گزارش می‌شوند. هر یک
از این موارد `ready_to_import=false` ایجاد می‌کند.

گزارش‌های قدیمی بدون coverage همچنان با `coverage=null` خوانده می‌شوند. فیلد داخل `payload_json`
ذخیره می‌شود و migration جدولی لازم ندارد. schema نسخه ۲ قرارداد coverage را معرفی کرد؛ فرمول
امتیاز و policy پذیرش در schema نسخه ۳ و سند TB2-006 نسخه‌گذاری شده‌اند.

## قرارداد Preview و Import

Preview علاوه بر گزارش کیفیت یک `preview_checksum` محتوایی برمی‌گرداند. checksum از candleهای
canonical و بدون `received_at` ساخته می‌شود؛ بنابراین تفاوت زمان دریافت هویت محتوا را تغییر نمی‌دهد.

درخواست Import باید همان checksum را در `preview_checksum` ارسال کند. Backend داده را دوباره می‌گیرد
و پیش از ذخیره مقایسه می‌کند:

- checksum برابر: کنترل کیفیت و ساخت snapshot ادامه می‌یابد؛
- checksum متفاوت: HTTP 409، بدون Dataset جدید، و history ناموفق با کد `preview_mismatch`؛
- Refresh به Preview کاربر وابسته نیست و مثل قبل نسخه تازه را از آخرین داده می‌سازد، اما coverage
  کامل را مستقل کنترل می‌کند.

UI checksum و آمار پوشش را در Preview نشان می‌دهد، checksum را هنگام Import خودکار ارسال می‌کند و
برای 409 تغییر داده از کاربر می‌خواهد Preview تازه بگیرد. Dataset Detail نیز گزارش پوشش persisted را
نمایش می‌دهد.

## شواهد پذیرش

تست‌های این مرحله باید این سناریوها را بدون شبکه زنده پوشش دهند:

1. بازه کامل با coverage صددرصد؛
2. ورودی بین مرزهای timeframe و محاسبه صحیح grid UTC؛
3. head و tail ناقص با issue مستقل؛
4. gap داخلی و رد Import با HTTP 422؛
5. تغییر candle بعد از Preview و رد Import با HTTP 409؛
6. ثبت `preview_mismatch` در import history؛
7. persistence و نمایش coverage در Dataset Detail؛
8. سازگاری Dataset قدیمی با quality report یا coverage ثبت‌نشده.
9. رد کندل خارج از بازهٔ نیمه‌باز و open time خارج از grid تایم‌فریم.

این مرحله صحت شبکه زنده Provider را ادعا نمی‌کند؛ پذیرش زنده همچنان باید با SHA نهایی و artifact
sanitize‌شده ثبت شود.
