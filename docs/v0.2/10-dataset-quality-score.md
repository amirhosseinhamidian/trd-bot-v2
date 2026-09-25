# TB2-006 — امتیاز کیفیت نسخه‌دار و سیاست پذیرش Dataset

پروپوزال v0.2 نمایش Quality Score، gap، duplicate و اعتبار داده را الزام می‌کند، اما فرمول یا
آستانه مشخصی ارائه نمی‌دهد. این مرحله یک قرارداد deterministic و قابل ممیزی تعریف می‌کند؛ Score
جایگزین issueهای صریح نیست و اجازه نمی‌دهد کیفیت ضعیف یک مولفه با مولفه دیگر پنهان شود.

## قرارداد `quality-score-v1`

گزارش جدید دو مولفه صفر تا صد دارد:

| مولفه | تعریف |
| --- | --- |
| `coverage_percent` | برای Import API همان نسبت کندل‌های یکتای داخل بازه به slotهای مورد انتظار است؛ بدون requested range از فاصله نخستین تا آخرین open time استنتاج می‌شود. |
| `integrity_percent` | نسبت کندل‌هایی است که issue ساختاری timestampدار ندارند. empty/mixed-series کل مولفه را صفر می‌کند. duplicate، ترتیب نامعتبر، کندل باز، خارج از بازه و مرز زمانی نامعتبر روی کندل متاثر محاسبه می‌شوند. |

فرمول نسخه اول بدون وزن دلخواه است:

```text
score_percent = round((coverage_percent * integrity_percent) / 100, 2)
```

حاصل‌ضرب غیرجبرانی است: پوشش ۵۰٪ با یکپارچگی ۱۰۰٪ همچنان امتیاز ۵۰ دارد. gap و head/tail ناقص
فقط در coverage شمرده می‌شوند تا دوبار جریمه نشوند. مدل canonical `OHLCVCandle` قیمت‌های مثبت،
OHLC سازگار، volume غیرمنفی و timestamp معتبر را پیش از Quality Checker الزام می‌کند؛ خطای raw
file/provider که اصلاً به این مدل نرسد باید در لایه ingestion گزارش شود و امتیاز ساختگی نگیرد.

## قرارداد `strict-quality-v1`

Dataset تنها وقتی پذیرفته می‌شود که هم‌زمان:

1. `score_percent == 100.0` باشد؛
2. هیچ `DataQualityIssue` وجود نداشته باشد.

تمام issueهای فعلی مسدودکننده‌اند. Score برای توضیح شدت نقص است، نه threshold نرم؛ امتیاز بالا
نمی‌تواند gap، duplicate یا candle باز را قابل پذیرش کند. `ready_to_import` و `is_valid` از تصمیم
persisted policy استفاده می‌کنند.

## persistence و سازگاری

- Snapshotهای جدید `schema_version=3` دارند و report شامل `score` و `acceptance` است.
- schemaهای ۱ و ۲ و گزارش‌های قدیمی بدون score/policy همچنان parse می‌شوند؛ در این حالت UI شواهد
  ثبت‌نشده را صریح نشان می‌دهد و `is_valid` برای سازگاری از نبود issue استفاده می‌کند.
- گزارش کامل هر Import و Refresh داخل payload رکورد audit ذخیره می‌شود؛ migration ستونی لازم نیست.
- Refresh با محتوای یکسان Snapshot قبلی را تغییر نمی‌دهد، اما ارزیابی جدید خودش را در version
  history دارد. Refresh با محتوای تازه Snapshot schema ۳ مستقل می‌سازد.
- Preview، پاسخ خطای HTTP 422، Dataset Detail و version history نسخه فرمول، breakdown و policy را
  نمایش/برمی‌گردانند.

## شواهد پذیرش

1. داده کامل امتیاز ۱۰۰ و تصمیم accepted دارد؛
2. یک gap در سه slot امتیاز coverage و نهایی ۶۶٫۶۷ دارد و رد می‌شود؛
3. پوشش کامل همراه candle باز، coverage صد و integrity پنجاه دارد و رد می‌شود؛
4. head/tail ناقص با issueهای پایدار و score متناظر برمی‌گردد؛
5. payload قدیمی بدون score/policy خوانده می‌شود؛
6. Import موفق و Refresh بدون تغییر محتوا quality report مستقل در audit record دارند؛
7. failure کیفیت score و policy ردشده را در History و HTTP 422 حفظ می‌کند؛
8. UI امتیاز، دو مولفه، نسخه فرمول و نسخه policy را در Preview/Dataset/Version History نشان می‌دهد.
