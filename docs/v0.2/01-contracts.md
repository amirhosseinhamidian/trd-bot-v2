# TB2-001 — قراردادهای مبنا و تصمیم‌های طراحی

این سند قراردادهای **قابل اتکا در HEAD** و پیشنهادهای لازم برای گام‌های بعدی را جدا می‌کند. «هدف» در جدول‌ها قرارداد پیاده‌شده نیست و به معنی نهایی‌شدن طراحی API، schema یا انتخاب فناوری نیست. هر تصمیمی که نیاز به تغییر API/داده داشته باشد در پچ مربوط با تست و راه مهاجرت قطعی می‌شود.

## مرز محصول و سازگاری

| قرارداد | وضع فعلی/منبع | قاعده برای مراحل بعدی |
| --- | --- | --- |
| دامنه | `src/trd_bot/main.py` برنامه را «historical research and paper-analysis» معرفی می‌کند؛ APIهای فعلی در `/api/v1` هستند. | API سفارش‌گذاری یا ارسال سفارش واقعی، credential معامله و live trading به v0.2 اضافه نشود؛ هر قابلیت جدید فقط تحقیق و شبیه‌سازی است. |
| بازتولیدپذیری | `DatasetSnapshot` frozen است و checksum/provenance دارد؛ Experiment به Dataset و نام/نسخهٔ Strategy ارجاع می‌دهد. | هر نتیجه به همان snapshot و strategy version بماند؛ refresh داده و تغییر منطق استراتژی نباید نتیجهٔ قدیمی را بازتفسیر کند. |
| API و مهاجرت | `/api/v1/research/...` و `/api/v1/market-data/...` فعال هستند؛ migrationهای موجود تا `20260831_0014_optimization_executions.py` دیده می‌شوند. | مسیرهای موجود بدون ضرورت نشکنند؛ schema فقط با migration قابل اجرا از DB خالی و بدون overwrite رکوردهای قبلی توسعه یابد. |
| خطاها | APIهای موجود برای بعضی موارد با HTTPException و `detail` متن خطا برمی‌گردانند. | وقتی قرارداد جدید لازم شد، کد خطای پایدار و پیام قابل فهم تعریف شود؛ `detail`/status موجود بدون سنجش clientهای فعلی یک‌باره عوض نشود. |
| اسرار | `MarketDataProviderCatalog` فقط adapterهای عمومی `binance-public`، `nobitex-public` و `kraken-public` را با `requires_credentials=False` ارائه می‌کند. | اتصال عمومی secret درخواست نکند؛ راه credential احتمالی بعدی باید backend-managed باشد و کلید در UI، log، URL یا response افشا نشود؛ بازار/معامله خارج از دامنه است. |

## قرارداد ورود داده و مدل تحقیق

| حوزه | قرارداد قابل مشاهده | هدف و محل تصمیم تکمیلی |
| --- | --- | --- |
| کندل | `OHLCVCandle` در `src/trd_bot/domain/market_data.py`: source، pair، timeframe (`15m/1h/4h/1d`)، زمان aware که UTC می‌شود، open/high/low/close/volume به صورت Decimal، is_closed؛ بازار فعلی spot. CSV/JSON/Parquet در Backend به همین مدل normalize می‌شوند و `close_time` باید با timeframe برابر باشد. | هیچ parser فایل یا provider مجاز نیست مدل پژوهش را دور بزند؛ format جدید باید قبل از DatasetBuilder به همین schema برسد. |
| provider | interface پیاده‌شده `test_connection()` و `get_candles(pair,timeframe,start,end,limit)` است؛ `MarketDataProviderCatalog` metadata می‌دهد. adapterهای Nobitex و Kraken، بازهٔ نیمه‌باز، حذف کندل باز، timeout/retry محدود و normalization مشترک دارند. | Nobitex منبع مستقیم اصلی است؛ Kraken منبع دوم وابسته به مسیر شبکه/VPN و محدود به ۷۲۰ entry اخیر است. قابلیت‌های `list_markets` و کشف نماد در مرحلهٔ بعدی تکمیل می‌شوند. |
| بازه | در provider حافظه‌ای انتخاب با `start_time <= open_time < end_time` انجام می‌شود؛ request دارای زمان aware است. | برای همهٔ مسیرها semantics بازهٔ نیمه‌باز و تکلیف کندل آخر/بازهٔ باز مبنا شود یا در TB2-004 با شاهد مخالف بازنگری شود؛ preview و import باید دربارهٔ coverage یک معنی بدهند. |
| snapshot | `DatasetSnapshot` دارای `dataset_id`, `schema_version`, checksum, quality_report, provenance, candles است؛ `MarketDataImportRecord` تاریخچهٔ درخواست را نگه می‌دارد. | snapshot immutable بماند؛ باید تعیین شود اشتراک checksum یکسان بین دو Connection چگونه با provenance هر import و version lineage سازگار می‌شود (TB2-005). |
| کیفیت | `DataQualityReport` پوشش requested range، امتیاز `quality-score-v1`، breakdown پوشش/یکپارچگی و تصمیم `strict-quality-v1` را نگه می‌دارد؛ گزارش هر Import/Refresh نیز در audit record ثبت می‌شود. مسیر فایل پس از normalization همین policy را روی بازه‌ی اولین open تا آخرین close اجرا می‌کند و alignment زمانی را می‌سنجد. | خطای container/mapping/row قبل از Snapshot کد پایدار دارد؛ Dataset فایل فقط با policy پذیرفته‌شده قابل ذخیره است. |
| strategy | `build_default_strategy_registry()` سه strategy با metadata و نسخهٔ `1.0.0` می‌سازد؛ lookup کاتالوگ در `/api/v1/research/strategies` است. | قرارداد عدم تغییر رفتار در همان نسخه، schema پارامتر و نگاشت history به StrategyVersion در TB2-010/011 تثبیت شود؛ نوع نگهداری registry هنوز الزاماً DB نیست. |
| optimization | `OptimizationPlan` bounded و `OptimizationExecution` با queued/running/succeeded/failed موجودند؛ scorer انتخاب objective تکی دارد. | شمار/نتیجهٔ هر trial، best_experiment_id، score breakdown و folds باید به Experiment/Dataset/StrategyVersion وصل شود؛ workflow پچ‌های TB2-012 تا TB2-015 تعریف شود. |
| jobs | Experiment و Walk-Forward در FastAPI `BackgroundTasks` اجرا می‌شوند. | قرارداد مشترک durable با progress/retry/idempotency/cancel و پیوند به نتیجه در TB2-008 تعیین شود؛ queue/worker محصول یک انتخاب عملیاتی است، نه تصمیم پذیرفته‌شدهٔ TB2-001. |

