# P6-07 — Final v0.3 Acceptance and Freeze

وضعیت: **زیرساخت Freeze آماده است؛ اجرا پس از commit، push و CI سبز candidate انجام می‌شود**

این مرحله آخرین گیت Phase 6 و پایان چرخه توسعه v0.3 است. هیچ قابلیت محصولی، migration، endpoint،
صفحه UI یا مجوز عملیاتی جدیدی اضافه نمی‌شود. هدف فقط اتصال شواهد Hardening و عملیات نسخه به یک
candidate SHA و تولید یک acceptance artifact نهایی و tamper-resistant است.

Freeze با tag، GitHub Release، deploy یا merge به `main` یکسان نیست. این عملیات فقط با تصمیم جداگانه
مالک مخزن انجام می‌شوند و runner هیچ‌کدام را اجرا نمی‌کند.

## پیش‌شرط Candidate

ابتدا تمام تغییرات P6-01 تا P6-07 به‌جز acceptance artifact نهایی باید در یک commit یا زنجیره commit
قرار گرفته، push شده و GitHub Actions همان SHA سبز باشد:

```bash
git status --short
git rev-parse HEAD
git branch --show-current
```

برای اجرای Freeze:

- worktree باید کاملاً clean باشد؛
- branch نباید detached باشد؛
- رکورد `artifacts/p5-09/phase-five-acceptance.json` باید معتبر و commit پذیرفته‌شده P5 باید ancestor
  نامزد فعلی باشد؛
- چهار artifact Phase 6 باید حداکثر هفت روز عمر داشته باشند؛
- SHA و `environment_label` هر چهار artifact باید با candidate یکسان باشند؛
- GitHub Actions باید برای همان candidate SHA نتیجه `success` داشته باشد.

## Artifactهای الزامی

| مرحله | Artifact | شرط پذیرش |
| --- | --- | --- |
| P6-01 | inventory در زمان Freeze دوباره از repository ساخته می‌شود | `passed=true` و no-live |
| P6-02 | Release Capacity Benchmark | `passed=true` و همان SHA/environment |
| P6-03 | Outcome/Learning Review | offline، بدون auto-tuning/ML و بازبینی انسانی ثبت‌شده |
| P6-04 | Maintenance Plan نهایی | `human_approval_required=false` |
| P6-06 | Installation Verification | `passed=true` و inventory checksum یکسان |

وضعیت `insufficient_data` یا `observational` در P6-03 شکست release نیست؛ این وضعیت از نتیجه‌گیری
زودهنگام جلوگیری می‌کند. warning یا `human_review_required=true` باید واقعاً بازبینی و با smoke دستی
تأیید شود. هیچ policy خودکار تغییر نمی‌کند.

اگر P6-04 هنوز action از نوع `required`، `review` یا `blocked` دارد، acceptance runner پیش از اجرای
گیت‌ها آن را رد می‌کند. actionهای مجاز باید مطابق runbook P6-04 بسته و plan جدید با output تازه تولید
شود؛ artifact قبلی overwrite نمی‌شود.

## دیتابیس گیت نهایی

چرخه downgrade/rebuild مخرب فقط روی PostgreSQL 17 با نام دقیق `trd_bot_test` اجرا می‌شود. از
دیتابیس توسعه، restore upgrade، دیتابیس benchmark یا volume اصلی استفاده نکنید.

```bash
export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://trd_bot:trd_bot_test_password@127.0.0.1:5432/trd_bot_test'
```

Runner URL را در artifact ثبت نمی‌کند و command evidence نیز هر آرگومان حاوی DSN را رد می‌کند.

## گیت‌های خودکار

Runner شش gate مرتب را اجرا می‌کند:

1. `release_contract`: نسخه، امنیت، Release Cut، مستندات و parserهای Freeze؛
2. `phase_six_contract`: hardening، capacity، outcome، maintenance و installation؛
3. `backend`: format، lint، typing و تمام تست‌های non-integration؛
4. `migration_cycle`: upgrade، downgrade تا base، rebuild و drift check؛
5. `postgresql_resilience`: تمام تست‌های integration؛
6. `frontend`: `npm ci`، format، lint، typecheck، test و build.

هر gate پس از اولین command ناموفق متوقف می‌شود، ولی gateهای بعدی برای کامل بودن evidence اجرا
می‌شوند. خروجی command فقط argv امن، exit code و duration را نگهداری می‌کند. پس از پایان gateها،
worktree دوباره کنترل می‌شود و هر تغییر ناخواسته پیش از تولید artifact باعث توقف است.

## Smokeهای دستی الزامی

پیش از استفاده از flagهای `pass` واقعاً این موارد را بررسی و نتیجه را نگهداری کنید:

- fresh install، upgrade، restore drill و rollback runbook؛
- API، worker restart/reclaim، idempotent retry و lifecycle رابط کاربری؛
- Outcome/Learning report و تمام warningها توسط انسان؛
- بسته‌شدن retention/maintenance بدون حذف immutable evidence؛
- lineage کامل Strategy/Signal/Candidate/Risk/Portfolio و فقط Paper/Shadow؛
- نبود exchange credential، private account، wallet، fund transfer و live-order capability.

