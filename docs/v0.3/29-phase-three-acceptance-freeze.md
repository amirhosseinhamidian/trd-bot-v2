# P3-10 — Phase Three Acceptance and Freeze

وضعیت: **گیت پیاده‌سازی‌شده؛ ثبت evidence روی SHA نهایی مالک مخزن باقی است**

تاریخ تصمیم: `2026-10-17`

مبنای کد: P3-09 در commit محلی
`8d8d666`

این مرحله قابلیت محصولی یا migration تازه اضافه نمی‌کند. هدف، اثبات کامل Market Context Foundation
در محدودهٔ `Crypto Spot / public read-only` است. Freeze فقط وقتی پذیرفته می‌شود که P2، benchmarkهای
P3، تمام گیت‌های محلی، smoke دستی و GitHub Actions به یک candidate SHA متصل باشند.

## 1. ماتریس پذیرش

| Gate | شاهد لازم |
| --- | --- |
| prior freeze | record پذیرفته‌شده و checksummed مربوط به P2؛ commit آن ancestor کاندیدا باشد |
| golden benchmark | سه سناریو، حداقل 30 sample، fingerprint ثابت و runtime در budget روی همان SHA |
| background jobs | fixture v2، queue واقعی PostgreSQL و workload واقعی context روی همان SHA |
| `repository_contract` | version، security و parserهای tamper-evident P0 تا P3 |
| `market_context_contract` | contracts، persistence، alignment، features، regime، jobs، Monitoring، API/UI و benchmark |
| `backend` | Ruff format/lint، mypy و تمام تست‌های غیر integration |
| `migration_cycle` | `upgrade head → downgrade base → upgrade head → alembic check` |
| `postgresql_resilience` | race، recovery، dedupe و durability روی PostgreSQL 17 |
| `frontend` | format، lint، typecheck، test و production build |
| manual smoke | stack، generation/UI، stale fail-closed، restart/dedupe، Monitoring و security inventory |
| GitHub Actions | run موفق با `head_sha` دقیقاً برابر candidate |

## 2. ویژگی fail-closed

اسکریپت `scripts/verify_v0_3_phase_three.py` موارد زیر را الزام می‌کند:

- HEAD روی branch باشد و worktree در شروع کاملاً تمیز باشد؛
- دیتابیس فقط PostgreSQL با نام دقیق `trd_bot_test` باشد؛
- چرخهٔ مخرب migration تأیید صریح داشته باشد؛
- P2 پذیرفته شده و commit آن ancestor کاندیدا باشد؛
- هر دو benchmark با SHA و environment کاندیدا منطبق و حداکثر 365 روزه باشند؛
- Golden fixture، feature set و regime policy checksumهای canonical داشته باشند؛
- هر سه سناریوی Golden پذیرفته و زیر runtime budget باشند؛
- background evidence کامل، synthetic و دارای reference دقیق
  `background-job-workloads-v2+postgresql-queue-v1` باشد؛
- workload context حداقل 20 اجرای موفق، صفر failure، 56 window و پنج feature داشته باشد؛
- queue wait و runtime p95 در budget فریز‌شده باشند؛
- CI موفق و SHA آن برابر HEAD باشد؛
- derived outcomeهای دست‌کاری‌شده هنگام parse رد شوند؛
- فایل خروجی موجود overwrite نشود.

## 3. دیتابیس یک‌بارمصرف پذیرش

این دیتابیس با دیتابیس benchmark P3-09 متفاوت است و migration cycle تمام محتوای آن را پاک می‌کند:

```bash
docker run --name trd-bot-p3-acceptance-db17 \
  -e POSTGRES_USER=trd_p3 \
  -e POSTGRES_PASSWORD=trd_p3_password \
  -e POSTGRES_DB=trd_bot_test \
  -p 55437:5432 \
  -d postgres:17-alpine

docker exec trd-bot-p3-acceptance-db17 \
  pg_isready -U trd_p3 -d trd_bot_test

export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://trd_p3:trd_p3_password@localhost:55437/trd_bot_test'
export TRD_BOT_DATABASE_URL="$TRD_BOT_TEST_DATABASE_URL"

PYTHONPATH=src python -m alembic upgrade head
```

