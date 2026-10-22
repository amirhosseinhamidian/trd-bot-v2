# TB2-017 — breakdown رتبه‌بندی Candidate

این مرحله دلیل عددی رتبه و نتیجهٔ کنترل ریسک هر Candidate را از شواهد immutable
موجود در Candidate Journal بازسازی می‌کند. هیچ migration، اجرای سفارش یا تغییر در
payload اصلی Journal انجام نمی‌شود.

## قرارداد evidence

Candidate List، Detail و Lineage می‌توانند `candidate-decision-evidence-v1` را حمل
کنند. این payload دو بخش مستقل دارد:

- `candidate-ranking-score-v1`: رتبه، امتیاز کل، مؤلفه‌ها، وزن و سهم هر مؤلفه و
  قاعدهٔ tie-break؛
- `candidate-risk-compatibility-v1`: تصمیم، تعداد کنترل‌های موفق/ناموفق، نسبت
  سازگاری و تمام کنترل‌ها با مقدار واقعی، حد و دلیل.

projection این اطلاعات را از `CandidateRankingEntry` و `CandidateRiskAssessment`
همان Journal می‌سازد. بنابراین evidence با replay یا محاسبهٔ دوبارهٔ دادهٔ بازار
تولید نمی‌شود و تغییر زمان request نتیجه را عوض نمی‌کند.

## فرمول ranking

مؤلفه‌های عمومی به‌ترتیب ثابت زیر هستند:

| مؤلفه | مقدار خام | وزن پیش‌فرض |
| --- | --- | --- |
| confidence | confidence نرمال‌شدهٔ Candidate | ۰٫۴۵ |
| signal quality | قدرمطلق signal score | ۰٫۳۵ |
| freshness | سهم زمان اعتبار باقی‌مانده در لحظهٔ ranking | ۰٫۲۰ |

وزن واقعی هر اجرا داخل evidence است و تنها وزن پیش‌فرض جدول بالا نیست. سهم هر مؤلفه
با `ROUND_HALF_UP(raw_value × weight, 0.000001)` و امتیاز کل با جمع سهم‌ها و همان
quantum ساخته می‌شود. validator جمع سهم‌ها را با `total_score` ذخیره‌شده تطبیق
می‌دهد.

ترتیب نهایی همیشه `total_score` نزولی و سپس `candidate_id` صعودی است. اگر چند
Candidate امتیاز برابر داشته باشند، evidence فهرست مرتب شناسه‌ها و جایگاه Candidate
در tie را ثبت می‌کند. در نتیجه جابه‌جایی ترتیب ورودی، رتبه را تغییر نمی‌دهد.

## جداسازی risk compatibility

Risk policy بعد از ranking و با وضعیت Portfolio ارزیابی می‌شود؛ واردکردن نتیجهٔ آن
در همان امتیاز، وابستگی دوری بین رتبه و checkهای `rank_limit` و `ranking_score`
می‌سازد. به همین دلیل `affects_ranking_score=false` بخشی از قرارداد است. نسبت
سازگاری برابر تعداد check موفق تقسیم بر کل checkهاست و صرفاً خلاصهٔ خواندنی همان
هشت check ذخیره‌شده است؛ تصمیم canonical همچنان approved/rejected باقی می‌ماند.

Candidateای که پس از بازشدن position کاندید قبلی skipped شده، risk outcome ندارد و
با `status=not_evaluated` و دلیل `position_opened` نمایش داده می‌شود. نتیجهٔ رد یا
قبول برای آن ساخته نمی‌شود.

## API، UI و سازگاری

`GET /api/v1/research/candidates` علاوه بر rank و ranking score آخرین occurrence،
`latest_decision_evidence` را برمی‌گرداند. detail و lineage نیز evidence هر occurrence
را در خود occurrence حمل می‌کنند. Candidate List جمع امتیاز، فرمول، tie-break و
checkهای ریسک ناموفق را در breakdown فقط‌خواندنی نمایش می‌دهد.

فیلد evidence اختیاری است تا projectionهای JSON قدیمی همچنان خوانده شوند. نبود آن
در API به‌صورت `null` و در UI به‌صورت «شاهد breakdown در دسترس نیست» نمایش داده
می‌شود؛ امتیاز یا علت ساختگی جایگزین نمی‌شود. اگر Journal اصلی هنوز ranking و risk
payload کامل را داشته باشد، rebuild معمول projection evidence را دوباره می‌سازد.