## اجرای Final Acceptance

نام فایل‌های `/tmp` را با artifactهای واقعی تولیدشده روی candidate SHA جایگزین کنید:

```bash
export P6_GITHUB_ACTIONS_RUN_URL='https://github.com/amirhosseinhamidian/trd-bot-v2/actions/runs/123456789'

PYTHONPATH=src python scripts/verify_v0_3_phase_six.py \
  --database-url "$TRD_BOT_TEST_DATABASE_URL" \
  --confirm-destructive-migration-cycle trd_bot_test \
  --capacity-report /tmp/trd-bot-p6-02-release-capacity.json \
  --outcome-learning-review /tmp/trd-bot-p6-03-outcome-learning-review.json \
  --maintenance-plan /tmp/trd-bot-p6-04-maintenance-plan-final.json \
  --installation-report /tmp/trd-bot-p6-06-installation-verification.json \
  --github-actions-run-url "$P6_GITHUB_ACTIONS_RUN_URL" \
  --github-actions-head-sha "$(git rev-parse HEAD)" \
  --github-actions-conclusion success \
  --fresh-install-upgrade-restore-smoke pass \
  --api-worker-ui-lifecycle-smoke pass \
  --outcome-learning-review-smoke pass \
  --retention-maintenance-smoke pass \
  --paper-shadow-lineage-smoke pass \
  --security-network-smoke pass \
  --environment-label macbook-pro-reference
```

مسیر پیش‌فرض خروجی:

```text
artifacts/p6-07/v0.3-final-acceptance.json
```

نتیجه موفق باید این شرایط را داشته باشد:

- `ready_to_freeze_v0_3=true`؛
- `failed_gates=[]`؛
- تمام gateها `passed=true`؛
- `candidate_commit_sha` برابر SHA مربوط به CI و artifactها؛
- `release_version=0.3.0`؛
- `freeze_commit_policy=acceptance-artifact-only`؛
- `record_checksum` معتبر.

می‌توانید parser رسمی را دوباره اجرا کنید:

```bash
python - <<'PY'
from pathlib import Path
from trd_bot.phase_six_acceptance import parse_phase_six_acceptance_record

path = Path('artifacts/p6-07/v0.3-final-acceptance.json')
record = parse_phase_six_acceptance_record(path.read_bytes())
print(f'ready={record.ready_to_freeze_v0_3}')
print(f'candidate_sha={record.candidate_commit_sha}')
print(f'failed_gates={list(record.failed_gates)}')
print(f'record_checksum={record.record_checksum}')
PY
```

## Freeze commit

پس از نتیجه موفق، `git status --short` باید فقط acceptance artifact جدید را نشان دهد:

```bash
git status --short
git add artifacts/p6-07/v0.3-final-acceptance.json
git diff --cached --name-only
git diff --cached --check
```

خروجی `git diff --cached --name-only` باید دقیقاً یک خط باشد:

```text
artifacts/p6-07/v0.3-final-acceptance.json
```

سپس Freeze commit:

```bash
git commit -m "chore(v0.3): freeze final acceptance"
git push
```

GitHub Actions مربوط به Freeze commit نیز باید سبز شود. اگر acceptance ناموفق بود، artifact شکست‌خورده
را commit نکنید؛ علت را اصلاح، دیتابیس disposable را بازسازی و کل runner را با output تازه تکرار کنید.

## مرز نهایی نسخه

- حالت‌های مجاز فقط `RESEARCH`، `BACKTEST`، `PAPER` و `SHADOW` هستند؛
- Market Data فقط public و read-only است؛
- Decision و Portfolio Intelligence فقط advisory و شبیه‌سازی‌شده‌اند؛
- مدیریت دارایی واقعی، API خصوصی صرافی، secret، wallet و Live Execution وجود ندارد؛
- Freeze مجوز توصیه مالی، auto-tuning production یا آموزش ML production ایجاد نمی‌کند.

## معیار خروج P6-07

- [x] parser و runner پذیرش نهایی fail-closed و checksumدار هستند.
- [x] تمام artifactها به candidate SHA/environment یکسان متصل می‌شوند.
- [x] CI همان SHA، freshness هفت‌روزه و inventory checksum enforce می‌شوند.
- [x] maintenance باز، installation ناموفق و capacity ناموفق Freeze را متوقف می‌کنند.
- [x] backend، migration، PostgreSQL و frontend در رکورد نهایی evidence دارند.
- [x] فقط acceptance artifact اجازه ورود به Freeze commit را دارد.
- [ ] candidate commit و چهار artifact مرجع تولید شوند.
- [ ] CI candidate و smokeهای دستی ثبت شوند.
- [ ] runner با `ready_to_freeze_v0_3=true` پایان یابد.
- [ ] Freeze commit فقط شامل acceptance artifact باشد و CI آن سبز شود.

پس از تکمیل چهار مورد پایانی، Phase 6 و نسخه محلی v0.3.0 پایان یافته‌اند. tag، GitHub Release، deploy
یا merge همچنان تصمیم‌های جداگانه‌اند.
