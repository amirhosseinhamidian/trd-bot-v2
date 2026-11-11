# TRD-V031-10 — Cross-repository contract tests and real local smoke

این stage قرارداد frozen بین TRD Bot و Nexora را با consumer واقعی Nexora و provider واقعی TRD Bot
روی loopback اعتبارسنجی می‌کند. مبنای consumer، commit
`1e114b58b1a9cfc4ef91280c6506aa58bb2f53e8` و tree
`6c5756f177c2f0025faeb776515e99c077630177` است. provider profile دو repository باید
byte-identical و دارای SHA-256 برابر
`2d21e80db378c2dc2c1b3a6fbb1f44bcbbad0c34d89f4d073b25e179a55fbcc8` باشد.

## مرز سازگاری event

مدل durable داخلی Stage 06 برای journal، gap detection و verifier تاریخی حفظ شده است. در مرز HTTP،
projection صریح frozen wire contract تولید می‌شود: `aggregate` تو‌در‌تو، `source` checksum-bound،
`emitted_at`، correlation ID قطعی و `payload_checksum`. این تغییر migration یا بازنویسی evidence
تاریخی ندارد.

## پذیرش واقعی

job `stage_contract` ابتدا verifier و focused tests را اجرا می‌کند، سپس Nexora pin‌شده را در مسیر
جداگانه checkout می‌کند و Uvicorn را روی `127.0.0.1` بالا می‌آورد. consumer واقعی
`TrdBotClient` هر ۱۲ سناریوی provider profile را اجرا می‌کند. تنها سناریوی optimistic local owner
review یک fixture contract است، چون این guard مالک Nexora است و نباید به command provider تبدیل شود؛
یازده سناریوی دیگر مستقیماً با provider محلی واقعی اجرا می‌شوند.

گزارش `trd-bot-v031-cross-repository-smoke-v1` شامل commit و tree هر دو repository، run ID،
۱۲ نتیجه، checksum profile و checksum خود گزارش است. artifact با نام
`TRD-V031-10-smoke-<commit>` به مدت ۹۰ روز نگهداری می‌شود. token موقت فقط در فایل خصوصی قرار دارد
و گزارش، log و export برای عدم نشت آن بررسی می‌شوند.

## انتقال stage

موفقیت محلی به‌تنهایی کافی نیست. `TRD-V031-11` و eligibility مربوط به `NEX-P3-03` فقط پس از سبز
شدن همه gateهای workflow و تولید acceptance evidence همان SHA مجاز می‌شوند. Stage 10 تسک Freeze
جداگانه ندارد؛ Freeze رسمی release در Stage 11 باقی می‌ماند. live execution، order submission،
exchange credential، fund transfer و database مشترک همچنان ممنوع‌اند.
