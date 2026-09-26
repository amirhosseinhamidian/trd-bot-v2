# TB2-001 — ماتریس پذیرش TRD BOT v0.2.0

مبنای این ماتریس صفحهٔ «Definition of Done» پروپوزال v0.2.0 (صفحهٔ ۳۵ PDF)، استراتژی QA صفحهٔ ۳۶ و snapshot `cf3caa9d16ecc7c1597ea0d37db13398cafa8e24` است. «جزئی/موجود» قضاوت ایستای کد است؛ هیچ ردیف تا زمان تست کاربر، migration و CI روی SHA نامزد انتشار «قبول» نیست. حتی قابلیت‌های Should در جدول اولویتِ پروپوزال اگر در Definition of Done آمده‌اند، برای انتشار باید پذیرفته شوند.

## دوازده شرط الزام‌آور انتشار

| ID | شرط پروپوزال | شاهد فعلی و وضعیت ایستا | آزمون پذیرش لازم | مرحلهٔ بستن |
| --- | --- | --- | --- | --- |
| D01 | حداقل یک Connection دادهٔ واقعی Test و Historical Import انجام دهد. | allowlist شامل Binance، Nobitex و Kraken است؛ metadata مسیر اتصال/default pair/عمق تاریخی به API و UI رسیده، lifecycle کامل Nobitex آزمون E2E آفلاین دارد و Import به checksum همان Preview مقید شده است. شواهد اجرای واقعی هنوز باید هنگام پذیرش SHA نهایی ثبت شوند. | Nobitex مستقیم و Kraken روی مسیر VPN را health-check کن؛ بازهٔ معلوم را وارد و provenance، coverage، خطای provider/timeout و نبود secret را کنترل کن. | TB2-003، TB2-003.5A تا C، TB2-004، TB2-009 |
| D02 | Dataset از API و فایل به schema یکسان برسد. | CSV/JSON/Parquet در Backend با mapping صریح به `OHLCVCandle` و `DatasetBuilder` مشترک می‌رسند؛ checksum و Quality Report fixture همسان بین سه format برابر است و provenance فایل ثبت می‌شود. **پیاده‌سازی‌شده؛ پذیرش نهایی باقی است**. | fixture یکسان را از provider/CSV/JSON/Parquet بخوان؛ candleهای canonical و گزارش کیفیت را مقایسه کن؛ ستون غیرمعمول، فایل خراب، limit و checksum منقضی را آزمایش کن. | TB2-007، TB2-024 |
| D03 | Quality Report و provenance برای Dataset قابل مشاهده باشد. | پوشش requested range و امتیاز/breakdown نسخه‌دار در Preview و Dataset Detail نمایش داده می‌شوند؛ policy پذیرش و issueها persisted هستند و payloadهای قدیمی بدون score همچنان خوانده می‌شوند. **پیاده‌سازی‌شده؛ پذیرش نهایی باقی است**. | fixture کامل، head/tail ناقص، gap و خطای یکپارچگی را در API/UI کنترل کن؛ snapshot قدیمی باید با `coverage/score=null` خوانده شود. | TB2-004، TB2-006، TB2-024 |
| D04 | Refresh نسخهٔ تازه بسازد و نسخهٔ قبلی را تغییر ندهد. | Snapshot و History اتمیک‌اند؛ stale refresh با `refresh_conflict` رد می‌شود؛ checksum مشترک Snapshot را duplicate نمی‌کند. گزارش کیفیت هر Import/Refresh روی audit record همان تلاش ثبت و در version history نمایش داده می‌شود، حتی وقتی محتوای canonical تغییر نکرده است. **پیاده‌سازی‌شده؛ PostgreSQL gate باقی است**. | checksum/نتایج Experiment قدیمی ثابت بماند؛ دو refresh هم‌زمان فقط یک نسخه بسازند؛ هر نسخه score/policy همان ارزیابی را نشان دهد. | TB2-005، TB2-006، TB2-024 |
| D05 | Strategy Registry و version lineage در Experimentها حفظ شوند. | registry سه strategy و فیلد نسخه در Experiment؛ صفحهٔ strategy جزئی. **جزئی**. | Experiment قدیمی با Dataset و نسخهٔ رفتار معین بازتولید شود؛ صفحهٔ strategy به history همان نسخه برسد. | TB2-010، TB2-011 |
| D06 | Optimization با robustness و Walk-Forward قابل بازسازی باشد. | plan/execution/scorer/worker مقدماتی؛ route غیرمتصل، تست API placeholder؛ **ناتمام**. | grid کوچک از API/UI به trialهای persisted و foldهای out-of-sample برسد؛ نمونهٔ overfit بهتر رتبه نگیرد؛ retry deterministic. | TB2-008، TB2-012 تا TB2-015 |
| D07 | نمودار Equity/Drawdown/Benchmark در Experiment و Portfolio نمایش داده شود. | نمودارهای Experiment و performance series موجود؛ Portfolio analytics کامل نیست. **جزئی**. | مقادیر جدول و نمودار برای دادهٔ golden برابر باشند؛ drawdown و benchmark و portfolio equity در UI دیده شوند. | TB2-016، TB2-020 |
| D08 | ranking breakdown و علت رد ریسک قابل مشاهده باشند. | domain ranking/risk و projection با امتیاز کل/تصمیم موجود؛ breakdown و Risk dashboard هنوز کامل نیست. **جزئی**. | در دو Candidate دلیل رتبه و tie-break روشن؛ یک رد به rule و نمودار شمار علل رد لینک شود. | TB2-017 تا TB2-019 |
| D09 | Position Detail زنجیرهٔ منشأ تا Exit را نشان دهد. | GET position و Portfolio Detail موجود؛ صفحهٔ اختصاصی Position و lineage تصویری کامل دیده نشد. **جزئی**. | از Candidate/Portfolio به Position بسته برو؛ Dataset/Experiment/Signal، entry/exit/fee/PnL/reason/event را دنبال کن. | TB2-018، TB2-021 |
| D10 | کارهای سنگین Background Job و progress داشته باشند. | FastAPI BackgroundTasks برای Experiment/Walk-Forward، import تاریخی synchronous؛ **ناتمام**. | import/trial در صف با progress پس از reload و restart، retry امن و محدودیت منابع؛ request بلاک نشود. | TB2-008، TB2-009، TB2-013 |
| D11 | Backend، PostgreSQL، frontend build و migration-from-zero سبز باشند. | فایل CI و راهنمای MVP موجود؛ نتیجهٔ این HEAD ثبت نشده. **تأییدنشده**. | lint/typecheck/unit/integration/build، migration روی DB آزمایشی خالی و E2E در CI همین SHA سبز شود. | TB2-002، TB2-024، TB2-025 |
| D12 | endpoint یا UI برای live order execution وجود نداشته باشد. | routeهای ثبت‌شده در `main.py` پژوهش/شبیه‌سازی هستند؛ با تغییر کد دوباره بررسی شود. **بازبینی مستمر**. | route inventory و رابط‌ها روی SHA نهایی بررسی شوند؛ credential یا درخواست سفارش واقعی و withdrawal پذیرفته نشود. | هر مرحله؛ TB2-024/025 |

