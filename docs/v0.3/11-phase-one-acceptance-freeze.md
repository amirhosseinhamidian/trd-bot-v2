# P1-07 — پذیرش نهایی و Freeze مرحلهٔ اول

وضعیت: **گیت پیاده‌سازی‌شده؛ ثبت evidence روی SHA مالک مخزن باقی است**

تاریخ تصمیم: `2026-10-11`

این مرحله قابلیت محصولی یا migration تازه اضافه نمی‌کند. هدف، اثبات بسته‌شدن بدهی‌های P1 روی یک
commit تمیز پیش از ورود به P2 است. نتیجه فقط زمانی پذیرفته می‌شود که گیت‌های محلی، چرخهٔ کامل
PostgreSQL، smoke دستی و GitHub Actions همگی به همان SHA اشاره کنند.

## ماتریس پذیرش

| gate | شاهد لازم |
| --- | --- |
| `repository_contract` | version، مرز امنیت انتشار، MVP و minimum export baseline |
| `backend` | Ruff format/lint، mypy و تمام تست‌های غیر integration |
| `migration_cycle` | `upgrade head -> downgrade base -> upgrade head -> alembic check` |
| `postgresql_recovery` | تمام integration testها، race/reclaim صف و lifecycleهای durable |
| `frontend` | format، lint، typecheck، test و production build |
| GitHub Actions | run موفق با `head_sha` دقیقاً برابر commit محلی |
| manual smoke | API/worker/frontend، restart workload، Monitoring recovery و Network امنیتی |

تست PostgreSQL این مرحله علاوه بر race/recovery قبلی، عبور واقعی فایل Dataset از مرز request به
stage ماندگار، worker مستقل، Dataset نهایی و پاک‌شدن stage مصرف‌شده را کنترل می‌کند.

## مرز ایمنی دیتابیس

اسکریپت `scripts/verify_v0_3_phase_one.py` fail-closed است:

- فقط URL با dialect PostgreSQL و نام دقیق دیتابیس `trd_bot_test` را می‌پذیرد؛
- برای `downgrade base` تأیید صریح `trd_bot_test` می‌خواهد؛
- روی detached HEAD یا worktree دارای تغییر اجرا نمی‌شود؛
- URL دیتابیس و credential را در evidence ثبت نمی‌کند؛
- فایل خروجی موجود را بازنویسی نمی‌کند؛
- فقط GitHub Actions با conclusion برابر `success` و SHA برابر commit جاری را می‌پذیرد.

اجرای این چرخه روی دیتابیس development، benchmark یا هر دیتابیس دارای دادهٔ قابل نگهداری ممنوع
است.

## ساخت دیتابیس یک‌بارمصرف روی macOS

پورت `55434` عمداً از پورت benchmark قبلی جدا است:

```bash
docker run --name trd-bot-p1-acceptance-db17 \
  -e POSTGRES_USER=trd_p1 \
  -e POSTGRES_PASSWORD=trd_p1_password \
  -e POSTGRES_DB=trd_bot_test \
  -p 55434:5432 \
  -d postgres:17-alpine

docker exec trd-bot-p1-acceptance-db17 \
  pg_isready -U trd_p1 -d trd_bot_test

export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://trd_p1:trd_p1_password@localhost:55434/trd_bot_test'
```

## smoke دستی پیش از freeze

روی همان commit و با stack محلی، این چهار دسته باید واقعاً بررسی و فقط سپس با `pass` ثبت شوند:

1. API، worker و frontend هم‌زمان بالا بیایند و health/UI قابل استفاده باشند.
2. یک Dataset file import و یک Experiment/Walk-Forward durable اجرا شوند؛ worker میان کار restart
   شود و job تکراری یا نتیجهٔ گم‌شده ایجاد نشود.
3. Monitoring ابتدا lease منقضی را نشان دهد و پس از reclaim وضعیت تازه و نتیجه را نمایش دهد.
4. Network و route inventory هیچ live order، credential، wallet، deposit یا withdrawal نداشته
   باشند.

## ساخت evidence نهایی

پس از push و سبزشدن هر سه job در GitHub Actions، SHA و URL همان run را بردار:

```bash
P1_SHA=$(git rev-parse HEAD)

PYTHONPATH=src python scripts/verify_v0_3_phase_one.py \
  --database-url "$TRD_BOT_TEST_DATABASE_URL" \
  --confirm-destructive-migration-cycle trd_bot_test \
  --github-actions-run-url 'https://github.com/OWNER/REPOSITORY/actions/runs/RUN_ID' \
  --github-actions-head-sha "$P1_SHA" \
  --github-actions-conclusion success \
  --local-stack-smoke pass \
  --durable-restart-smoke pass \
  --monitoring-recovery-smoke pass \
  --security-network-smoke pass \
  --environment-label macbook-pro-reference \
  --output artifacts/p1-07/phase-one-acceptance.json
```

فرمان تمام خروجی تست‌ها را در terminal نشان می‌دهد و در پایان یک record با schema
`phase-one-acceptance-record-v1` می‌نویسد. exit code صفر و مقدار زیر شرط ورود به P2 هستند:

```json
{
  "failed_gates": [],
  "ready_to_enter_phase_two": true
}
```

## معیار خروج P1-07

- [x] runner واحد و fail-closed برای تمام گیت‌های خودکار وجود دارد.
- [x] migration cycle فقط روی `trd_bot_test` و با تأیید مخرب اجرا می‌شود.
- [x] lifecycle فایل Dataset روی PostgreSQL واقعی به integration gate افزوده شده است.
- [x] evidence credential دیتابیس را ذخیره نمی‌کند و tamper derived state را رد می‌کند.
- [x] CI و commit محلی باید SHA یکسان داشته باشند.
- [ ] اجرای GitHub Actions روی SHA نهایی مالک مخزن ثبت شود.
- [ ] smoke دستی چهارگانه روی همان SHA ثبت شود.
- [ ] record نهایی `ready_to_enter_phase_two=true` تولید شود.

تا بسته‌شدن سه مورد آخر، Phase 1 از نظر کد آماده است اما **freeze نشده** و شروع P2 مجاز نیست.
