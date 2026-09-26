# TB2-001 — مبنای نسخهٔ دوم

این سند فقط وضعیت **قابل مشاهده در کد** را در تاریخ ۲۰۲۶-۰۹-۱۲ ثبت می‌کند. مبنا، `feature/v0.3-strategy-foundation` در `cf3caa9d16ecc7c1597ea0d37db13398cafa8e24` است؛ SHA ریموت نیز هنگام بررسی همین مقدار بود. این checkout کم‌عمق است؛ ترتیب همهٔ commitهای پیشین از روی `git log` محلی قابل داوری نیست. نام برنچ معادل نسخهٔ انتشار نیست: معیار محصول، Definition of Done پروپوزال `TRD_BOT_v0.2.0_Proposal_FA.pdf` است. تکمیل v0.1.0 گفتهٔ صاحب پروژه است؛ در این مرحله صحت اجرای آن دوباره آزموده نشده است.

## روش و اصطلاحات

- «موجود»: کد/صفحه/API در HEAD دیده می‌شود، بدون حکم دربارهٔ کارکرد آن در محیط اجرا.
- «جزئی»: بخشی از مسیر یا مدل دیده می‌شود، ولی یکی از شرط‌های پروپوزال هنوز شاهد کافی ندارد.
- «یافت نشد»: در مسیرهای بررسی‌شده دیده نشد؛ ادعای اثبات نبودن در تمام مسیرهای ممکن نیست.
- «ناهمخوانی ایستا»: مسیر مشخصی در کد برای ریسک/نقص شناسایی شده است؛ شدت عملی باید با آزمون تأیید شود.
- «تأییدشده»: فقط پس از تست کاربر و CI روی همان SHA؛ هیچ‌یک از موارد زیر فعلاً این برچسب را ندارند.

در TB2-001 فایل اجرایی و تست تغییر نکرده و هیچ تست، migration، درخواست زنده به Binance یا build اجرا نشده است. جدول‌های زیر برای برنامه‌ریزی و تکرار بررسی روی checkout کاربر هستند.

## نقشهٔ فعلی سیستم

| حوزه | شاهد در HEAD | جمع‌بندی ایستا | پیگیری |
| --- | --- | --- | --- |
| نسخهٔ پایه | `src/trd_bot/research/{datasets,experiments,walk_forward.py,candidates.py}`، `src/trd_bot/paper/`، `tests/test_mvp_acceptance.py` | زیرساخت پژوهش/شبیه‌سازی و یک آزمون پذیرش v1 در مخزن موجودند؛ نتیجهٔ اجرای کنونی معلوم نیست. | TB2-002 و TB2-024 |
| Connection و provider | `src/trd_bot/market_data/{connections,providers.py}`، `src/trd_bot/api/routes/market_data_connections.py`، `frontend/src/app/[locale]/connections/page.tsx` | کاتالوگ allowlist با `binance-public` بدون credential، چرخهٔ add/test/enable/disable و UI موجود است. قرارداد، failure و امنیت باید روی محیط آزموده شوند. | TB2-003 |
| Import و فایل | `src/trd_bot/api/routes/{market_data_imports,datasets}.py`، `src/trd_bot/research/{historical_dataset_imports,historical_dataset_jobs,dataset_file_imports}.py`، `frontend/src/components/dashboard/dataset-import-form.tsx` | Preview و مسیرهای سازگار قبلی موجودند؛ endpointهای جدید import/refresh دادهٔ Provider را با پاسخ 202 وارد صف durable می‌کنند. فایل CSV/JSON/Parquet همچنان در request پردازش می‌شود تا قرارداد staging فایل خام جداگانه تعیین شود. | TB2-004، TB2-007، TB2-009 |
| کیفیت و versioning | `src/trd_bot/market_data/quality.py`، `src/trd_bot/research/datasets.py`، `alembic/versions/20260831_0013_market_data_import_lineage.py` | snapshot دارای checksum/provenance/quality report است و version history API/UI دارد. coverage بازه و امتیاز کیفیت کامل نیست؛ تراکنش snapshot/history مستقل است. | TB2-004 تا TB2-006 |
| Strategy | `src/trd_bot/strategies/registry.py`، `src/trd_bot/api/routes/research.py`، `frontend/src/app/[locale]/strategies/` | کاتالوگ EMA/SMA/RSI با نام و نسخه و صفحات لیست/detail موجود است. رجیستری فعلی در کد ساخته می‌شود؛ history و هویت نسخهٔ رفتار نیاز به بررسی/تکمیل دارد. | TB2-010، TB2-011 |
| Optimization | `src/trd_bot/research/{optimization,optimization_executions,optimization_runner,optimization_worker}.py`، `alembic/versions/20260831_0014_optimization_executions.py` | planner، scorer تک‌معیاره، state machine، repository و worker مقدماتی موجودند؛ API route به برنامه متصل نیست و جریان کامل trial/Walk-Forward/UI وجود ندارد. | TB2-012 تا TB2-015 |
| Experiment/Walk-Forward | `src/trd_bot/api/routes/research.py`، `src/trd_bot/research/performance_series.py`، `frontend/src/components/dashboard/experiment-performance-charts.tsx` | اجرای پژوهش و نمودارهای equity/drawdown/benchmark موجودند. fold analytics و اجزای کامل analytics نسخه دوم هنوز نیازمند پیاده‌سازی/پذیرش‌اند. | TB2-016 |
| Candidate و Risk | `src/trd_bot/research/{candidate_ranking,risk_policy,candidate_projection}.py`، `src/trd_bot/api/routes/candidates.py`، صفحات Candidate | مدل رتبه/سیاست ریسک و lineage موجودند؛ API projection امتیاز کل را می‌دهد، اما breakdown و داشبورد تجمیعی Risk نسخهٔ دوم تکمیل نشده‌اند. | TB2-017 تا TB2-019 |
| Portfolio/Position | `src/trd_bot/api/routes/portfolios.py`، `src/trd_bot/paper/`، `frontend/src/app/[locale]/portfolios/` | route دریافت Position و جزئیات Portfolio موجود است؛ صفحهٔ اختصاصی Position و تحلیل جامع عملکرد/ریسک هنوز دیده نمی‌شود. | TB2-020، TB2-021 |
| Jobs و Monitoring | `src/trd_bot/jobs.py`، `src/trd_bot/db/background_job_repositories.py`، `scripts/run_background_worker.py`، `src/trd_bot/api/routes/{jobs,monitoring}.py` | صف PostgreSQL با idempotency، lease/recovery، progress، retry/cancel و API مشاهده موجود است؛ import/refresh دادهٔ Provider به worker متصل شده، اما Optimization و حذف `BackgroundTasks` قدیمی هنوز مرحله‌ای است. | TB2-008، TB2-009، TB2-013، TB2-023 |
| CI و release | `.github/workflows/ci.yml`، `docs/mvp-release-checklist.md`، `tests/` | workflow فقط push به main، PR به main یا اجرای دستی را پوشش می‌دهد؛ این صرفاً وجود گیت است، نه نتیجهٔ سبز همین برنچ. مستند انتشار موجود مربوط به MVP است. | TB2-002، TB2-024، TB2-025 |