## فهرست تصمیم‌ها؛ پیشنهاد اولیه، هنوز قرارداد اجرایی نیست

| ADR | سؤال و پیشنهاد برای بررسی | تکلیف نهایی |
| --- | --- | --- |
| ADR-01 | **تصمیم TB2-004:** Preview checksum محتوایی برمی‌گرداند؛ Import داده را دوباره fetch و checksum را مقایسه می‌کند و تغییر را با HTTP 409 رد می‌کند. | بسته در TB2-004 |
| ADR-02 | **تصمیم TB2-005:** checksum برابر یک Snapshot canonical مشترک دارد؛ Import سازنده مالک provenance و نسخهٔ ۱ Snapshot است و هر Import بعدی رکورد audit مستقل خود را بدون ادعای lineage تازه نگه می‌دارد. Snapshot و رکورد موفق در یک تراکنش ثبت می‌شوند. | بسته در TB2-005 |
| ADR-03 | **تصمیم TB2-006:** امتیاز نسخه‌دار حاصل‌ضرب پوشش و یکپارچگی است و هیچ مولفه‌ای ضعف مولفه دیگر را جبران نمی‌کند. پذیرش fail-closed است: امتیاز ۱۰۰ و نبود هرگونه issue مسدودکننده لازم است. | بسته در TB2-004/006 |
| ADR-08 | **تصمیم TB2-007:** فایل در سه مرحله inspect، preview و commit پردازش می‌شود؛ client فقط mapping/identity را می‌فرستد، Backend parse می‌کند و commit باید checksum canonical همان preview را ارائه کند. فایل خام ذخیره نمی‌شود، اما filename امن، format، SHA-256 فایل و mapping در provenance Snapshot ثبت می‌شوند. | بسته در TB2-007 |
| ADR-04 | تضمین نسخهٔ رفتار Strategy: افزایش version با هر تغییر سیگنال، hash نسخه یا هر دو؟ پیشنهاد: نسخهٔ منتشرشده immutable با تست golden؛ راه migration برای experimentهای قدیمی ثبت شود. | TB2-010 |
| ADR-05 | پشتهٔ job/worker چگونه با PostgreSQL و استقرار موجود بدون هزینهٔ غیرضروری سازگار شود؟ پیشنهاد: صف persistent با lease/recovery و محدودیت هم‌زمانی؛ انتخاب فناوری پس از سنجش محیط استقرار. | TB2-008 |
| ADR-06 | تعریف robustness، وزن‌ها، حداقل sample، دوره‌ها، train/test split و tie-break چیست؟ پیشنهاد: ابتدا golden مثال overfit و fold بی‌معامله بسازیم، سپس score نسخه‌دار نهایی شود. | TB2-014 |
| ADR-07 | error contract جدید چگونه در کنار endpointهای موجود سازگار می‌ماند؟ پیشنهاد: کد ماشین‌خوان برای مسیر جدید همراه HTTP status، بدون شکستن client فعلی. | TB2-002/012 |

**معیار خروج TB2-001:** قرارداد موجود از هدف پیشنهادی تفکیک شده، هر ADR صاحب مرحله و سناریوی پذیرش دارد، و تمام Definition of Doneها در ماتریس همراه شاهد کد/تست و گام بعدی ثبت شده‌اند. این مرحله هیچ ADR فنیِ حل‌نشده را «تأیید شده» اعلام نمی‌کند.
