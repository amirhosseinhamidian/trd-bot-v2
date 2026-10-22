# TB2-024 — گیت QA، migration، recovery و امنیت

## دامنه مرحله

این مرحله قابلیت محصولی تازه اضافه نمی‌کند. هدف آن تبدیل معیارهای انتشار به گیت‌های قابل تکرار است:

- چرخه کامل Alembic روی PostgreSQL خالی: `base -> head -> base -> head`؛
- race واقعی صف با دو session مستقل PostgreSQL؛
- reclaim شدن lease منقضی پس از توقف worker و رد worker قدیمی؛
- پذیرش E2E مسیر Candidate/Portfolio/Position موجود؛
- inventory خودکار API، OpenAPI، frontend و providerها برای حفظ مرز تحقیق و شبیه‌سازی.

`TB2-022` همچنان deferred است. در این مرحله migration یا endpoint تازه‌ای اضافه نمی‌شود.

## قرارداد migration

CI پایگاه `trd_bot_test` خالی را تا `head` بالا می‌برد، کل زنجیره را تا `base` پایین می‌آورد و دوباره
تا `head` بازسازی می‌کند. سپس `alembic check` و integration testها اجرا می‌شوند. این چرخه فقط روی
پایگاه آزمایشی مجاز است؛ اجرای `downgrade base` روی دیتابیس توسعه یا دادهٔ قابل نگهداری ممنوع است.

قبولی migration نیازمند این موارد است:

1. تمام revisionها یک زنجیره خطی و دارای `downgrade()` باشند.
2. هر دو اجرای `upgrade head` موفق باشند.
3. `alembic check` بعد از بازسازی نهایی schema معوق گزارش نکند.
4. integration testها بعد از چرخه کامل روی schema بازسازی‌شده اجرا شوند.

## قرارداد race و recovery صف

آزمون PostgreSQL مرحله دو enqueue هم‌زمان با یک `(kind, idempotency_key)` می‌فرستد. دقیقاً یک
درخواست باید رکورد بسازد و هر دو caller باید همان `job_id` را دریافت کنند. سپس دو worker هم‌زمان
برای claim رقابت می‌کنند و فقط یکی مالک lease می‌شود. پس از انقضای lease، session تازه job را reclaim
می‌کند، `attempt_count` افزایش می‌یابد و worker قبلی اجازه ثبت success ندارد.

این آزمون از `SELECT ... FOR UPDATE SKIP LOCKED` و unique constraint واقعی PostgreSQL استفاده
می‌کند و با SQLite جایگزین نمی‌شود.

## قرارداد امنیت انتشار

گیت `test_release_security_boundary.py` باید با هر route یا schema تازه دوباره اجرا شود:

- segmentهای live order، trading، account صرافی، wallet، deposit و withdrawal در API و صفحه‌های
  frontend ممنوع‌اند؛
- schemaهای OpenAPI نباید ورودی‌هایی مانند API key، secret، password، passphrase یا token بپذیرند؛
- تمام adapterهای catalog انتشار باید شناسه `-public` و `requires_credentials=false` داشته باشند.

واژه‌های پژوهشی داخل مدل Candidate مانند `trade_plan` به‌تنهایی نقض دامنه نیستند؛ گیت روی سطح
عملیات عمومی API و UI تمرکز دارد. گسترش allowlist ممنوع فقط با تصمیم جدید دامنه انجام می‌شود.

## ترتیب اجرای مالک مخزن

ابتدا تست‌های محدود مرحله را از ریشه مخزن اجرا کن:

```bash
python -m pytest tests/test_release_security_boundary.py tests/test_mvp_acceptance.py -q
python -m pytest \
  tests/test_postgresql_integration.py::test_postgresql_background_job_races_and_expired_lease_recovery \
  -m integration -v
```

سپس گیت کامل backend را اجرا کن:

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
```

چرخه migration فقط روی `trd_bot_test` خالی یا قابل حذف اجرا شود:

```bash
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
python -m alembic check
python -m pytest -m integration -v
```

گیت frontend:

```bash
cd frontend
npm run format:check
npm run lint
npm run test
npm run build
cd ..
```

## پذیرش دستی باقی‌مانده

موارد وابسته به محیط واقعی به CI آفلاین سپرده نمی‌شوند:

1. Nobitex با اتصال مستقیم و Kraken با VPN health-check و Historical Import شوند.
2. worker هنگام Import و Optimization متوقف و دوباره اجرا شود؛ progress و result پس از restart باقی
   بمانند.
3. Monitoring ابتدا lease منقضی را `stuck` نشان دهد و پس از reclaim وضعیت تازه را نمایش دهد.
4. صفحه‌های فارسی و انگلیسی Dataset، Experiment، Candidate، Risk، Portfolio، Position و Monitoring
   با داده پذیرش بازبینی شوند.
5. route inventory و Network مرورگر هیچ درخواست سفارش، حساب صرافی، credential یا withdrawal نشان
   ندهد.

## قالب ثبت شاهد

```text
Stage: TB2-024
Branch: feature/v0.3-strategy-foundation
Commit: <full SHA>
Worktree: clean | <known files>
Focused release tests: pass | fail
Migration cycle: pass | fail
PostgreSQL race/recovery: pass | fail
Backend full gate: pass | fail
Frontend full gate: pass | fail
Nobitex direct acceptance: pass | fail
Kraken VPN acceptance: pass | fail
Restart/Monitoring acceptance: pass | fail
Security inventory: pass | fail
GitHub Actions run: <URL or run ID>
Notes: <warnings, skipped tests, failure evidence>
```

تا قبل از ثبت خروجی همین SHA، این مرحله «گیت آماده اجرا» است و نتیجه عملکردی آن تأییدشده محسوب
نمی‌شود. نامزد انتشار و tag در TB2-025 ساخته می‌شوند.