## ریسک‌های مشخص‌شده برای گام‌های بعد

| شناسه | شاهد مستقیم | اثر احتمالی و وضعیت اثبات | گام |
| --- | --- | --- | --- |
| R-01 | `src/trd_bot/api/routes/optimization_executions.py` در `src/trd_bot/main.py` include نشده؛ `tests/test_optimization_execution_api.py` فقط `assert True` دارد و `tests/test_optimization_execution_flow_api.py` خودش placeholder integration را ذکر می‌کند. | endpoint تولیدی بهینه‌سازی در برنامه فعلی فعال نیست؛ آزمون پذیرش واقعی لازم است. | TB2-012 |
| R-02 | متدهای `preview()` و `import_dataset()` در `src/trd_bot/research/historical_dataset_imports.py` جداگانه `_fetch_and_check()` را می‌خوانند. | احتمال تغییر داده بین preview و نتیجهٔ واقعی؛ باید با provider پاسخ‌متغیر آزموده شود. | TB2-004 |
| R-03 | `MarketDataQualityChecker.check(candles)` در `src/trd_bot/market_data/quality.py` requested range را نمی‌گیرد و تنها بین کندل‌های دریافتی gap می‌یابد. | بازه‌ای با سر/ته ناقص ممکن است بی‌هشدار معتبر تلقی شود؛ شرط پوشش مرز باید آزموده شود. | TB2-004، TB2-006 |
| R-04 | `SqlAlchemyDatasetRepository.save()` و `SqlAlchemyMarketDataImportRepository.save()` هر کدام commit می‌کنند؛ route import به ترتیب هر دو را فراخوانی می‌کند. | در شکست ثبت history، snapshot ثبت‌شده می‌تواند باقی بماند؛ سناریوی rollback و refresh هم‌زمان نیازمند آزمون است. | TB2-005 |
| R-05 | `OptimizationScorer.metric_value()` فقط یک objective خام (total return، excess return یا max drawdown) را مبنا می‌گیرد. | محدودیت در سنجش overfitting/robustness طبق پروپوزال، نه خطای قطعی محاسبهٔ همین objective. | TB2-014 |
| R-06 | **بسته در TB2-007:** `dataset_file_imports.py` سه فرمت CSV/JSON/Parquet را با سقف فایل/ردیف/ستون/cell و mapping صریح به `OHLCVCandle` می‌رساند؛ فرم دیگر فایل را در مرورگر parse نمی‌کند. | مسیر فایل همان Quality Policy و DatasetBuilder را استفاده می‌کند و Preview/Commit با checksum canonical محافظت می‌شود؛ پذیرش نهایی روی fixtureهای هر سه فرمت در TB2-024 ثبت می‌شود. | TB2-007، TB2-024 |
| R-07 | `get_optimization_execution_repository()` در `src/trd_bot/api/dependencies.py` از `next(get_database_session())` استفاده می‌کند، برخلاف dependencyهای request-scoped همان فایل. | lifecycle session ممکن است درست بسته نشود؛ هنگام فعال‌سازی API باید اصلاح شود. | TB2-012 |

## وضعیت تأیید و دستورات بررسی مالک مخزن

در این نقطه تمامی نتایج تست/CI/migration برای SHA مبنا «نامعلوم» هستند. پیش از ارجاع به نتیجهٔ QA، همان SHA و خروجی فرمان‌ها باید ثبت شوند؛ ابتدا `git status --short --branch` و `git rev-parse HEAD`، سپس طبق راهنمای `../mvp-release-checklist.md` گیت‌های backend/PostgreSQL/frontend روی دیتابیس آزمایشی اجرا شوند. `docker compose down -v` در راهنمای MVP دادهٔ volume را حذف می‌کند و نباید برای این بررسی روی پایگاه داده‌ای که باید حفظ شود اجرا شود.

این وضعیت با آمدن commit جدید خودکار معتبر نمی‌ماند: پیش از هر TB2 بعدی، HEAD و ماتریس پذیرش باید دوباره با تغییرهای مؤثر مقایسه شوند.
