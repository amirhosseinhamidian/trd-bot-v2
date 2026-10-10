# P1-01 — Secure Dataset Staging و Durable Import

وضعیت: **تکمیل‌شده در کد؛ آمادهٔ CI و migration روی PostgreSQL مرجع**

تاریخ تصمیم: `2026-10-10`

این مرحله بدهی `V3-D01` را می‌بندد. Commit فایل Dataset دیگر rowها را داخل request پردازش و
Snapshot را هم‌زمان ذخیره نمی‌کند. API فقط upload محدودشده را اعتبارسنجی اولیه می‌کند، آن را همراه
با intent تأییدشده در storage موقت PostgreSQL قرار می‌دهد و یک `BackgroundJob` durable می‌سازد.

## قرارداد اجرا

1. `inspect` و `preview` مانند قبل synchronous و bounded باقی می‌مانند.
2. `POST /api/v1/research/datasets/files` نام فایل، extension، اندازه و checksum را بدون parse کردن
   rowها بررسی می‌کند.
3. stage و job در یک transaction ثبت می‌شوند؛ شکست هرکدام کل enqueue را rollback می‌کند.
4. پاسخ API برابر `202 Accepted` و بدنهٔ آن `BackgroundJobSummary` است.
5. worker با `stage_id` و checksum موجود در payload، stage را دوباره می‌خواند و preview checksum،
   schema، کیفیت و محتوای فایل را دوباره اعتبارسنجی می‌کند.
6. پس از موفقیت، cancellation یا failure دائمی، byteهای stage حذف می‌شوند. stage منقضی نیز در
   زمان enqueue بعدی یا هنگام اجرای job حذف می‌شود.

## مرز امنیت و ماندگاری

| کنترل | قرارداد |
| --- | --- |
| محل موقت | جدول خصوصی `dataset_file_stages` در PostgreSQL؛ بدون مسیر فایل عمومی |
| حداکثر اندازه | `10 MiB` |
| نام فایل | فقط basename امن، حداکثر 255 کاراکتر |
| اتصال محتوا | SHA-256 در stage، payload و idempotency intent |
| TTL | 24 ساعت |
| payload صف | فقط `stage_id` و `file_checksum`؛ بدون byteهای فایل |
| retry | حداکثر 3 attempt با lease پنج‌دقیقه‌ای |
| خطای integrity | fail-closed و بدون نمایش محتوای فایل در پیام خطا |

فایل و intent کاربر با هم ذخیره می‌شوند تا worker دقیقاً همان محتوایی را پردازش کند که برای آن
preview تأیید شده است. checksum هم هنگام materialize شدن مدل stage و هم پیش از import کنترل
می‌شود. jobهای تکراری برای intent یکسان با idempotency key مشترک به همان job موجود resolve می‌شوند.

## Migration و عملیات

revision جدید `20261010_0018` جدول `dataset_file_stages` را با constraintهای اندازه، طول checksum
و ترتیب زمان ایجاد/انقضا اضافه می‌کند. indexهای checksum، creation time و expiry برای lookup و
cleanup تعریف شده‌اند. downgrade فقط همین indexها و جدول موقت را حذف می‌کند.

قبل از اجرای worker در محیط مقصد:

```bash
alembic upgrade head
```

worker موجود به handler جدید `dataset_file_import` مجهز است و نیاز به process جداگانه‌ای ندارد.
Frontend پس از enqueue، job ID را نشان می‌دهد و کاربر را برای پیگیری وضعیت به Monitoring می‌برد؛
کاتالوگ تا پیش از پایان worker نتیجهٔ نهایی را وانمود نمی‌کند.

## رفتار خطا

| code | نتیجه |
| --- | --- |
| `dataset_file_stage_missing` | failure دائمی؛ stage دیگر قابل بازیابی نیست |
| `dataset_file_stage_expired` | failure دائمی و حذف stage |
| `dataset_file_stage_checksum_mismatch` | failure دائمی و حذف stage |
| `dataset_file_stage_corrupt` | failure دائمی و حذف دادهٔ ناسازگار |
| `dataset_file_preview_mismatch` | failure دائمی؛ فایل یا mapping با preview یکسان نیست |
| خطای موقت DB/worker | retry توسط قرارداد عمومی `BackgroundJob` |

## معیار خروج P1-01

- [x] parse و ساخت Dataset از request commit به worker منتقل شد.
- [x] stage و job به‌صورت اتمیک و idempotent ثبت می‌شوند.
- [x] payload صف فاقد upload bytes است و به checksum متصل است.
- [x] TTL، cleanup موفق، cancellation، expiry و failure دائمی تست شده‌اند.
- [x] API و Frontend قرارداد asynchronous را نمایش می‌دهند.
- [x] migration و حضور جدول جدید در گیت PostgreSQL ثبت شده است.
- [x] تست end-to-end repository تا worker و Dataset نهایی وجود دارد.
- [ ] CI مالک مخزن روی commit نهایی backend، PostgreSQL و frontend را سبز کند.

تا سبز شدن CI، مرحله از نظر implementation کامل است اما evidence نهایی محیط مرجع هنوز ثبت نشده
است. P1-02 باید migration durable مربوط به Experiment Execution (`V3-D02`) را ادامه دهد.
