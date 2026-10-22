# P6-06 — Fresh Install and Upgrade Verification

وضعیت: **پیاده‌سازی شده؛ اجرای مرجع روی PostgreSQL 17 و SHA کامیت‌شده باقی است**

این مرحله دو مسیر مستقل release را روی دیتابیس‌های disposable واقعی بررسی می‌کند:

1. نصب تازه از schema کاملاً خالی تا migration head نسخه v0.3؛
2. ارتقا از head رسمی v0.2 به head نسخه v0.3 با حفظ identity داده‌های lineage.

Runner هیچ دیتابیس، role یا volume ایجاد و حذف نمی‌کند. ساخت و cleanup دیتابیس‌ها عمداً در اختیار
اپراتور باقی می‌ماند و اجرای runner فقط پس از تأیید نام دقیق هر دو دیتابیس انجام می‌شود.

## قرارداد fail-closed

| مورد | Fresh install | Upgrade |
| --- | --- | --- |
| وضعیت اولیه | public schema خالی | `20260926_0017` |
| وضعیت نهایی | `20261020_0036` | `20261020_0036` |
| دیتابیس | نام شامل `fresh` و `test`/`bench` | نام شامل `upgrade` و `test`/`bench` |
| schema نهایی | دقیقاً 55 جدول application | دقیقاً 55 جدول application |
| Alembic drift | صفر | صفر |
| lineage | relations خالی باقی بمانند | identity checksum قبل و بعد یکسان باشد |

این نام‌ها به‌طور صریح رد می‌شوند: `postgres`، `template0`، `template1`، `trd_bot` و
`trd_bot_test`. دو URL یا نام یکسان نیز رد می‌شوند. Runner نیازمند worktree کاملاً clean است تا
artifact به `git rev-parse HEAD` واقعی متصل شود.

Relations حفاظت‌شده عبارت‌اند از:

- `dataset_snapshots`
- `research_experiments`
- `simulated_portfolios`
- `simulated_positions`
- `candidate_journals`

Artifact فقط نام دیتابیس‌های disposable، revision، تعداد جدول، checksum نام جدول‌ها، تعداد row و
checksum شناسه‌ها/محتوای canonical را ثبت می‌کند. DSN، password، payload پژوهشی و محتوای journal
ثبت نمی‌شوند.

## آماده‌سازی PostgreSQL 17

ابتدا container محلی را روشن کنید:

```bash
docker compose up -d postgres
docker compose ps
```

دو دیتابیس اختصاصی بسازید. اگر نام‌ها از اجرای قبلی باقی مانده‌اند، فقط همین دو دیتابیس disposable
را حذف و دوباره ایجاد کنید؛ دیتابیس `trd_bot` یا `trd_bot_test` را تغییر ندهید.

```bash
docker compose exec -T postgres dropdb --if-exists -U trd_bot trd_bot_v03_fresh_test
docker compose exec -T postgres dropdb --if-exists -U trd_bot trd_bot_v02_upgrade_test
docker compose exec -T postgres createdb -U trd_bot -O trd_bot trd_bot_v03_fresh_test
docker compose exec -T postgres createdb -U trd_bot -O trd_bot trd_bot_v02_upgrade_test

export P6_FRESH_DATABASE_URL='postgresql+psycopg://trd_bot:trd_bot_dev_password@127.0.0.1:5432/trd_bot_v03_fresh_test'
export P6_UPGRADE_DATABASE_URL='postgresql+psycopg://trd_bot:trd_bot_dev_password@127.0.0.1:5432/trd_bot_v02_upgrade_test'
```

Fresh database باید خالی بماند. فقط upgrade database را به head رسمی v0.2 برسانید:

```bash
TRD_BOT_DATABASE_URL="$P6_UPGRADE_DATABASE_URL" \
  python -m alembic upgrade 20260926_0017

TRD_BOT_DATABASE_URL="$P6_UPGRADE_DATABASE_URL" \
  python -m alembic current
```

خروجی command دوم باید revision `20260926_0017` را نشان دهد. اگر از restore واقعی v0.2 استفاده می‌کنید،
نسخه restoreشده باید همین revision را داشته باشد و حداقل دو row در مجموعه relations حفاظت‌شده
وجود داشته باشد.

## اجرای verification مرجع

ابتدا تغییرات P6-06 را commit کنید و مطمئن شوید `git status --short` خالی است. برای دیتابیس مصنوعی
خالی از flag زیر استفاده کنید تا یک Dataset و Experiment deterministic روی schema v0.2 ثبت شوند:

