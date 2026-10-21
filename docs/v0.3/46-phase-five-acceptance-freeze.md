# P5-09 — benchmark، پذیرش و Freeze نهایی Phase 5

وضعیت: **گیت پیاده‌سازی‌شده؛ ثبت evidence روی SHA نهایی مالک مخزن باقی است**

این مرحله قابلیت محصولی، migration یا endpoint تازه اضافه نمی‌کند. هدف آن اثبات end-to-end زنجیرهٔ
`Market Context → Strategy → Candidate → Risk → Portfolio Intelligence` و فریز صریح Phase 5 است.
مرز محصول همچنان `Crypto Spot / public read-only / Research-Shadow-Paper` است؛ پیشنهادهای Risk و
Portfolio فقط evidence آفلاین هستند و هیچ سفارش واقعی، credential صرافی یا مدیریت دارایی واقعی مجاز
نیست.

## ماتریس پذیرش

| Gate | شاهد لازم |
|---|---|
| prior freeze | record پذیرفته‌شده P4، checksum معتبر و commit آن ancestor کاندیدا باشد |
| decision benchmark | حداقل ۱۰۰ sample، یک fingerprint قطعی و p95 حداکثر ۲۵ms روی همان SHA |
| repository contract | security boundary و parserهای tamper-evident فریز P4/P5 |
| decision contract | قرارداد، persistence، worker، Strategy، Candidate، Risk، Portfolio و API |
| backend | Ruff format/lint، mypy و تمام تست‌های non-integration |
| migration cycle | `upgrade head → downgrade base → upgrade head → alembic check` |
| PostgreSQL resilience | تمام integration testها روی PostgreSQL 17 یک‌بارمصرف |
| frontend | format، lint، typecheck، test و production build |
| manual smoke | شش مشاهدهٔ end-to-end روی همان SHA |
| GitHub Actions | run موفق با `head_sha` دقیقاً برابر candidate |

## benchmark قطعی Decision Pipeline

Fixture ثابت BTC/USDT یک Context مصرف‌پذیر، Strategy فعال SMA، Candidate پذیرفته‌شده، Risk sizing و
Portfolio خالی Shadow می‌سازد. هر sample هر چهار stage را بدون clock، network، account یا mutation
Portfolio اجرا می‌کند. fingerprint نهایی checksum رکوردها و outcomeهای چهار stage را pin می‌کند.

checksumهای policyهای Compatibility، Candidate، Risk و Portfolio نیز در report ثبت می‌شوند. تغییر
fixture، policy یا خروجی stage بدون تغییر evidence قابل پنهان‌کردن نیست.

پس از commit کردن P5-09، benchmark را روی SHA نهایی اجرا کنید:

```bash
P5_SHA=$(git rev-parse HEAD)

PYTHONPATH=src python scripts/benchmark_decision_pipeline.py \
  --samples 1000 \
  --commit-sha "$P5_SHA" \
  --environment-label macbook-pro-reference \
  --output /tmp/trd-bot-p5-decision-benchmark-final.json
```

Benchmark فقط روی worktree تمیز اجرا می‌شود، فایل موجود را overwrite نمی‌کند و در صورت شکست با کد ۲
خارج می‌شود.

## دیتابیس یک‌بارمصرف پذیرش

چرخه migration تمام محتوای دیتابیس را پاک می‌کند؛ فقط دیتابیس دقیق `trd_bot_test` پذیرفته می‌شود:

```bash
docker run --name trd-bot-p5-09-acceptance-db17 \
  -e POSTGRES_USER=trd_p5 \
  -e POSTGRES_PASSWORD=trd_p5_password \
  -e POSTGRES_DB=trd_bot_test \
  -p 55440:5432 \
  -d postgres:17-alpine

export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://trd_p5:trd_p5_password@localhost:55440/trd_bot_test'
export TRD_BOT_DATABASE_URL="$TRD_BOT_TEST_DATABASE_URL"
PYTHONPATH=src python -m alembic upgrade head
```

## Smoke دستی روی candidate

هر شش مورد باید واقعاً مشاهده و سپس با `pass` ثبت شوند:

1. **Strategy/Signal/Candidate lineage:** evidence صفحه‌های موجود به Dataset، Context، Strategy و
   policy همان evaluation متصل باشد و stage ناقص جعل نشود.
