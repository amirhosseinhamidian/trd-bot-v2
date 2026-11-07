# TRD-V031-07 — Idempotent Human Decision Review Commands

وضعیت: **Acceptance candidate**
تاریخ تصمیم: ۲۰۲۶-۱۱-۰۷
پیش‌نیاز پذیرفته‌شده: `TRD-V031-06` در commit
`ee96c73ead801a93497b1cb9b06decb5eac5842a`

## هدف

این مرحله feedback انسانی accept/reject/defer را از Nexora برای decision evaluationهای Paper و
Shadow دریافت می‌کند. Nexora منبع حقیقت review مالک است و TRD Bot فقط receipt پایدار ثبت می‌کند؛
این command نه مجوز اجرا می‌سازد، نه live order ایجاد می‌کند و نه portfolio transaction ثبت می‌کند.

## Endpoint و قرارداد

```text
POST /api/v1/integration/nexora/commands/decision-reviews
```

درخواست به service token، correlation ID، `Content-Type: application/json` و `Idempotency-Key`
با طول ۱۶ تا ۱۶۰ نیاز دارد. سه command نسخه‌دار پذیرفته می‌شوند:

- `decision_review.accept.v1`
- `decision_review.reject.v1`
- `decision_review.defer.v1`

payload باید source reference کامل یک `decision_evaluation` موجود را شامل شود. `decision_id`، mode،
شناسه منبع و checksum با snapshot immutable تطبیق داده می‌شوند. mismatch با `412` رد می‌شود.

## Idempotency و persistence

- اولین درخواست معتبر با `202` و receipt با status برابر `accepted` پاسخ می‌گیرد؛
- replay همان key و همان canonical payload با همان command ID و زمان پذیرش، ولی correlation جاری،
  receipt با status برابر `duplicate` می‌دهد؛
- همان key با payload متفاوت با `409 IDEMPOTENCY_CONFLICT` fail-closed می‌شود؛
- migration `20261107_0039` journal append-only `nexora_decision_reviews` را ایجاد می‌کند؛
- request checksum، source reference، source checksum و safety flags در journal ثبت می‌شوند.

## مرز امنیتی

mode فقط `paper` یا `shadow` است. provider همچنان نسخه `0.3.0` و ناسازگار باقی می‌ماند. هیچ exchange
credential، live execution، wallet/fund transfer یا database مشترکی اضافه نشده است. `NEX-P3-03`
تا تکمیل `TRD-V031-10` و موفقیت Real Local Provider Smoke بسته می‌ماند.

## Acceptance

```bash
python3 scripts/verify_v0_3_1_decision_review_commands.py
python3 -m unittest tests/test_v0_3_1_decision_review_commands.py -v
python3 -m pytest \
  tests/test_nexora_decision_reviews.py \
  tests/test_nexora_decision_snapshots.py \
  tests/test_nexora_snapshot_persistence.py \
  tests/test_database.py -v
python3 -m ruff format --check .
python3 -m ruff check .
python3 -m mypy
python3 -m pytest -m "not integration"
```

فقط artifact پذیرش موفق متصل به همان commit می‌تواند `TRD-V031-08` را باز کند. Freeze task
جداگانه‌ای ساخته نمی‌شود.
