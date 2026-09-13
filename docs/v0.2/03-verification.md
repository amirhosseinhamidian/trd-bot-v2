# TB2-002 — راهنمای راستی‌آزمایی نسخهٔ دوم

این راهنما برای اجرای گیت‌های یکسان روی checkout محلی و GitHub Actions است. نتیجه فقط زمانی به یک مرحله نسبت داده می‌شود که branch، commit SHA و خروجی هر گیت ثبت شده باشند. وجود workflow یا تست به‌تنهایی به معنی سبز بودن آن نیست.

## دامنهٔ خودکار CI

`.github/workflows/ci.yml` در این رویدادها اجرا می‌شود:

- هر push به `main`، `feature/**`، `fix/**` و `bugfix/**`؛
- هر pull request با مقصد `main`؛
- اجرای دستی با `workflow_dispatch`.

برنچ فعلی `feature/v0.3-strategy-foundation` با الگوی `feature/**` منطبق است. سه job با نام ثابت باید نتیجهٔ موفق داشته باشند:

1. `Backend quality and tests`
2. `PostgreSQL migrations and integration tests`
3. `Frontend quality, tests, and build`

لغوشدن اجرای قدیمی پس از push جدید، به دلیل `concurrency` طبیعی است؛ فقط اجرای مربوط به آخرین SHA معیار است.

## ثبت مبنا پیش از اجرا

از ریشهٔ مخزن اجرا و خروجی را همراه گزارش مرحله نگه دارید:

```bash
git status --short --branch
git rev-parse HEAD
python --version
node --version
npm --version
docker --version
docker compose version
```

پیش‌نیازها Python 3.12 یا بالاتر، Node.js 22 یا بالاتر، Docker و Docker Compose هستند. اگر worktree تغییرات دیگری دارد، خروجی تست را به‌عنوان شاهد یک patch مستقل ثبت نکنید.

## گیت backend

در virtual environment پروژه و از ریشهٔ مخزن:

```bash
python -m pip install -e ".[dev]"
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
```

هر فرمان باید status صفر داشته باشد. warning یا تست skipped باید در گزارش مرحله نوشته شود، حتی اگر فرمان موفق باشد.

## گیت PostgreSQL

برای بررسی معمول محلی، PostgreSQL توسعه را بدون حذف volume بالا بیاورید:

```bash
cp -n .env.example .env
docker compose up -d postgres
docker compose ps
python -m alembic upgrade head
python -m alembic check
python -m pytest -m integration -v
```

سرویس `postgres` باید healthy باشد. `alembic check` باید نبود migration معوق را گزارش کند و همهٔ integration testها باید status صفر داشته باشند.

این مسیر اثبات migration-from-zero نیست اگر volume قبلاً داده داشته باشد. برای TB2-002، job مستقل PostgreSQL در CI پایگاه دادهٔ تازه می‌سازد و شاهد migration از صفر است. فرمان `docker compose down -v` دادهٔ PostgreSQL محلی را حذف می‌کند و جزو بررسی معمول این مرحله نیست.

## گیت frontend

از پوشهٔ `frontend`:

```bash
npm ci
npm run format:check
npm run lint
npm run test
npm run build
```

هر پنج فرمان باید status صفر داشته باشند. build باید با `NEXT_PUBLIC_API_BASE_URL` معتبر انجام شود؛ CI مقدار `http://127.0.0.1:8000` را برای build تعیین می‌کند.

## بررسی نتیجهٔ CI

پس از push، اجرای workflow مربوط به SHA ثبت‌شده را باز کنید و این موارد را کنترل کنید:

- event باید `push` یا `pull_request` مورد انتظار باشد؛
- head branch و commit SHA باید با گزارش محلی یکسان باشند؛
- هر سه job بالا باید success باشند؛
- اجرای cancelled یا نتیجهٔ workflow قدیمی، شاهد آخرین patch نیست؛
- اگر job شکست خورد، نام job، نام step و بخش خطای log را بدون secret ثبت کنید.

برای فعال‌سازی branch protection در آینده، نام همین سه job به‌عنوان required status check استفاده شود. تغییر نام jobها باید آگاهانه باشد، چون ruleهای محافظت‌شده به نام check وابسته‌اند.

## قالب نتیجهٔ هر TB2

```text
Stage: TB2-XXX
Branch: feature/v0.3-strategy-foundation
Commit: <full SHA>
Worktree: clean | <known files>
Backend: pass | fail | not required
PostgreSQL/migrations: pass | fail | not required
Frontend: pass | fail | not required
Manual acceptance: pass | fail | not required
GitHub Actions run: <URL or run ID>
Notes: <warnings, skipped tests, failure evidence>
```

یک مرحله فقط با تست‌های متناسب با دامنهٔ خودش، بررسی دستی لازم و CI مربوط به همان SHA بسته می‌شود. گیت کامل migration-from-zero و E2E نامزد انتشار در TB2-024 دوباره اجرا خواهد شد.
