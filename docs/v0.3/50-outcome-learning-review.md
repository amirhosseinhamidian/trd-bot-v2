# P6-03 - Outcome/Learning Review

وضعیت: **پیاده سازی شده؛ اجرای review مرجع روی PostgreSQL و SHA نهایی باقی است**

این مرحله evidenceهای Outcome موجود را در یک گزارش تجمیعی و قابل ممیزی کنار هم قرار می دهد.
گزارش برای بازبینی انسانی policy است و هیچ policy را تغییر نمی دهد، مدل production آموزش نمی دهد و
قابلیت سفارش گذاری یا مدیریت دارایی واقعی ایجاد نمی کند.

## منابع Evidence

`SqlAlchemyOutcomeLearningReviewReader` فقط queryهای aggregate محدود اجرا می کند و payloadهای row را
در حافظه بارگذاری نمی کند:

| حوزه | Evidence تجمیعی |
| --- | --- |
| Alert | confirmed، neutral، false-positive، drift، awaiting outcome و میانگین directional return |
| Candidate | no-position، closed و توزیع canonical دلیل خروج |
| Decision | تعداد evaluation و disposition هر stage از Strategy تا Portfolio |
| Portfolio | تعداد Paper/Shadow، برد/باخت/breakeven و realized PnL موقعیت های بسته |

شناسه محیط، زمان UTC و commit SHA به گزارش متصل می شوند. policy و کل گزارش checksum مستقل دارند و
parse مجدد، derived readiness و signalها را بازسازی و کنترل می کند.

## Policy بازبینی

نسخه policy برابر `outcome-learning-review-policy-v1` و checksum فریز شده آن برابر است با:

```text
01a16992e6096a96ab9a2ae5fab0b7df8789cc5ecdb53365a8b1721428c9fd4c
```

| معیار | حداقل sample / آستانه warning |
| --- | ---: |
| Alert outcomes | 30 |
| Candidate journals | 30 |
| Decision evaluations | 30 |
| Outcomes هر Decision stage | 30 |
| Closed simulated positions | 30 |
| Alert false-positive rate | 30% |
| Alert drift rate | 30% |
| Candidate no-position rate | 70% |
| Decision non-acceptance rate | 50% |
| Simulated loss rate | 50% |

سه وضعیت ممکن است:

- `insufficient_data`: هیچ sample اصلی برای نتیجه گیری وجود ندارد؛
- `observational`: بخشی از evidence موجود است ولی حداقل sampleها کامل نیست؛
- `review_ready`: تمام sampleهای اصلی برای بازبینی انسانی کافی هستند.

`insufficient_data` یا `observational` شکست اجرایی نیست. این وضعیت ها مانع نتیجه گیری زودهنگام هستند.
Warning نیز پیشنهاد معامله یا تغییر خودکار policy نیست؛ فقط دلیل و evidence لازم برای بازبینی دستی را
ثبت می کند.

## مرز ایمنی

قرارداد report به صورت صریح این موارد را enforce می کند:

- `offline_only=true`؛
- `external_order_submission_allowed=false`؛
- `automatic_policy_updates_applied=false`؛
- `production_ml_training_performed=false`؛
- هیچ credential، account، wallet، سفارش یا API خصوصی در schema گزارش پذیرفته نمی شود.

این مرحله endpoint، صفحه UI یا migration جدید ندارد و inventory فریز شده P6-01 را تغییر نمی دهد.

## اجرای Review مرجع

بعد از commit تغییرات و بالا آوردن PostgreSQL در migration head:

```bash
export TRD_BOT_TEST_DATABASE_URL='postgresql+psycopg://trd_p6:trd_p6_password@localhost:55441/trd_bot_test'

PYTHONPATH=src python scripts/review_v0_3_outcomes.py \
  --database-url "$TRD_BOT_TEST_DATABASE_URL" \
  --environment-label macbook-pro-reference \
  --output /tmp/trd-bot-p6-03-outcome-learning-review.json
```

Runner فقط PostgreSQL را می پذیرد، migration head را کنترل می کند، output موجود را overwrite نمی کند
و به database چیزی نمی نویسد. `commit_sha` باید SHA همان commit باشد که CI آن سبز می شود.

## گیت های کد

```bash
python -m pytest tests/test_outcome_learning_review.py -q
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest -m "not integration"
python -m pytest -m integration -q
```

## معیار خروج P6-03

- [x] evidenceهای Alert، Candidate، Decision و Portfolio در یک snapshot تجمیعی جمع می شوند.
- [x] sample floor، warning threshold، readiness و signalها deterministic و checksumدار هستند.
- [x] aggregateهای ناسازگار و artifact دست کاری شده رد می شوند.
- [x] تغییر policy، آموزش ML و اجرای سفارش صریحاً ممنوع هستند.
- [x] reader فقط خواندنی است و payloadهای row را بارگذاری نمی کند.
- [ ] review مرجع روی PostgreSQL و SHA نهایی تولید و ثبت شود.
- [ ] تست integration و GitHub Actions روی همان SHA سبز شوند.

پس از بستن این گیت، مرحله مجاز بعدی `P6-04 - Retention and Maintenance Operations` است.
