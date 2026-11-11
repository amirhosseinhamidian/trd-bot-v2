# TRD-V031-00 — Nexora Integration Delivery Roadmap

وضعیت: **Frozen**
تاریخ تصمیم: ۲۰۲۶-۱۱-۰۵
مبنای کد: TRD Bot `v0.3.0` در commit
`bbb9fd4fbc25e25aa512a9fde1dda912321cdd33`

## هدف

نسخه `0.3.1` فقط boundary لازم برای اتصال نسخه‌دار Nexora را به TRD Bot اضافه
می‌کند. این نسخه نباید رفتار strategy، policyهای Risk یا محدوده معامله را به‌صورت
اساسی تغییر دهد و همچنان فقط حالت‌های `RESEARCH`، `BACKTEST`، `PAPER` و
`SHADOW` را پشتیبانی می‌کند.

قرارداد ورودی در Nexora با commit
`1e114b58b1a9cfc4ef91280c6506aa58bb2f53e8` فریز شده است. دو artifact زیر
بدون تغییر semantic در این repository نگهداری می‌شوند:

- قرارداد `NEX-P3-02` با checksum
  `e0c0cee635c27e52825501fd36de68cb07a6e3feeb70b8fdefeb5e5fcbbbf753`؛
- provider profile نسخه `0.3.1` با checksum
  `48cfcd61b8f2cb866e4c921d31f5c61db83d3f08e5123d690a069a57c3aba109`.

نسخه `0.3.0` همچنان ناسازگار است. سازگاری `0.3.1` فقط پس از تطبیق دقیق
capabilityها و اجرای smoke واقعی local بین دو repository قابل اعلام است.

## ترتیب اجرا

| مرحله | خروجی اصلی |
| --- | --- |
| `TRD-V031-00` | adoption قرارداد فریز‌شده و roadmap fail-closed |
| `TRD-V031-00-FREEZE` | ثبت CI همان SHA و Freeze roadmap |
| `TRD-V031-01` | service token خصوصی و capability negotiation |
| `TRD-V031-02` | snapshot protocol پایدار، cursor و source reference |
| `TRD-V031-03` | snapshotهای Portfolio |
| `TRD-V031-04` | snapshotهای Decision |
| `TRD-V031-05` | snapshotهای Alert |
| `TRD-V031-06` | durable event feed، lookup، replay و gap detection |
| `TRD-V031-07` | commandهای idempotent برای accept/reject/defer |
| `TRD-V031-08` | export job، status و manifest کامل |
| `TRD-V031-09` | full resync و gap recovery |
| `TRD-V031-10` | contract fixtures و smoke واقعی با Nexora |
| `TRD-V031-11` | پذیرش نهایی و release cut نسخه `0.3.1` |

مراحل `00` تا `04` در تاریخ واقعی repository با چرخهٔ مستقل Freeze تکمیل شده‌اند و artifactهای
آن‌ها immutable باقی می‌مانند. از مرحلهٔ `TRD-V031-05` به بعد، هر مرحله فقط پس از
`CI Acceptance PASS` همان commit باز می‌شود و Freeze مستقل stage حذف شده است. جزئیات این
تصمیم در [ADR فرایند یکپارچه](development-workflow.md) ثبت شده است.

مرحله‌هایی که migration دارند باید روی PostgreSQL 17 از schema خالی و upgrade path موجود
آزمایش شوند. PostgreSQL round-trip و `alembic check` حتی در مرحله‌های بدون migration نیز
به‌عنوان gate تشخیص drift اجرا می‌شوند.

## مرز امنیتی و عملیاتی

موارد زیر در تمام مسیر ثابت می‌مانند:

- اتصال مستقیم یا دیتابیس مشترک با Nexora ممنوع است؛
- service token فقط از فایل خصوصی absolute خوانده می‌شود و به browser، query،
  cookie، log یا export وارد نمی‌شود؛
- event delivery حداقل یک‌بار و idempotent است؛ ادعای exactly-once وجود ندارد؛
- cursor منقضی با `410` پاسخ می‌گیرد و reset خاموش ممنوع است؛
- owner review در Nexora منبع حقیقت است و command provider فقط feedback مربوط به
  Paper/Shadow محسوب می‌شود؛
- export ناقص پذیرفته نمی‌شود و تمام فایل‌ها checksum و lineage دارند؛
- exchange credential، wallet، fund transfer و live order همچنان خارج از scope هستند؛
- هیچ مدل AI یا ML مجوز اجرای معامله ایجاد نمی‌کند.

## رابطه با Nexora

`NEX-P3-03` تا پایان `TRD-V031-10` و ثبت smoke واقعی باز نمی‌شود. fixtureها برای
توسعه کافی‌اند، اما جای provider واقعی را نمی‌گیرند. نبود VPS مانع این smoke محلی
نیست؛ همچنین سبز شدن این نسخه به معنی production readiness یا عبور از گیت استقرار
Nexora نیست.

## شواهد Freeze

roadmap روی candidate زیر فریز شده است:

- commit: `947e0313aab25829e1944d093bc9b5e8e900b459`؛
- tree: `93dff48c4b8b7c7f522c4500a19b99698c017922`؛
- workflow اختصاصی roadmap: run
  [`42025511338`](https://github.com/amirhosseinhamidian/trd-bot-v2/actions/runs/42025511338)،
  نتیجه `success`؛
- workflow کامل CI: run
  [`42025511100`](https://github.com/amirhosseinhamidian/trd-bot-v2/actions/runs/42025511100)،
  شامل backend، frontend و PostgreSQL، همگی `success`؛
- run/job IDها و checksumهای roadmap و قرارداد upstream در
  `artifacts/v0.3.1/trd-v031-00-integration-roadmap-freeze.json` ثبت شده‌اند.

این Freeze فقط roadmap و قرارداد ورودی را می‌بندد. هنوز endpoint، migration،
service token runtime یا ادعای سازگاری provider تحویل نشده است.

## معیار پذیرش Freeze

```bash
python scripts/verify_v0_3_1_integration_roadmap.py

python -m unittest \
  tests/test_v0_3_1_integration_roadmap.py \
  -v

python -m ruff format --check \
  scripts/verify_v0_3_1_integration_roadmap.py \
  tests/test_v0_3_1_integration_roadmap.py

python -m ruff check \
  scripts/verify_v0_3_1_integration_roadmap.py \
  tests/test_v0_3_1_integration_roadmap.py

python -m mypy
python -m pytest -m "not integration"
git diff --check
```

خروجی verifier باید شامل markerهای زیر باشد:

```text
TRD_V031_00_NEXORA_CONTRACT_ADOPTION=PASS
TRD_V031_00_ROADMAP=PASS
TRD_V031_00_FREEZE=PASS
TRD_V031_00_RUNTIME_CHANGE=NONE
TRD_V031_00_DATABASE_MIGRATION=NONE
TRD_V031_01_IMPLEMENTATION_GATE=OPEN
NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE
TRD_BOT_LIVE_EXECUTION=DISABLED
```

مرحله مجاز بعدی فقط `TRD-V031-01 — Service authentication and capability negotiation` است.

> این marker، خروجی تاریخی Freeze مرحلهٔ `00` است. وضعیت جاری repository در commit
> `2ca62661fc80096e03c16e2b02cc19a997ba2d07` مراحل `00` تا `08` را پذیرفته‌شده نگه
> می‌دارد و مرحلهٔ جاری `TRD-V031-09` را با مدل `Implementation + Acceptance` باز می‌کند.
