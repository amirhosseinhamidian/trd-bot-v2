# TRD-V031-01 — Service Authentication and Capability Negotiation

وضعیت: **Frozen**
تاریخ تصمیم: ۲۰۲۶-۱۱-۰۵
پیش‌نیاز فریز‌شده: commit
`7b878dec891f5cd6e540a58cdeab2bc458214491`

## خروجی مرحله

این مرحله اولین runtime boundary اتصال Nexora را در namespace زیر اضافه می‌کند:

```text
GET /api/v1/integration/nexora/capabilities
```

endpoint فقط پس از دریافت service token معتبر، `Accept: application/json` و یک
`X-Correlation-ID` از نوع UUID canonical پاسخ می‌دهد. پاسخ شامل نسخه قرارداد، نسخه
provider، correlation ID و capability matrix فریز‌شده است.

نسخه برنامه در این candidate عمداً `0.3.0` باقی می‌ماند. در نتیجه کلاینت Nexora آن
را خارج از بازه `>=0.3.1,<0.4.0` تشخیص می‌دهد و sync را شروع نمی‌کند. تکمیل این
endpoint به‌تنهایی ادعای سازگاری یا readiness نسخه `0.3.1` نیست.

## ساخت service token

برای development محلی یک token تصادفی حداقل ۳۲ بایتی در فایل خصوصی absolute بسازید:

```bash
install -d -m 700 "$HOME/.config/trd-bot/private"
python3.12 - <<'PY'
import secrets
from pathlib import Path

path = Path.home() / ".config/trd-bot/private/nexora-service-token"
path.write_text(secrets.token_urlsafe(48), encoding="ascii")
path.chmod(0o600)
print(path)
PY

export TRD_BOT_NEXORA_SERVICE_TOKEN_FILE="$HOME/.config/trd-bot/private/nexora-service-token"
```

token نباید در `.env`، command line، query string، cookie، browser، log، payload یا
export قرار گیرد. فایل باید regular، بدون symlink، absolute، فقط قابل دسترس برای
مالک و بین ۳۲ تا ۴۰۹۶ بایت ASCII printable باشد. تنظیم ناامن یا فایل ناخوانا با
`503 SOURCE_UNAVAILABLE` fail closed می‌شود؛ token مفقود یا نامعتبر با پاسخ یکسان
و sanitised از نوع `401 UNAUTHORIZED` رد می‌شود.

## مرز transport

- در `production` فقط HTTPS پذیرفته می‌شود؛
- HTTP در `development` و `test` فقط برای loopback مجاز است؛
- CORS اجازه ارسال `Authorization` یا `X-Correlation-ID` را به browser نمی‌دهد؛
- پاسخ redirect ندارد و token هرگز در response یا error بازتاب داده نمی‌شود؛
- مقایسه token با `hmac.compare_digest` انجام می‌شود.

## capability matrix

پاسخ موفق دقیقاً این capabilityها را اعلام می‌کند:

| فیلد | مقدار |
| --- | --- |
| contract | `nexora-trd-integration-v1` |
| event envelope | `trd-integration-event-envelope-v1` |
| export manifest | `nexora-export-manifest-v1` |
| source reference | `nexora-source-reference-v1` |
| commands | `decision_review.accept.v1`, `decision_review.reject.v1`, `decision_review.defer.v1` |
| cache TTL | ۳۰۰ ثانیه |

Snapshot، event، command و export endpointها هنوز در این مرحله ایجاد نشده‌اند و به
ترتیب roadmap اضافه می‌شوند. migration دیتابیس نیز وجود ندارد.
Inventory فریز‌شدهٔ سطح API نیز برای ثبت additive operation جدید از ۱۱۲ به ۱۱۳
به‌روزرسانی شده است؛ artifact پذیرش نهایی `v0.3.0` دست‌نخورده باقی می‌ماند.

## اجرای acceptance محلی

ابتدا محیط Python 3.12 پروژه را فعال کنید؛ در صورت نبود آن:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

سپس gateها را اجرا کنید:

```bash
python scripts/verify_v0_3_1_service_auth_capabilities.py

python -m unittest \
  tests/test_v0_3_1_service_auth_capabilities.py \
  -v

python -m pytest \
  tests/test_nexora_integration_capabilities.py \
  -v

python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
git diff --check
```

خروجی verifier باید markerهای زیر را داشته باشد:

```text
TRD_V031_01_SERVICE_AUTHENTICATION=PASS
TRD_V031_01_CAPABILITY_NEGOTIATION=PASS
TRD_V031_01_CONSTANT_TIME_COMPARISON=PASS
TRD_V031_01_TRANSPORT_BOUNDARY=PASS
TRD_V031_01_FREEZE=PASS
TRD_V031_01_DATABASE_MIGRATION=NONE
TRD_BOT_PROVIDER_VERSION=0.3.0_INCOMPATIBLE
NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE
TRD_BOT_LIVE_EXECUTION=DISABLED
NEXT_ALLOWED_STAGE=TRD-V031-02
```

## شواهد Freeze

این مرحله روی candidate زیر فریز شده است:

- commit: `8020a31e0caede35461c7f5684e82b06bda4bb35`؛
- tree: `5c625cac1b92cbc825c2dc661839e045280eb160`؛
- workflow اختصاصی service-auth: run
  [`42032113793`](https://github.com/amirhosseinhamidian/trd-bot-v2/actions/runs/42032113793)،
  نتیجه `success`؛
- workflow roadmap: run
  [`42032113701`](https://github.com/amirhosseinhamidian/trd-bot-v2/actions/runs/42032113701)،
  نتیجه `success`؛
- workflow کامل CI: run
  [`42032113886`](https://github.com/amirhosseinhamidian/trd-bot-v2/actions/runs/42032113886)،
  شامل backend، frontend و PostgreSQL، همگی `success`؛
- checksumهای stage contract، release inventory و فایل‌های runtime در
  `artifacts/v0.3.1/trd-v031-01-service-auth-capabilities-freeze.json` ثبت شده‌اند.

این Freeze فقط service-auth و capability negotiation را می‌بندد. نسخه provider
هنوز `0.3.0` و ناسازگار است؛ snapshot protocol، migration، smoke واقعی و ادعای
production readiness در این مرحله وجود ندارند.

## مرحله بعد

پس از این Freeze، فقط `TRD-V031-02 — Stable snapshot protocol and source references`
مجاز است. باز شدن `NEX-P3-03`، bump نسخه `0.3.1` و ادعای compatibility تا
Freezeهای بعدی و smoke واقعی local مسدود می‌مانند.