هیچ دیتابیس development یا دارای دادهٔ قابل نگهداری نباید به verifier داده شود.

## 4. ساخت evidence روی candidate نهایی

ابتدا P3-10 را commit و push کنید. گزارش ساخته‌شده روی commit P3-09 برای freeze نهایی معتبر نیست؛
هر دو benchmark باید روی SHA جدید دوباره اجرا شوند:

```bash
P3_SHA=$(git rev-parse HEAD)

PYTHONPATH=src caffeinate -i python scripts/benchmark_market_context.py \
  --samples-per-scenario 30 \
  --warmup-iterations 2 \
  --environment-label macbook-pro-reference \
  --commit-sha "$P3_SHA" \
  --output /tmp/trd-bot-p3-market-context-golden-final.json
```

برای background capacity از PostgreSQL benchmark جداگانهٔ بخش P3-09 استفاده کنید:

```bash
PYTHONPATH=src caffeinate -i python scripts/benchmark_postgresql_capacity.py \
  --database-url "$TRD_BOT_P3_BENCHMARK_DATABASE_URL" \
  --event-count 100000 \
  --job-count 250 \
  --query-samples 200 \
  --environment-label macbook-pro-reference \
  --commit-sha "$P3_SHA" \
  --output /tmp/trd-bot-p3-postgresql-capacity-final.json

PYTHONPATH=src caffeinate -i python scripts/benchmark_background_job_workloads.py \
  --queue-report /tmp/trd-bot-p3-postgresql-capacity-final.json \
  --samples-per-kind 20 \
  --warmup-iterations 2 \
  --output /tmp/trd-bot-p3-background-jobs-capacity-final.json
```

مقدار `TRD_BOT_P3_BENCHMARK_DATABASE_URL` باید به دیتابیس یک‌بارمصرف P3-09 با نام شامل `benchmark`
اشاره کند، نه `trd_bot_test` پذیرش.

## 5. smoke دستی پیش از freeze

این شش مورد باید روی همان commit واقعاً مشاهده و فقط سپس با `pass` ثبت شوند.

### 5.1 Stack محلی

API، worker و frontend را با دیتابیس پذیرش بالا بیاورید. این endpointها و UI باید پاسخ دهند:

```bash
curl -sS --fail-with-body http://127.0.0.1:8000/api/v1/health | python -m json.tool
curl -sS --fail-with-body http://127.0.0.1:8000/api/v1/monitoring/market-context | python -m json.tool
curl -sS --fail-with-body 'http://127.0.0.1:8000/api/v1/market-context?limit=12&offset=0' | python -m json.tool
curl -sS -o /dev/null -w 'UI HTTP %{http_code}\n' http://127.0.0.1:3000/fa/market-context
```

### 5.2 ساخت context قابل‌مصرف

بعد از دقیقهٔ دوم ساعت، fixture synthetic را روی boundary فعلی stage و job ماندگار را enqueue کنید:

```bash
PYTHONPATH=src python - <<'PY'
from datetime import UTC, datetime

from trd_bot.db import (
    SqlAlchemyMarketContextEvaluationEnqueuer,
    SqlAlchemyMarketDataEventStore,
    get_session_factory,
)
from trd_bot.domain.market_data import Timeframe
from trd_bot.market_context import (
    MarketContextGoldenScenarioId,
    build_market_context_golden_windows,
    floor_market_context_boundary,
    market_context_golden_fixture_v1,
)

now = datetime.now(UTC)
as_of = floor_market_context_boundary(now, Timeframe.HOUR_1)
fixture = market_context_golden_fixture_v1()
windows = build_market_context_golden_windows(
    MarketContextGoldenScenarioId.TRENDING_UP_LOW,
    as_of=as_of,
)
factory = get_session_factory()

with factory.begin() as session:
    store = SqlAlchemyMarketDataEventStore(session)
    for window in windows:
        store.stage_window_version(window)

with factory.begin() as session:
    result = SqlAlchemyMarketContextEvaluationEnqueuer(session).enqueue(
        source=fixture.source,
        pair=fixture.pair,
        as_of=as_of,
        requested_at=now,
    )
    print("created:", result.created)
    print(result.job.model_dump_json(indent=2))
PY
```

