# TB2-025 — نامزد انتشار محلی v0.2.0

## تصمیم دامنه

این مرحله نسخهٔ `0.2.0` را برای استفادهٔ محلی آماده می‌کند. موارد زیر در این مرحله انجام نمی‌شوند:

- staging یا deploy روی سرور؛
- merge به `main` یا ساخت Pull Request؛
- ساخت یا push کردن tag؛
- انتشار GitHub Release؛
- قابلیت اختیاری TB2-022.

این موارد حذف نشده‌اند و فقط تا تصمیم صریح مالک مخزن deferred هستند. نامزد انتشار همچنان محدود به
`RESEARCH`، `BACKTEST`، `PAPER` و `SHADOW` است و قابلیت معاملهٔ زنده ندارد.

## مبنا و قرارداد نسخه

- مبنای این مرحله branch `feature/v0.3-strategy-foundation` روی commit
  `4113f897dfe91af1c79be6c72f4bff35c9a5f163` است.
- GitHub Actions run `36533943285` برای commit مبنا با نتیجهٔ `success` تمام شده است.
- نسخه باید در `pyproject.toml`، package پایتون، تنظیم پیش‌فرض API، `.env.example`،
  `frontend/package.json` و root package در lockfile برابر `0.2.0` باشد.
- `tests/test_release_version.py` واگرایی این منابع را fail می‌کند.
- مقدار صریح `TRD_BOT_APP_VERSION` در `.env` محلی بر تنظیم پیش‌فرض اولویت دارد؛ اگر `.env` قدیمی
  هنوز `0.1.0` دارد، آن را به `0.2.0` تغییر بده.

موفقیت CI مبنا شاهد TB2-024 است. خود TB2-025 فقط پس از اجرای گیت‌ها روی SHA تازهٔ حاصل از این پچ
قابل پذیرش است.

## استثناهای شناخته‌شدهٔ نامزد

صف durable مسیرهای import/refresh از provider و Optimization را پوشش می‌دهد. پردازش upload فایل
و مسیرهای legacy اجرای Experiment/Walk-Forward هنوز به‌طور کامل به worker منتقل نشده‌اند. این بدهی
از ماتریس TB2-024 پنهان نمی‌شود و برای استفادهٔ محلی باید به‌عنوان release exception پذیرفته یا پیش
از tag آینده در یک مرحلهٔ جداگانه بسته شود. این استثنا مجوز افزودن معاملهٔ زنده نیست.

## راه‌اندازی امن روی macOS

این مسیر volume فعلی PostgreSQL را حذف نمی‌کند. از ریشهٔ مخزن:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp -n .env.example .env
docker compose up -d postgres
docker compose ps
python -m alembic upgrade head
python -m alembic check
```

اگر `.env` از قبل وجود دارد، `cp -n` آن را بازنویسی نمی‌کند. URL دیتابیس و
`TRD_BOT_APP_VERSION=0.2.0` را دستی کنترل کن. روی دیتابیس توسعه‌ای که باید حفظ شود
`docker compose down -v` یا `alembic downgrade base` اجرا نکن.

سه terminal محلی لازم است:

```bash
# terminal 1
source .venv/bin/activate
python -m uvicorn trd_bot.main:app --reload
```

```bash
# terminal 2
source .venv/bin/activate
python scripts/run_background_worker.py
```

```bash
# terminal 3
cd frontend
npm ci
npm run dev
```

سپس `http://127.0.0.1:3000` را باز کن و پاسخ
`http://127.0.0.1:8000/api/v1/health` را کنترل کن. پاسخ health باید نسخهٔ `0.2.0` داشته باشد.

برای بررسی UI با دادهٔ مصنوعی و فقط روی PostgreSQL محلی development می‌توان اجرا کرد:

```bash
source .venv/bin/activate
python scripts/seed_demo_data.py
python scripts/seed_monitoring_demo.py
```

## ترتیب پذیرش نامزد

ابتدا تست متمرکز نسخه و انتشار:

```bash
python -m pytest tests/test_release_version.py tests/test_health.py \
  tests/test_release_security_boundary.py tests/test_mvp_acceptance.py -q
```

سپس backend:

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
```

PostgreSQL و integration بدون پاک‌کردن volume توسعه:

```bash
docker compose up -d postgres
docker compose ps
python -m alembic upgrade head
python -m alembic check
python -m pytest -m integration -v
```

Frontend:

```bash
cd frontend
npm ci
npm run format:check
npm run lint
npm run test
npm run build
cd ..
```

پذیرش دستی شامل Historical Import از Nobitex مستقیم و Kraken با VPN، مشاهدهٔ پیشرفت worker،
restart/reclaim یک job آزمایشی، و بازبینی صفحه‌های فارسی و انگلیسی Dataset، Experiment،
Optimization، Candidate، Risk، Portfolio، Position و Monitoring است. هیچ درخواست credential یا
عملیات سفارش نباید در Network مرورگر دیده شود.

## معیار بستن مرحله

1. همهٔ منابع نسخه و پاسخ health مقدار `0.2.0` داشته باشند.
2. گیت‌های backend، PostgreSQL/integration و frontend روی یک SHA تمیز موفق باشند.
3. GitHub Actions همان SHA با سه job موفق ثبت شود.
4. API، worker و frontend در اجرای محلی هم‌زمان قابل استفاده باشند.
5. پذیرش Nobitex مستقیم و Kraken با VPN و restart worker ثبت شود.
6. مرز no-live-trading حفظ و TB2-022 همچنان deferred باشد.
7. release exception مسیرهای request-bound بالا صریحاً پذیرفته یا برای patch بعدی رد شود.
8. هیچ deploy، merge، tag یا انتشار بیرونی بدون تصمیم جداگانه انجام نشده باشد.

## قالب ثبت شاهد

```text
Stage: TB2-025
Branch: feature/v0.3-strategy-foundation
Commit: <full SHA after applying this patch>
Worktree: clean | <known files>
Version consistency: pass | fail
Focused release tests: pass | fail
Backend full gate: pass | fail
PostgreSQL/migrations: pass | fail
Frontend full gate: pass | fail
Local API/worker/frontend smoke: pass | fail
Nobitex direct acceptance: pass | fail
Kraken VPN acceptance: pass | fail
Restart/Monitoring acceptance: pass | fail
Security inventory: pass | fail
Request-bound job exception: accepted | rejected
GitHub Actions run: <URL or run ID>
Server deployment: deferred
Tag/GitHub Release: deferred
Notes: <warnings, skipped tests, failure evidence>
```

## انتشار بعدی، فقط با تصمیم جداگانه

پس از قبولی کامل نامزد می‌توان در مرحله‌ای جداگانه دربارهٔ merge، tag امضاشده و GitHub Release
تصمیم گرفت. تا آن زمان `0.2.0` یک نامزد محلی untagged است و هیچ فرمان deploy یا push tag بخشی از
این مرحله نیست.
