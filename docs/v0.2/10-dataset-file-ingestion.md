# TB2-007 — ورود canonical فایل Dataset

## دامنه

این مرحله مسیر CSV محدود و client-side را با یک قرارداد واحد Backend برای CSV، JSON و
Parquet جایگزین می‌کند. خروجی هر format پیش از ذخیره به `OHLCVCandle` می‌رسد، با
`strict-quality-v1` ارزیابی می‌شود و سپس از همان `DatasetBuilder` مسیر provider عبور
می‌کند. این مسیر background job نیست؛ worker جدا به body درخواست دسترسی ندارد و انتقال آن
نیازمند staging محدود و checksum-bound با expiry/cleanup است. TB2-009 فقط Import دادهٔ Provider
را بدون ذخیره‌سازی بایت فایل به صف durable متصل می‌کند.

## قرارداد سه‌مرحله‌ای

1. `POST /api/v1/research/datasets/files/inspect` فایل را با limitهای قطعی باز می‌کند،
   ستون‌ها را برمی‌گرداند و mapping احتمالی را پیشنهاد می‌دهد.
2. `POST /api/v1/research/datasets/files/preview` فایل و mapping صریح را normalize می‌کند،
   coverage/quality را می‌سنجد و checksum محتوای canonical را برمی‌گرداند.
3. `POST /api/v1/research/datasets/files` همان عملیات را دوباره انجام می‌دهد و تنها وقتی
   checksum با Preview و policy کیفیت سازگار است Snapshot immutable می‌سازد.

هر درخواست multipart فقط یک فایل دارد و request ساختاریافته به‌صورت JSON در فیلد
`request` ارسال می‌شود. تغییر فایل، mapping، source، pair یا timeframe که محتوای canonical
را عوض کند با `preview_mismatch` و HTTP 409 رد می‌شود.

## محدودیت‌ها و خطاها

- حجم فایل: حداکثر ۱۰ MiB
- ردیف: حداکثر ۱۰۰٬۰۰۰
- ستون: حداکثر ۱۰۰
- cell: حداکثر ۱٬۰۰۰٬۰۰۰
- CSV و JSON فقط UTF-8؛ JSON فقط array of objects یا `{ "candles": [...] }`
- Parquet باید signature معتبر و metadata سازگار داشته باشد و پیش از decode با limitها
  سنجیده شود.
- تمام timestampها timezone-aware هستند؛ open روی grid UTC تایم‌فریم قرار می‌گیرد و
  `close_time` صریح باید دقیقاً یک interval پس از open باشد.
- نام فایل با basename امن می‌شود؛ مسیر client نگهداری نمی‌شود.

خطاهای قابل انتظار دارای `detail.code` پایدارند. فایل بزرگ HTTP 413، format ناشناخته
HTTP 415، Preview منقضی HTTP 409 و سایر خطاهای container/mapping/row/quality HTTP 422
دارند. فایل خام persist نمی‌شود.

## provenance و سازگاری

Snapshot فایل `kind=manual_upload` دارد و filename امن، format، SHA-256 بایت فایل و
mapping نهایی را ثبت می‌کند. Snapshotهای قدیمی `manual_upload` که این metadata را ندارند
همچنان قابل خواندن‌اند. endpoint قدیمی JSON candle برای clientهای موجود حذف نشده است؛ UI
جدید فقط مسیر multipart سمت Backend را استفاده می‌کند.

## پذیرش

- fixture منطقی یکسان در CSV/JSON/Parquet checksum و Quality Report یکسان می‌دهد.
- mapping ستون نامتعارف به خروجی canonical درست می‌رسد.
- فایل خراب، encoding نامعتبر، duplicate column، limit و row نامعتبر قبل از persistence
  رد می‌شوند.
- gap، open candle، timestamp خارج از grid و close-time ناسازگار Import نمی‌شوند.
- تغییر پس از Preview هیچ Snapshotی ذخیره نمی‌کند.
- UI inspect، mapping، Preview، quality rejection و commit موفق را نمایش می‌دهد.

این سند نتیجه اجرای test/build را ادعا نمی‌کند؛ شواهد نهایی روی SHA کاربر در TB2-024 ثبت
می‌شود.