پس از اجرای worker، catalog باید `consumable=true` و UI باید trend، volatility، confidence، زمان‌ها
و Advanced evidence/lineage را بدون خطا نمایش دهد.

### 5.3 Restart، reclaim و dedupe

برای تست دقیق، job بالا را پیش از اجرای worker با lease کوتاه claim کنید، process را متوقف نگه دارید،
پس از انقضای lease worker را اجرا کنید و سپس همان intent را دوباره enqueue کنید. نتیجهٔ پذیرفته‌شده:

- همان job با attempt بعدی reclaim و `succeeded` شود؛
- فقط یک manifest، یک feature snapshot و یک assessment برای intent باقی بماند؛
- enqueue تکراری `created=false` و همان job/result را برگرداند.

### 5.4 Stale context

یک boundary قدیمی fixture را stage/evaluate کنید و detail assessment آن را بخوانید. assessment باید
برای audit قابل مشاهده ولی `consumable=false` باشد و حداقل علت `boundary_mismatch` را داشته باشد.

### 5.5 Monitoring recovery

در زمان lease منقضی Monitoring باید وضعیت job/freshness ناسالم را نشان دهد و پس از reclaim به نتیجهٔ
تازه و backlog بازیابی‌شده برسد. تعداد queued/running job و freshness باید با وضعیت واقعی صف و آخرین
assessment منطبق باشد.

### 5.6 Security inventory

OpenAPI، routeها، Network مرورگر و payloadها را بررسی کنید. هیچ credential، exchange account، wallet،
deposit، withdrawal، live order یا مسیر write به صرافی نباید وجود داشته باشد.

## 6. اجرای verifier نهایی

پس از سبزشدن GitHub Actions همان SHA و تکمیل smokeها:

```bash
P3_SHA=$(git rev-parse HEAD)

PYTHONPATH=src python scripts/verify_v0_3_phase_three.py \
  --database-url "$TRD_BOT_TEST_DATABASE_URL" \
  --confirm-destructive-migration-cycle trd_bot_test \
  --golden-benchmark-report /tmp/trd-bot-p3-market-context-golden-final.json \
  --background-jobs-capacity-report /tmp/trd-bot-p3-background-jobs-capacity-final.json \
  --github-actions-run-url 'https://github.com/OWNER/REPOSITORY/actions/runs/RUN_ID' \
  --github-actions-head-sha "$P3_SHA" \
  --github-actions-conclusion success \
  --local-stack-smoke pass \
  --context-generation-ui-smoke pass \
  --stale-context-smoke pass \
  --worker-restart-smoke pass \
  --monitoring-recovery-smoke pass \
  --security-network-smoke pass \
  --environment-label macbook-pro-reference \
  --output artifacts/p3-10/phase-three-acceptance.json
```

نتیجهٔ قابل پذیرش:

```json
{
  "failed_gates": [],
  "golden": {"passed": true},
  "background_jobs": {"passed": true},
  "ready_to_freeze_phase_three": true
}
```

## 7. معیار خروج P3-10

- [x] verifier واحد و fail-closed برای تمام گیت‌های P3 وجود دارد.
- [x] P2 با checksum، تصمیم پذیرش و ancestry دوباره اعتبارسنجی می‌شود.
- [x] Golden و background evidence مستقل از derived state ارزیابی می‌شوند.
- [x] SHA، environment و تازگی هر دو benchmark با candidate تطبیق داده می‌شود.
- [x] migration cycle فقط روی `trd_bot_test` و با تأیید مخرب اجرا می‌شود.
- [x] parser تمام outcomeهای مشتق‌شدهٔ دست‌کاری‌شده را رد می‌کند.
- [x] scope امنیتی public read-only صریح باقی می‌ماند.
- [ ] دو benchmark نهایی روی SHA مالک مخزن پذیرفته شوند.
- [ ] GitHub Actions موفق همان SHA ثبت شود.
- [ ] smoke دستی شش‌گانه روی همان SHA ثبت شود.
- [ ] record نهایی `ready_to_freeze_phase_three=true` تولید و commit شود.

تا بسته‌شدن چهار مورد آخر، Phase 3 از نظر کد آماده است اما هنوز freeze نشده است.