```bash
PYTHONPATH=src python scripts/verify_v0_3_installation.py \
  --fresh-database-url "$P6_FRESH_DATABASE_URL" \
  --upgrade-database-url "$P6_UPGRADE_DATABASE_URL" \
  --confirm-fresh-database trd_bot_v03_fresh_test \
  --confirm-upgrade-database trd_bot_v02_upgrade_test \
  --seed-upgrade-fixture \
  --environment-label macbook-pro-reference \
  --output /tmp/trd-bot-p6-06-installation-verification.json
```

برای یک copy بازیابی‌شده از دیتابیس واقعی v0.2، `--seed-upgrade-fixture` را حذف کنید. هیچ‌گاه runner
را روی دیتابیس اصلی یا تنها backup موجود اجرا نکنید؛ upgrade درجا و برگشت‌ناپذیر است.

Runner به‌ترتیب زیر عمل می‌کند:

1. output جدید، worktree clean، URLها و confirmationها را بررسی می‌کند؛
2. خالی بودن fresh schema و revision دقیق upgrade schema را پیش از هر migration بررسی می‌کند؛
3. در صورت درخواست، fixture دو-row را در یک transaction روی v0.2 درج می‌کند؛
4. fingerprintهای lineage را ثبت می‌کند؛
5. هر دو دیتابیس را با Alembic به `head` می‌رساند و `alembic check` اجرا می‌کند؛
6. schema نهایی را با metadata و inventory فریز‌شده مقایسه می‌کند؛
7. fingerprintهای قبل و بعد upgrade و no-live security inventory را ارزیابی می‌کند؛
8. report commit-bound و checksumدار را بدون overwrite می‌نویسد.

خروجی موفق باید `passed=true`، `failure_reasons=[]`، revision نهایی `20261020_0036`، تعداد 55
جدول و `release_security_boundary_passed=true` داشته باشد.

## بررسی Artifact

```bash
python - <<'PY'
from pathlib import Path
from trd_bot.release_installation import parse_release_installation_report

path = Path('/tmp/trd-bot-p6-06-installation-verification.json')
report = parse_release_installation_report(path.read_bytes())
print(f'passed={report.passed}')
print(f'commit_sha={report.commit_sha}')
print(f'report_checksum={report.report_checksum}')
print(f'fresh={report.fresh_install.after.migration_revision}')
print(f'upgrade={report.upgrade.after.migration_revision}')
PY
```

هر تغییر در row count، identity checksum، outcome یا report checksum هنگام parse رد می‌شود.

## گیت‌های کد

```bash
python -m pytest \
  tests/test_release_installation.py \
  tests/test_v0_3_documentation.py \
  tests/test_release_hardening.py \
  tests/test_release_version.py \
  -q

python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
python -m pytest -m integration -q
```

Frontend نیز باید روی همان SHA با `format:check`، `lint`، `typecheck`، `test -- --run` و `build`
سبز باشد. P6-06 جای CI یا smoke دستی API/UI را نمی‌گیرد؛ artifact آن یکی از ورودی‌های پذیرش نهایی
Phase 6 است.

## Cleanup

پس از ذخیره artifact و نتیجه gateها:

```bash
docker compose exec -T postgres dropdb --if-exists -U trd_bot trd_bot_v03_fresh_test
docker compose exec -T postgres dropdb --if-exists -U trd_bot trd_bot_v02_upgrade_test
unset P6_FRESH_DATABASE_URL P6_UPGRADE_DATABASE_URL

docker compose exec -T postgres psql -U trd_bot -d postgres -Atc \
  "SELECT datname FROM pg_database WHERE datname IN ('trd_bot_v03_fresh_test', 'trd_bot_v02_upgrade_test');"
```

command آخر نباید خروجی داشته باشد.

## معیار خروج P6-06

- [x] fresh و upgrade روی دیتابیس‌های مجزا و صریحاً تأییدشده اجرا می‌شوند.
- [x] preconditionهای empty schema و revision v0.2 قبل از mutation fail-closed هستند.
- [x] schema نهایی با metadata، Alembic head و drift check تطبیق داده می‌شود.
- [x] identity و content پنج relation اصلی lineage قبل و بعد ارتقا حفاظت می‌شود.
- [x] artifact commit-bound، sanitizeشده، checksumدار و tamper-resistant است.
- [x] no-live inventory بخشی از نتیجه installation است.
- [ ] اجرای مرجع PostgreSQL 17 روی SHA کامیت‌شده `passed=true` شود.
- [ ] backend، integration، frontend و CI روی همان SHA سبز شوند.

پس از بستن این گیت، مرحله مجاز بعدی `P6-07 — Final v0.3 Acceptance and Freeze` است.
