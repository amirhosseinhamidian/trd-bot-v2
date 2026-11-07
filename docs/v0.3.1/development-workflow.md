# ADR-001 — Integrated Stage Implementation and Acceptance

وضعیت: **Accepted**
تاریخ تصمیم: ۲۰۲۶-۱۱-۰۷
دامنه: `TRD BOT v0.3.1`

## تصمیم

از مرحلهٔ واقعی بعدی، یعنی `TRD-V031-05`، هر مرحله یک مأموریت واحد
**Implementation + Acceptance** است. زنجیرهٔ تحویل به‌صورت زیر است:

```text
Stage N → CI Acceptance PASS → Stage N+1
```

دیگر برای یک مرحلهٔ عادی، تسک یا commit جداگانه‌ای فقط برای ثبت Freeze ساخته نمی‌شود.
این تغییر کنترل کیفی را حذف نمی‌کند؛ همان کنترل‌ها در reusable workflow
`.github/workflows/v0-3-1-stage-acceptance.yml` اجرا و نتیجهٔ آن‌ها برای همان commit به‌صورت
evidence نسخه‌دار ذخیره می‌شود.

## دلیل شروع از TRD-V031-05

در زمان تصویب این ADR، وضعیت واقعی branch با commit
`250d84ebd93b9999230ac316b1cb919e66be7bc5` بررسی شد. مراحل `TRD-V031-00` تا
`TRD-V031-04` پیش‌تر با مدل دوچرخه‌ای Implementation/Freeze تکمیل شده بودند. بازنویسی
artifactها یا verifierهای آن‌ها تاریخ ممیزی را مخدوش می‌کرد؛ بنابراین هر پنج Freeze تاریخی
بدون تغییر باقی می‌مانند و مدل جدید از `TRD-V031-05` فعال است.

## چرخهٔ توسعه

برای هر مرحله از `05` تا `10`:

1. scope، قرارداد، معیار پذیرش و مرز امنیتی در stage manifest تعریف می‌شود.
2. implementation، تست‌ها، قرارداد و مستند مرحله در همان مأموریت تکمیل می‌شوند.
3. stage manifest از `planned` به `candidate` تغییر می‌کند.
4. workflow اختصاصی مرحله فقط reusable acceptance workflow را با `stage_id` صدا می‌زند.
5. prerequisite evidence مرحلهٔ قبل قبل از اجرای تست‌ها بررسی می‌شود.
6. gateهای stage contract، backend، PostgreSQL، frontend و security اجرا می‌شوند.
7. job نهایی، نتیجه را برای همان commit و tree در JSON نسخه‌دار ثبت می‌کند.
8. فقط evidence با `accepted=true` و تمام gateهای `success` مرحلهٔ بعد را باز می‌کند.

`TRD-V031-11` مرحلهٔ Final Release Cut است و می‌تواند Freeze رسمی release داشته باشد.

## Stage Acceptance Policy

منبع حقیقت فرایند
`contracts/trd-bot-v0.3.1-stage-acceptance-policy.json` است. ترتیب `05` تا `11`،
وابستگی‌ها، migration expectation، gateهای اجباری و استثناهای Freeze در این قرارداد
fail-closed تعریف شده‌اند.

هر stage manifest در `contracts/v0.3.1/stage-acceptance/` قرار می‌گیرد و شامل موارد زیر است:

- prerequisite evidence مرحلهٔ قبل؛
- verifier و تست‌های focused؛
- وضعیت migration؛
- فایل‌ها یا دایرکتوری‌هایی که checksum آن‌ها در evidence ثبت می‌شود؛
- مرحلهٔ بعد و مرزهای امنیتی.

برای انتقال از یک مرحلهٔ پذیرفته‌شده به مرحلهٔ بعد، فقط SHA commit پذیرفته‌شده در manifest
مرحلهٔ بعد ثبت می‌شود. Run ID در Git commit نمی‌شود و از GitHub Actions API بر اساس نام
artifact و همان SHA بازیابی می‌شود؛ بنابراین circular dependency ایجاد نمی‌شود.

## CI Evidence Collection

فایل خروجی مطابق
`contracts/trd-bot-v0.3.1-stage-acceptance-evidence.schema.json` است و حداقل شامل موارد
زیر می‌شود:

