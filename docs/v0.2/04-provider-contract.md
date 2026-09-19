# TB2-003 — قرارداد اتصال داده و اسرار

این مرحله فقط اتصال‌های **read-only** دادهٔ بازار را پوشش می‌دهد. provider پیش‌فرض
`binance-public` عمومی است و هیچ API key، secret، token یا credential دریافت نمی‌کند.
افزودن provider معاملاتی، ثبت سفارش، برداشت و نگهداری credential خارج از دامنهٔ v0.2 است.

## قرارداد قابل اجرا

- provider فقط از allowlist سمت backend انتخاب می‌شود.
- capabilityهای market type و timeframe در catalog اعلام و پیش از import کنترل می‌شوند.
- هر request بیرونی timeout محدود و retry محدود با exponential backoff دارد.
- HTTP 429 با `Retry-After` محدودشده مدیریت می‌شود و retry نامحدود وجود ندارد.
- اتصال تا قبل از health check موفق فعال نمی‌شود؛ failure اتصال فعال را غیرفعال می‌کند.
- `last_error_code` یکی از کدهای پایدار زیر است و متن `last_error` فقط توضیح پاک‌سازی‌شده است:
  - `provider_request_failed`
  - `provider_timeout`
  - `provider_rate_limited`
  - `provider_http_error`
  - `provider_response_invalid`
  - `provider_unavailable`
- مقدارهای ورودی نامعتبر در پاسخ validation بازتاب داده نمی‌شوند.
- credentialهای رایج در خطای health check، پاسخ import و تاریخچهٔ import با
  `[REDACTED]` جایگزین می‌شوند.
- URLهای Binance فقط پارامترهای `symbol`، `interval`، `startTime`، `endTime` و `limit`
  دارند.

## migration

Migration `20260919_0015` ستون nullable به نام `last_error_code` را اضافه می‌کند، رکوردهای
قدیمی unhealthy را با `provider_request_failed` backfill می‌کند و سازگاری health state را
در constraint دیتابیس تثبیت می‌کند.

## بررسی محلی بدون شبکهٔ بیرونی

```bash
python -m alembic upgrade head
python -m alembic check
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
python -m pytest -m integration -v
```

## smoke test واقعی و اختیاری

این بررسی جزو CI نیست و فقط در محیطی اجرا می‌شود که دسترسی خروجی به Binance دارد. ابتدا API
را اجرا کن و سپس درخواست‌های زیر را به‌ترتیب بفرست. مقدار `connection_id` پاسخ مرحلهٔ ایجاد
را در سه URL بعدی جایگزین کن.

```bash
curl -sS http://127.0.0.1:8000/api/v1/market-data/providers

curl -sS -X POST http://127.0.0.1:8000/api/v1/market-data/connections \
  -H 'Content-Type: application/json' \
  -d '{"provider_id":"binance-public","display_name":"Binance public acceptance"}'

curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/market-data/connections/CONNECTION_ID/test

curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/market-data/connections/CONNECTION_ID/enable

curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/market-data/connections/CONNECTION_ID/datasets/preview \
  -H 'Content-Type: application/json' \
  -d '{"name":"BTC-USDT acceptance","pair":{"base_asset":"BTC","quote_asset":"USDT","market_type":"spot"},"timeframe":"1h","start_time":"2026-09-01T00:00:00Z","end_time":"2026-09-01T04:00:00Z"}'

curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/market-data/connections/CONNECTION_ID/datasets \
  -H 'Content-Type: application/json' \
  -d '{"name":"BTC-USDT acceptance","pair":{"base_asset":"BTC","quote_asset":"USDT","market_type":"spot"},"timeframe":"1h","start_time":"2026-09-01T00:00:00Z","end_time":"2026-09-01T04:00:00Z"}'
```

معیار قبولی smoke test: provider بدون credential فهرست شود، health برابر `healthy` شود،
connection فعال شود، preview چهار کندل بسته با `ready_to_import=true` برگرداند و import یک
`DatasetSummary` با `source=binance-public` و `candle_count=4` بسازد. اگر دسترسی شبکه به
Binance مسدود باشد، failure باید با کد پایدار، متن بدون secret و state غیرفعال ثبت شود.
