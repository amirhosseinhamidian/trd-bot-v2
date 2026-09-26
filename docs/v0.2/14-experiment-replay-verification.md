# TB2-011 — تأیید بازاجرای Experiment

## هدف و API

مسیر زیر یک Experiment ذخیره‌شده را به‌صورت read-only دوباره اجرا می‌کند:

```text
POST /api/v1/research/experiments/{experiment_id}/replay-verification
```

این درخواست رکورد Experiment، Dataset، Strategy یا نتیجه را تغییر نمی‌دهد و replay تازه را نیز
به‌عنوان Experiment جدید ذخیره نمی‌کند. خروجی فقط شاهد همان بررسی با زمان اجرا، وضعیت، کد پایدار،
fingerprintها، checksum نتیجه‌ها و نام بخش‌های متفاوت است.

## ورودی دقیق replay

Verifier از داده‌های زیر استفاده می‌کند:

- `DatasetSnapshot` immutable با همان `dataset_id`؛
- تعریف Registry با همان `strategy_name` و `strategy_version`؛
- تطابق دقیق `behavior_fingerprint` ثبت‌شده و Registry؛
- پارامترهای Strategy بر اساس schema همان نسخه؛
- `horizon_candles` رکورد؛
- `backtest_config` ذخیره‌شده داخل `ResearchPipelineResult`.

checksum نتیجه از JSON canonical کل `ResearchPipelineResult` محاسبه می‌شود، نه فقط metricهای
خلاصه. در اختلاف، کلیدهای سطح اول متفاوت مانند `signals`، `performance_report` یا
`benchmark_result` گزارش می‌شوند و payload حجیم دوباره به client فرستاده نمی‌شود.

## semantics نتیجه

| status | نمونه کد | معنی |
| --- | --- | --- |
| `verified` | `verified` | checksum و مدل کامل نتیجه بازاجرا دقیقاً برابر نتیجه ذخیره‌شده است. |
| `mismatch` | `dataset_integrity_mismatch`, `strategy_fingerprint_mismatch`, `result_mismatch` | محتوای Dataset، هویت رفتار یا خروجی با تاریخچه یکسان نیست. |
| `unverifiable` | `legacy_fingerprint_missing`, `dataset_not_found`, `strategy_version_not_found`, `invalid_strategy_parameters`, `replay_failed` | شاهد لازم موجود یا معتبر نیست؛ سیستم از حدس‌زدن و اعلام موفقیت خودداری می‌کند. |

Experimentهای پیش از TB2-010 که fingerprint ندارند عمداً replay-verified نمی‌شوند. fingerprint
فعلی به آن‌ها نسبت داده یا backfill نمی‌شود. همین قاعده برای Dataset حذف‌شده و نسخه‌ای که دیگر
کد اجرایی آن در Registry نیست اعمال می‌شود.

## رابط کاربری و عملیات

صفحه جزئیات Experiment پنل «تأیید بازاجرا» دارد. بررسی فقط با کلیک کاربر اجرا می‌شود تا بار CPU
در render عادی صفحه ایجاد نشود. UI وضعیت و دلیل، دو checksum، دو fingerprint و بخش‌های متفاوت
را نمایش می‌دهد. شکست شبکه با نتیجه mismatch اشتباه گرفته نمی‌شود.

این مرحله migration ندارد و هیچ جدول audit جدیدی نمی‌سازد. persist کردن دوره‌ای شواهد replay،
در صورت نیاز release، باید همراه retention و job policy جداگانه طراحی شود.