2. **Risk fail-closed:** Context stale/unavailable، confidence ناکافی، incompatibility یا policy limit
   به رد/تعویق همراه policy version، checksum و reason code منجر شود.
3. **Paper/Shadow Portfolio:** exposure، concentration، correlation، scenario، اثر Candidate و exit
   recommendation نمایش داده شود؛ مشاهده یا ارزیابی aggregate را mutate نکند.
4. **Worker recovery:** lease منقضی reclaim شود و retry همان intent، evaluation و evidence را بدون
   رکورد تکراری بازگرداند.
5. **API/UI:** endpointهای فقط‌خواندنی و progressive disclosure پنج صفحهٔ Strategy، Signal، Candidate،
   Risk و Portfolio در `/fa` و `/en` بررسی شوند.
6. **Security inventory:** OpenAPI، routeها، network و payloadها فاقد credential، wallet، exchange
   account، deposit/withdrawal و live-order write باشند.

## اجرای verifier نهایی

پس از سبزشدن GitHub Actions همان SHA:

```bash
P5_SHA=$(git rev-parse HEAD)

PYTHONPATH=src python scripts/verify_v0_3_phase_five.py \
  --database-url "$TRD_BOT_TEST_DATABASE_URL" \
  --confirm-destructive-migration-cycle trd_bot_test \
  --decision-benchmark-report /tmp/trd-bot-p5-decision-benchmark-final.json \
  --github-actions-run-url 'https://github.com/OWNER/REPOSITORY/actions/runs/RUN_ID' \
  --github-actions-head-sha "$P5_SHA" \
  --github-actions-conclusion success \
  --strategy-signal-candidate-lineage-smoke pass \
  --risk-gate-fail-closed-smoke pass \
  --paper-shadow-portfolio-advisory-smoke pass \
  --worker-restart-idempotency-smoke pass \
  --api-ui-progressive-disclosure-smoke pass \
  --security-network-smoke pass \
  --environment-label macbook-pro-reference \
  --output artifacts/p5-09/phase-five-acceptance.json
```

خروجی پذیرفته‌شده باید تصمیم مشتق‌شده زیر را داشته باشد:

```json
{
  "failed_gates": [],
  "benchmark": {"passed": true},
  "ready_to_freeze_phase_five": true
}
```

Verifier fail-closed است: detached HEAD، worktree کثیف، دیتابیس غیرمجاز، P4 ردشده، ancestry نامعتبر،
SHA یا environment ناسازگار، benchmark قدیمی، CI نامنطبق، smoke ناقص، gate شکست‌خورده و outcome
دست‌کاری‌شده همگی freeze را متوقف می‌کنند. command evidence هیچ database URL یا credential ذخیره
نمی‌کند.

## cleanup

```bash
docker ps -a \
  --filter 'name=^/trd-bot-p5-09-acceptance-db17$' \
  --format '{{.Names}}'

docker rm -f trd-bot-p5-09-acceptance-db17
unset TRD_BOT_DATABASE_URL TRD_BOT_TEST_DATABASE_URL

if ! docker ps -a \
  --filter 'name=^/trd-bot-p5-09-acceptance-db17$' \
  --format '{{.Names}}' | grep -q .
then
  echo P5_09_FREEZE_AND_CLEANUP=PASS
fi
```

## معیار خروج P5-09

- [x] benchmark قطعی و same-SHA برای چهار stage تصمیم وجود دارد.
- [x] fixture و policy checksumها tamper-evident هستند.
- [x] verifier واحد قراردادها، migration، PostgreSQL، frontend و security boundary را پوشش می‌دهد.
- [x] P4 پذیرفته‌شده و ancestry آن دوباره بررسی می‌شود.
- [x] راهنمای smoke دستی و cleanup ثبت شده است.
- [ ] benchmark نهایی روی SHA مالک مخزن پذیرفته شود.
- [ ] GitHub Actions موفق همان SHA ثبت شود.
- [ ] smoke دستی شش‌گانه روی همان SHA ثبت شود.
- [ ] record نهایی با `ready_to_freeze_phase_five=true` تولید و commit شود.

تا بسته‌شدن چهار مورد آخر، Phase 5 از نظر کد آماده است اما freeze عملیاتی آن هنوز انجام نشده است.
