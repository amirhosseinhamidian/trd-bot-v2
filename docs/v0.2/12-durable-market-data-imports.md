# TB2-009 — اجرای بادوام Import دادهٔ بازار

## دامنه این مرحله

Preview دادهٔ Provider عمداً synchronous باقی می‌ماند، چون read-only و بدون side effect است.
ساخت Dataset و Refresh از مسیرهای جدید زیر با پاسخ `202 Accepted` در صف ثبت می‌شوند:

- `POST /api/v1/market-data/connections/{connection_id}/dataset-jobs`
- `POST /api/v1/market-data/connections/{connection_id}/imports/{import_id}/refresh-job`

مسیرهای synchronous قبلی فعلاً برای سازگاری clientهای موجود حفظ شده‌اند. cutover رابط کاربری
و حذف مسیر قدیمی باید پس از rollout worker انجام شود تا deploy بین نسخه‌ای شکسته نشود.

## payload و idempotency

فقط `HistoricalDatasetJobPayload` نسخهٔ یک پذیرفته می‌شود. Import شامل identity، بازه، pair،
timeframe و checksum همان Preview است؛ Refresh فقط شناسه آخرین Import موفق را نگه می‌دارد و
هنگام اجرا وضعیت lineage را دوباره بررسی می‌کند.

کل payload canonical hash می‌شود. enqueue تکراری همان request همان job را برمی‌گرداند. برای
هر attempt یک `import_id` قطعی از `job_id` و `attempt_count` ساخته می‌شود؛ بنابراین retry دستی
audit قبلی را بازنویسی نمی‌کند. Provider نیز retry محدود داخلی خود را پیش از fail شدن attempt
اعمال می‌کند، پس jobهای Import با budget اولیه یک attempt ساخته می‌شوند.
enqueue دوبارهٔ job شکست‌خورده آن را خودکار اجرا نمی‌کند؛ retry صریح از
`POST /api/v1/jobs/{job_id}/retry` انجام می‌شود.

## اجرا و نتیجه

handler allowlisted با Session مستقل worker، connection و provider را resolve می‌کند، داده را
دوباره fetch و validate می‌کند و Dataset/Import record را اتمیک commit می‌کند. progress در
نقاط ۱۰، ۷۵ و ۹۵ درصد persist می‌شود. در موفقیت، `result_reference` شناسه Import audit است؛
در failure، متن provider پیش از ذخیره در history redacted می‌شود.

Cancel تا پیش از commit cooperative است. اگر cancel پس از fetch مشاهده شود، Dataset و audit
ساخته نمی‌شوند. crash یا lease منقضی از قواعد reclaim صف TB2-008 پیروی می‌کند.

## مرز فایل‌های آپلودی

CSV/JSON/Parquet در این patch وارد worker نمی‌شوند، چون فایل خام طبق قرارداد TB2-007 ذخیره
نمی‌شود و process worker به body درخواست دسترسی ندارد. انتقال امن این مسیر نیازمند قرارداد
staging محدود، checksum-bound، expiry و cleanup است و نباید با قرار دادن بایت فایل در payload
JSON صف شبیه‌سازی شود.

## اجرای عملیاتی

پس از migration TB2-008، API و worker باید هم‌زمان deploy شوند:

```bash
python scripts/run_background_worker.py
```

این سند نتیجهٔ test یا اجرای واقعی Provider را ادعا نمی‌کند؛ شواهد CI و probe روی SHA کاربر
ثبت می‌شوند.
