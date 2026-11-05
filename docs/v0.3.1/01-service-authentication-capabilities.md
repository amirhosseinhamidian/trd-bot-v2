# TRD-V031-01 — Service Authentication and Capability Negotiation

وضعیت: **Candidate**
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

## مرحله بعد

پس از CI موفق روی همان candidate SHA، فقط
`TRD-V031-01-FREEZE` مجاز است. `TRD-V031-02`، باز شدن `NEX-P3-03`، bump نسخه
`0.3.1` و ادعای compatibility تا Freezeهای بعدی و smoke واقعی local مسدود می‌مانند.
