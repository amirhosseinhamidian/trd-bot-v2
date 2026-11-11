# TRD-V031-09 — Full Resync and Gap Recovery

این مرحله مسیر fail-closed بازیابی projectionهای Nexora را روی قرارداد frozen نسخه `0.3.1`
پیاده می‌کند. عملیات HTTP جدیدی اضافه نشده است: consumer پس از دریافت `410 CURSOR_EXPIRED`،
مشاهدهٔ gap در `aggregate_version` یا checksum نامعتبر، انتشار projection را متوقف می‌کند و از
snapshotها و event feed موجود یک resync کامل می‌سازد.

## State machine و signal بازیابی

پاسخ `410` snapshot و event اکنون در `error.details` صریحاً
`action=full_snapshot_resync`، `projection_publication=pause`، قابل‌مشاهده‌بودن وضعیت degraded و
ممنوعیت partial publish را اعلام می‌کند. reset خاموش cursor همچنان ممنوع است.

State machine مراحل `projection_paused`، `snapshot_scanning`، `event_replay`، `reconciling`،
`ready_to_publish` و `published` را فقط به ترتیب مجاز طی می‌کند. هر gap یا تعارض غیرقابل‌حل آن
را به `operator_intervention_required` می‌برد و publication token تولید نمی‌شود.

## Snapshot و event reconciliation

هر ۱۰ resource frozen در سه گروه Portfolio، Decision و Alert باید—even اگر خالی باشند—به‌طور
کامل اسکن شوند. Source reference و checksum هر item پیش از ورود اعتبارسنجی می‌شود. Eventها با
هر دو کلید `event_id` و `idempotency_key` deduplicate می‌شوند؛ تکرار دقیق پذیرفته می‌شود، اما
تعارض identity یا پرش نسخهٔ aggregate باعث escalation اپراتور خواهد شد.

Eventهای قدیمی‌تر یا مساوی checkpoint snapshot دوباره اعمال نمی‌شوند. فقط replay پیوسته می‌تواند
یک publication token قطعی بسازد. projection و checkpoint باید با دو checksum در یک transaction
منتشر شوند؛ state machine هیچ مسیر partial publish ندارد.

## امنیت و مرز نسخه

این مرحله migration و endpoint جدید ندارد و فقط از snapshot/event evidence موجود استفاده می‌کند.
هیچ service token یا secret در report وارد نمی‌شود. اجرای زنده، سفارش پول واقعی، credential
صرافی، wallet، انتقال وجه و دیتابیس مشترک با Nexora همچنان ممنوع‌اند. Provider هنوز `0.3.0`
و ناسازگار است؛ `NEX-P3-03` تا پایان `TRD-V031-10` و Real Local Provider Smoke بسته می‌ماند.

## پذیرش یکپارچه

```bash
python scripts/verify_v0_3_1_full_resync.py
python -m unittest tests/test_v0_3_1_full_resync.py -v
python -m pytest tests/test_nexora_resync.py tests/test_nexora_event_feed.py \
  tests/test_nexora_portfolio_snapshots.py -v
python -m ruff format --check .
python -m ruff check .
python -m mypy
```

Workflow مرحله علاوه بر سناریوهای موفق، missing resource، duplicate conflict، gap حل‌نشده،
checksum tamper و جلوگیری از publication ناقص را تست می‌کند. Gateهای backend، PostgreSQL
round-trip و Alembic check، frontend، contract و security باید روی همان SHA موفق شوند تا Evidence
نسخه‌دار `TRD-V031-09`، مرحله `TRD-V031-10` را باز کند. Freeze task جداگانه وجود ندارد.
