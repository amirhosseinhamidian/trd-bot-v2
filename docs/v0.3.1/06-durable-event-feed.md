# TRD-V031-06 — Durable Event Feed, Lookup, Cursors, and Replay

وضعیت: **Acceptance candidate**
تاریخ تصمیم: ۲۰۲۶-۱۱-۰۷
پیش‌نیاز پذیرفته‌شده: `TRD-V031-05` در commit
`10435e4c98e59d2d616fde1c6b92a2598d20a1ee`

## هدف

این مرحله یک journal پایدار و append-only برای eventهای قابل مصرف Nexora فراهم می‌کند. هر event
دارای envelope نسخه‌دار، checksum، `event_id`، `idempotency_key` و `aggregate_version` است.
مصرف‌کننده می‌تواند feed را page کند، یک event را با ID بازیابی کند و cursor قبلی را تا زمان
انقضا replay کند.

## Endpointها

```text
GET /api/v1/integration/nexora/events
GET /api/v1/integration/nexora/events/{event_id}
```

هر دو endpoint به service token، correlation ID و `Accept: application/json` نیاز دارند و پاسخ
موفق آن‌ها `private, no-store` است.

## Semantics و recovery

- تحویل صریحاً `at_least_once` است و ادعای exactly-once وجود ندارد؛
- `event_id` و `idempotency_key` کلیدهای deduplication هستند؛
- ترتیب تضمین‌شده در سطح aggregate و با `aggregate_version` است؛
- version غیرپیوسته هنگام append رد می‌شود و consumer نیز می‌تواند gap را از envelope تشخیص دهد؛
- replay همان cursor ممکن است همان eventها را دوباره تحویل دهد؛
- cursor ناشناخته با `400` و تغییر limit با `409` رد می‌شود؛
- cursor منقضی `410` می‌دهد و full snapshot resync لازم است؛
- lookup همان envelope checksummed موجود در feed را برمی‌گرداند.

## Persistence

migration `20261107_0038` دو جدول ایجاد می‌کند:

- `nexora_integration_events`: journal append-only؛
- `nexora_event_cursors`: checkpointهای opaque با TTL و limit ثابت.

CI باید fresh install، downgrade به base، upgrade path، Alembic check و PostgreSQL integration را
با موفقیت اجرا کند.

## مرز امنیتی

payload فقط برای Research/Paper/Shadow است. `offline_only=true` و
`external_order_submission_allowed=false` در envelope و schema اجباری هستند. service token،
exchange credential، live order، wallet action و fund transfer در journal یا cursor قرار نمی‌گیرند.
Review command هنوز به `TRD-V031-07` موکول است. Provider همچنان `0.3.0` و ناسازگار است و
`NEX-P3-03` تا `TRD-V031-10` و Real Local Provider Smoke بسته می‌ماند.

## Acceptance

```bash
python3 scripts/verify_v0_3_1_event_feed.py
python3 -m unittest tests/test_v0_3_1_event_feed.py -v
python3 -m pytest \
  tests/test_nexora_event_feed.py \
  tests/test_nexora_snapshot_protocol.py \
  tests/test_nexora_snapshot_persistence.py \
  tests/test_database.py -v
python3 -m ruff format --check .
python3 -m ruff check .
python3 -m mypy
python3 -m pytest -m "not integration"
```

فقط artifact پذیرش موفق متصل به همان commit می‌تواند `TRD-V031-07` را باز کند و Freeze task
جداگانه‌ای ساخته نمی‌شود.