- Stage ID، commit SHA، tree SHA و ref؛
- workflow run ID، run attempt، event و timestamp؛
- نتیجهٔ هر gate اجباری؛
- وضعیت تست‌های backend، PostgreSQL، frontend، stage contract و security؛
- checksum قرارداد، verifier، تست‌ها و artifactهای مرحله؛
- overall result، وضعیت بازشدن مرحلهٔ بعد و checksum خود evidence.

نام artifact از الگوی `TRD-V031-NN-acceptance-<commit-sha>` پیروی می‌کند و retention آن
**۹۰ روز** است. برای Release Candidate، تغییر قرارداد ناسازگار، تغییر امنیتی/معماری پرریسک
و Final Release Cut، evidence رسمی می‌تواند به Git منتقل شود. این انتقال milestone است،
نه یک Freeze تکراری برای هر stage.

Evidence فقط از metadata و نتیجهٔ gateهای allowlist‌شده ساخته می‌شود. token، password،
Authorization header، private key و secret در آن مجاز نیستند.

## Gateهای اجباری

- Ruff formatting و Ruff lint؛
- mypy strict؛
- backend unit tests؛
- PostgreSQL 17 integration tests؛
- fresh install، downgrade/upgrade path و `alembic check`؛
- frontend formatting، ESLint، TypeScript، test و production build؛
- contract و focused stage tests؛
- Nexora security boundary و deterministic persistence tests.

وجود migration تازه شرط اجرای PostgreSQL gate نیست؛ این gate همیشه اجرا می‌شود. در مراحل
دارای migration، round-trip واقعی علاوه بر `alembic check` الزام قطعی است.

## Stage Transition Rules

- `success` برای تمام gateهای اجباری + event از نوع `push` یا `workflow_dispatch`:
  نتیجه `accepted` و مرحلهٔ بعد باز می‌شود.
- اجرای موفق Pull Request: فقط `validation_only` و حق بازکردن مرحلهٔ بعد ندارد.
- `Failed` یا `Cancelled`: نتیجه `rejected` و transition بسته می‌ماند.
- gate با وضعیت `Skipped` یا missing: نتیجه `incomplete` و transition بسته می‌ماند.
- نبود artifact، artifact منقضی، SHA متفاوت، checksum نامعتبر یا run تکراری مبهم:
  prerequisite fail-closed می‌شود.

`NEX-P3-03` با پذیرش داخلی stageها باز نمی‌شود. این gate تا پایان `TRD-V031-10` و موفقیت
Real Local Provider Smoke بسته می‌ماند. نسخهٔ provider نیز پیش از smoke و تطبیق قرارداد،
compatible اعلام نمی‌شود.

## Release Freeze Policy

Freeze مستقل فقط برای موارد زیر مجاز است و باید دلیل فنی در همان milestone ثبت شود:

1. Release Candidate؛
2. Final Release Cut؛
3. تغییر قرارداد اساسی یا ناسازگار؛
4. تغییر معماری یا امنیتی پرریسک؛
5. milestone نیازمند audit رسمی.

Freezeهای `00` تا `04` immutable هستند. verifierهای تاریخی همچنان اجرا می‌شوند تا backward
compatibility و checksumهای ثبت‌شده حفظ شوند.

## Recovery Procedure for Failed CI

1. run ناموفق را با commit SHA و gate قرمز شناسایی کن.
2. evidence ردشده یا ناقص را بررسی کن؛ gate را bypass یا optional نکن.
3. علت را در همان stage اصلاح و commit تازه بساز.
4. workflow کامل acceptance را روی commit تازه اجرا کن.
5. فقط artifact همان commit تازه می‌تواند accepted شود.
6. rerun یک run transient مجاز است؛ `run_attempt` جدید در evidence ثبت می‌شود.
7. اگر run لغو شده باشد، نبود evidence پذیرفته‌شده به‌معنی بسته‌ماندن transition است.

## آماده‌سازی TRD-V031-05

manifest برنامه‌ریزی مرحله در
`contracts/v0.3.1/stage-acceptance/trd-v031-05.json` قرار دارد. در مأموریت بعدی باید feature
Alert Snapshot Resources، contract، verifier و تست‌های اعلام‌شده ایجاد، manifest به
`candidate` تبدیل و workflow مرحله به reusable acceptance متصل شود. این ADR هیچ feature
جدیدی از مرحلهٔ `05` را پیاده‌سازی نمی‌کند.
