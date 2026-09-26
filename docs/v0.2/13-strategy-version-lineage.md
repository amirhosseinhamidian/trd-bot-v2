# TB2-010 — هویت نسخه و lineage استراتژی

## قرارداد نسخهٔ منتشرشده

هویت اجرایی Strategy فقط رشتهٔ `version` نیست. هر تعریف Registry این اجزا را منتشر می‌کند:

- `name` و `version`؛
- schema canonical پارامترها شامل نوع، default و boundها؛
- `lifecycle_status` و نسخهٔ predecessor در صورت وجود؛
- `behavior_fingerprint` با قالب `sha256:<64-hex>`.

fingerprint از identity، schema پارامتر و یک قرارداد صریح implementation محاسبه می‌شود. تغییر
الگوریتم تولید سیگنال، منبع قیمت، semantics crossing یا schema پارامتر باید قرارداد تازه و
version تازه بسازد. ویرایش متن نمایشی یا deprecated کردن نسخه هویت رفتار را تغییر نمی‌دهد.

Registry در v0.2 code-owned و read-only است. این انتخاب امکان اجرای factory دقیق را حفظ می‌کند
و از این ادعا که یک ردیف DB به‌تنهایی کد قدیمی را بازسازی می‌کند جلوگیری می‌کند.

## API و پیمایش

علاوه بر catalog موجود، دو lookup صریح اضافه شده‌اند:

- `GET /api/v1/research/strategies/{name}/versions`
- `GET /api/v1/research/strategies/{name}/versions/{version}`

lookup نسخهٔ ناشناخته fallback به latest ندارد و `404` می‌دهد. صفحهٔ detail نسخه، fingerprint
و آخرین Experimentهای فیلترشده با همان `strategy_name` و `strategy_version` را نمایش می‌دهد و
به جزئیات هر Experiment لینک مستقیم دارد.

## snapshot در Experiment و سازگاری

`ExperimentBuilder` تعریف دقیق Registry را resolve می‌کند و fingerprint آن را هم در شناسهٔ
deterministic و هم در payload immutable Experiment قرار می‌دهد. بنابراین تغییر پنهانی رفتار
زیر همان name/version با هویت قبلی یکی تلقی نمی‌شود.

رکوردهای قبل از TB2-010 فیلد fingerprint ندارند. مدل آن‌ها را با مقدار `null` می‌خواند و UI
آن‌ها را legacy نشان می‌دهد؛ fingerprint فعلی Registry روی تاریخچه قدیمی backfill نمی‌شود، چون
اثباتی وجود ندارد که آن رکورد واقعاً با همین bytes/behavior ساخته شده باشد. این patch migration
دیتابیس ندارد، چون Experiment کامل در `payload_json` نگهداری می‌شود.

## مرز مرحله

این مرحله identity و navigation را می‌بندد. TB2-011 باید replay کنترل‌شده را اضافه کند: Dataset
immutable را بارگذاری کند، fingerprint ثبت‌شده را با Registry تطبیق دهد، پارامترها را بازسازی
کند و نتیجهٔ تازه را با نتیجهٔ ذخیره‌شده مقایسه کند. mismatch باید fail-closed باشد و نتیجهٔ
قدیمی را بازنویسی نکند.
