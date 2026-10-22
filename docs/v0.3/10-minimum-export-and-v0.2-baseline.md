# P1-06 — Minimum Export و v0.2 Release Baseline

وضعیت: **تکمیل‌شده در کد؛ آمادهٔ پذیرش CI**

تاریخ تصمیم: `2026-10-11`

این مرحله بدهی `V3-D06` را با یک تصمیم دامنه‌ای می‌بندد: برای شروع قابلیت‌های تازهٔ v0.3، حداقل
Export پذیرفته‌شدهٔ نسخهٔ دوم همان گزارش قطعی Experiment در قالب CSV است. این مرحله format یا
resource تازه‌ای اضافه نمی‌کند؛ قرارداد موجود را نسخه‌دار، امن و قابل جلوگیری از drift می‌کند.

## قرارداد فریز‌شده

| مورد | baseline پذیرفته‌شده |
| --- | --- |
| resource | یک `ResearchExperiment` ذخیره‌شده |
| policy | یک Acceptance Policy Preset دارای ID و version مشخص |
| endpoint | `GET /api/v1/research/experiments/{experiment_id}/report/presets/{preset_id}/export.csv` |
| schema | `experiment-report-csv-v1` |
| ستون‌ها | `section,metric,value` |
| ترتیب | قطعی و تحت golden checksum |
| interpretation | فقط `historical_research_only` |
| cache | `Cache-Control: no-store` |
| download hardening | `Content-Disposition: attachment` و `X-Content-Type-Options: nosniff` |

ردیف نخست داده پس از header، شناسهٔ schema را ثبت می‌کند. گزارش شامل lineage حداقلی Dataset،
Strategy name/version، Experiment، policy preset، پارامترها، performance، benchmark و acceptance
checks است. timestamp تولید export اضافه نشده تا خروجی یک گزارش یکسان byte-for-byte قطعی بماند.

مقدارهای رشته‌ای که ممکن است توسط spreadsheet به‌عنوان formula اجرا شوند با apostrophe خنثی
می‌شوند. مقدارهای typed مانند Decimal، integer، boolean، enum و datetime بدون تبدیل ناامن حفظ
می‌شوند؛ بنابراین اعداد منفی metric همچنان عدد خوانا باقی می‌مانند.

## موارد عمداً deferred

موارد زیر بخشی از minimum baseline نیستند و فقط همراه use case و acceptance مستقل در فاز مربوط
اضافه می‌شوند:

- فایل JSON قابل دانلود؛ پاسخ JSON گزارش برای API با export artifact یکسان نیست؛
- PDF report؛
- Dataset export در CSV/JSON/Parquet؛
- export مستقل Walk-Forward، Optimization، Candidate، Risk، Portfolio یا Position؛
- bulk export، archive چندفایلی، export background job و storage artifact؛
- Advanced Report Builder، template، notes و tags.

این defer به معنی حذف از roadmap نیست؛ فقط مانع گسترش زودهنگام دامنه پیش از P2 می‌شود.

## baseline نسخهٔ دوم

مبنای محصول همچنان `0.2.0` است و تا release cut نسخهٔ v0.3 تغییر نمی‌کند. قابلیت‌های Dataset
immutable، Strategy/Experiment، Walk-Forward، Optimization، Candidate/Risk، Paper/Shadow،
Portfolio analytics، Monitoring و UI فریز‌شدهٔ Nexora پایهٔ توسعه باقی می‌مانند. P1 فقط بدهی‌های
ورودی به v0.3 را می‌بندد و مجوز live order، credential معامله یا portfolio واقعی نمی‌دهد.

## Storage و migration

schema دیتابیس و artifact storage تغییر نمی‌کنند. CSV در لحظه از رکوردهای immutable موجود ساخته
می‌شود و نتیجهٔ export جداگانه persist نمی‌شود.

## معیار خروج P1-06

- [x] تنها export عمومی baseline همان CSV نسخه‌دار Experiment است.
- [x] schema ID، header و ترتیب کامل خروجی تحت تست deterministic/golden هستند.
- [x] lineage، performance، benchmark، policy و acceptance checks در CSV باقی مانده‌اند.
- [x] stringهای مستعد spreadsheet formula خنثی می‌شوند و metricهای عددی خراب نمی‌شوند.
- [x] هدرهای no-store، attachment و nosniff تست شده‌اند.
- [x] client frontend مسیر و MIME type صحیح را مصرف می‌کند.
- [x] فرمت‌ها و resourceهای deferred صریح ثبت شده‌اند.
- [x] migration دیتابیس لازم نیست.

مرحلهٔ بعد `P1-07` است: پذیرش نهایی Phase 1، اجرای PostgreSQL/migration/recovery gate و ثبت evidence
روی SHA مرجع مالک مخزن.