## ماتریس آزمون و شواهد لازم

| لایه | شاهد لازم هنگام اجرای مرحله | نمونهٔ هدف |
| --- | --- | --- |
| Unit | تست مرز و خروجی deterministic متناسب با تغییر. | validator، quality boundary، ranking components، job state machine. |
| Provider contract | fake provider و adapter واقعی بدون تکیه به شبکهٔ زنده در CI. | timeout/rate-limit/partial fetch، shape و normalization مشترک. |
| PostgreSQL integration | migration از DB خالی، transaction/failure و queryهای lineage. | شکست history rollback کند؛ refresh concurrent نسخه تکراری نسازد. |
| Golden dataset | fixture ثابت با checksum، timezone و quality معلوم. | همان input از مسیر API و فایل نتیجهٔ قابل مقایسه بدهد. |
| E2E | عبور یک دادهٔ کوچک از Connection/File تا پژوهش، Candidate، Portfolio و گزارش. | Snapshot و StrategyVersion و علت Exit قابل پیمایش. |
| Frontend | render، error/empty/loading، chart و حالت فقط‌خواندنی. | ستون نامتعارف، progress بعد از reload، fold بی‌معامله. |
| Failure | خطاهای قابل بازیابی و failure injection. | provider down، worker restart، فایل خراب، شکست DB پس از snapshot. |
| Security | مسیرهای لو نرفتن دادهٔ حساس و عدم اجرای معامله. | secret masking/log redaction، absence of live order routes. |

## تعریف بستن هر مرحله

برای هر TB2، پچ محدود، شمارهٔ مرحله، سناریوهای خطا، تغییر قرارداد و migration، commandهای قابل اجرا و خروجی واقعی تست صاحب پروژه ثبت می‌شود. برای TB2-001 فقط مستندسازی و سازگاری ماتریس با کد بررسی می‌شود؛ «قبولی عملکرد» شرط این مرحله نیست. TB2-002 گیت CI را قابل ارزیابی می‌کند و TB2-024 شواهد نهایی همهٔ D01 تا D12 را جمع می‌کند. provider دوم دیگر deferred نیست: سنجش دسترسی و انتخاب در TB2-003.5A، دو adapter در TB2-003.5B و اتصال UI/E2E در TB2-003.5C انجام می‌شود؛ market regime و streaming همچنان خارج از دامنهٔ انتشار v0.2 هستند.
