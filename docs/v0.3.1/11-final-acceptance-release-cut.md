# TRD-V031-11 — Final acceptance and v0.3.1 release cut

این مرحله یک `Implementation + Acceptance` واحد و آخرین مرحلهٔ roadmap نسخهٔ `0.3.1` است.
تغییر نسخه، release notes، قرارداد release و پذیرش CI در همین چرخه انجام می‌شوند؛ commit یا task
جداگانه‌ای صرفاً برای Freeze ایجاد نمی‌شود.

## پیش‌شرط قطعی

مرحلهٔ `TRD-V031-10` روی commit
`9d2bbf2caa8fa1281efaf053d33c73c5e495d3ef` و tree
`f2392c9cca0d9e3e58db350d8ba8d7cc3aafa7dd` پذیرفته شده است. workflow شمارهٔ
`43088041255` موفق بوده و دو artifact پذیرش و smoke با شناسه و digest در
`contracts/trd-bot-v0.3.1-final-release.json` ثبت شده‌اند.

## گیت پذیرش و tag

workflow مرحلهٔ ۱۱ ابتدا artifact پذیرش مرحلهٔ ۱۰ را از GitHub دریافت و اعتبارسنجی می‌کند. سپس
verifier مرحله، Ruff، mypy strict، تست‌های backend، چرخهٔ fresh-install/downgrade/upgrade و
`alembic check` روی PostgreSQL، تست و build فرانت‌اند، تست‌های امنیتی و smoke واقعی ۱۲ سناریویی
با Nexora پین‌شده را روی یک SHA اجرا می‌کند.

دو artifact با retention نودروزه تولید می‌شوند:

- `TRD-V031-11-smoke-<commit>` برای گزارش smoke واقعی؛
- `TRD-V031-11-acceptance-<commit>` برای نتیجهٔ تمام gateها، SHA commit/tree، run ID/attempt و
  checksum فایل‌های evidence.

فقط وقتی artifact پذیرش روی همان SHA وضعیت `accepted` دارد، tag سبک `v0.3.1` باید دقیقاً روی همان
commit ساخته شود. tag روی SHA دیگر، CI ناموفق/لغوشده/ناقص، اجرای pull request یا smoke محلی به‌تنهایی
release محسوب نمی‌شود. Run ID جاری داخل commit ثبت نمی‌شود تا circular dependency ایجاد نشود؛ هویت
run در artifact CI و مرجع immutable انتشار در Git tag نگهداری می‌شود.

## دامنهٔ compatibility

پس از پذیرش same-SHA و ایجاد tag، TRD BOT `v0.3.1` برای قرارداد
`nexora-trd-integration-v1` و بازهٔ provider `>=0.3.1,<0.4.0` در برابر Nexora پین‌شده تأیید می‌شود.
این نتیجه فقط compatibility اتصال local/private را پوشش می‌دهد. باز کردن یا Freeze کردن
`NEX-P3-03` متعلق به repository خود Nexora است و این release آن را به‌طور خودکار باز نمی‌کند.

## مرز ایمنی

- live trading، سفارش پول واقعی و external order submission غیرفعال‌اند؛
- exchange credential، wallet و fund transfer وجود ندارند؛
- دیتابیس TRD BOT با Nexora مشترک نیست؛
- secret یا service token در evidence ثبت نمی‌شود؛
- production deployment یا آماده‌بودن VPS ادعا نمی‌شود.

## بازیابی شکست

در شکست هر gate، tag ساخته نمی‌شود. علت روی همان branch اصلاح و commit جدید push می‌شود؛ workflow
کامل باید برای SHA جدید تکرار شود. artifact ناموفق یا ناقص نمی‌تواند release را قبول کند و نباید با
غیرفعال‌کردن gate یا جایگزین‌کردن smoke واقعی با fixture سبز شود.
