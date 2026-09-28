# TB2-018 — مقایسه و زنجیره تصمیم Candidate

این مرحله read model موجود Candidate را به یک مسیر قابل‌پیگیری از Dataset تا Exit
تبدیل می‌کند. هیچ migration، اجرای سفارش، یا بازسازی نتیجه از داده بازار انجام
نمی‌شود؛ همه خروجی‌ها از Candidate Projection و occurrenceهای immutable آن مشتق
می‌شوند.

## مقایسه هم‌گروه

`POST /api/v1/research/candidates/compare` بین دو تا چهار `candidate_id` یکتا
می‌پذیرد. همه Candidateها باید `latest_journal_id` یکسان داشته باشند؛ زیرا rank و
breakdown فقط داخل همان cohort تصمیم معنی قابل‌مقایسه دارند. مخلوط‌کردن Journalها
با `409` رد می‌شود و شناسه‌های پیدا‌نشده با پاسخ `404` ساخت‌یافته برمی‌گردند.

نتیجه با rank ذخیره‌شده و سپس Candidate ID مرتب می‌شود و occurrence کامل، از جمله
`candidate-decision-evidence-v1` یا `null` رکورد قدیمی، را بدون محاسبه دوباره حمل
می‌کند. UI فقط Candidateهای Journal سازگار را قابل انتخاب می‌کند و breakdown دو تا
چهار مورد را کنار هم نشان می‌دهد.

## Rank history

Candidate Detail فیلد `rank_history` را از `projection.history` به‌ترتیب جدیدترین
به قدیمی‌ترین برمی‌گرداند. هر نقطه شامل Journal، زمان ثبت، rank، ranking score،
وضعیت انتخاب و موجودبودن evidence است. نبود evidence قدیمی با
`evidence_available=false` ثبت می‌شود و breakdown ساختگی تولید نمی‌شود.

## قرارداد decision lineage

فیلد `decision_lineage` با نسخه `candidate-decision-lineage-v1` دقیقاً مراحل زیر را
به همین ترتیب حمل می‌کند:

1. `dataset`
2. `experiment`
3. `signal`
4. `candidate`
5. `risk`
6. `position`
7. `exit`

وضعیت هر node یکی از موارد زیر است:

| وضعیت | معنی |
| --- | --- |
| `available` | شناسه یا outcome ذخیره‌شده موجود است و UI منبع را لینک می‌کند. |
| `not_created` | مرحله بعد در این رخداد ساخته نشده است؛ برای نمونه پس از risk rejection. |
| `not_evaluated` | مرحله risk به‌دلیل skip شدن Candidate ارزیابی نشده است. |
| `unavailable` | رکورد قدیمی evidence لازم را ندارد و نتیجه‌ای جعل نمی‌شود. |

Dataset، Experiment، Signal و Candidate به صفحات فقط‌خواندنی خود لینک می‌شوند.
برای Signal، endpoint دقیق
`GET /api/v1/research/experiments/{experiment_id}/signals/{signal_id}` و صفحه detail
افزوده شده است. Position و Exit تا پیش از صفحه اختصاصی TB2-021 به کارت دقیق Position
در Portfolio با fragment همان `position_id` لینک می‌شوند. Risk به breakdown آخرین
تصمیم در Candidate Detail متصل است.

## حالت ردشده و سازگاری

برای Candidate ردشده، node ریسک outcome برابر `rejected` دارد و Position و Exit هر
دو `not_created` هستند. برای `no_fill` یا Candidate skipped نیز علت canonical حفظ
می‌شود. Projectionهای قدیمی همچنان خوانده می‌شوند؛ نبود evidence وضعیت Risk را
`unavailable` می‌کند، اما outcome ذخیره‌شده approved/rejected و شناسه‌های
Dataset/Experiment/Signal/Candidate حفظ می‌شوند.

این تغییر schema پایگاه داده را عوض نمی‌کند و Candidate Projection موجود همچنان
قابل rebuild است.
