# P5-01 — قراردادهای نسخه‌دار Decision Intelligence

وضعیت: **پیاده‌سازی‌شده برای ورود به P5-02**

این مرحله قرارداد ورودی و معنای خروجی زنجیرهٔ تصمیم را فریز می‌کند. هیچ migration، worker، API، UI،
ارزیابی Strategy، تولید Candidate یا تغییر Portfolio در P5-01 انجام نمی‌شود. مرز امنیتی همچنان
`Crypto Spot / public read-only / Research-Shadow-Paper` است و تمام قراردادها صریحاً
`offline_only=true` و `external_order_submission_allowed=false` دارند.

## 1. هدف

فازهای قبلی Observation، Market Context و Alert را پایدار کرده‌اند. P5 باید خروجی Context را بدون
شکستن مسیرهای v0.2 به Strategy، Signal، Candidate، Risk و Portfolio شبیه‌سازی‌شده متصل کند. پیش از
افزودن persistence یا runtime، هر ارزیابی باید ورودی دقیق، identity قطعی، idempotency و semantics
fail-closed داشته باشد.

## 2. واژگان فریز‌شده

### Mode

| مقدار | معنا |
| --- | --- |
| `research` | ارزیابی تحقیقاتی بدون lifecycle پرتفوی |
| `shadow` | مشاهدهٔ تصمیم در Shadow بدون سفارش واقعی |
| `paper` | استفاده در پرتفوی کاملاً شبیه‌سازی‌شده |

### Stage

ترتیب منطقی زنجیره برابر است با:

1. `strategy_evaluation`
2. `candidate_ranking`
3. `risk_gate`
4. `portfolio_simulation`

وجود نام Stage در قرارداد به معنی پیاده‌سازی runtime آن در P5-01 نیست؛ هر Stage در مرحلهٔ مالک خود
فعال می‌شود.

### Disposition

| مقدار | معنا |
| --- | --- |
| `accepted` | ورودی معتبر است و Stage جاری اجازهٔ ادامه می‌دهد |
| `rejected` | ورودی معتبر بوده ولی قاعدهٔ Strategy یا Risk آن را رد کرده است |
| `deferred` | ورودی معتبر است اما اقدام فعلی لازم نیست؛ مانند Signal خنثی |
| `unavailable` | پیش‌شرط معتبر وجود ندارد و هیچ تصمیم معاملاتی نباید استنتاج شود |

`accepted` هیچ reason code ندارد. سه وضعیت دیگر باید حداقل یک reason code مرتب، یکتا و نسخه‌دار
داشته باشند. خطای runtime، exception یا retry exhaustion به‌عنوان تصمیم تجاری جعل نمی‌شود و در
Monitoring ثبت خواهد شد.

## 3. Referenceهای tamper-evident

### Dataset

`DecisionDatasetReference` شناسه، schema version، source، pair، timeframe، بازه، تعداد Candle و
checksum محتوای Dataset immutable را pin می‌کند. خود Candleها در payload job تکرار نمی‌شوند.

### Strategy

`DecisionStrategyReference` شامل نام، نسخه، `behavior_fingerprint`، lifecycle و تمام پارامترهای
canonical است. پارامترها بر اساس نام مرتب می‌شوند و parameter ناقص، اضافی یا نوع نادرست پذیرفته
نمی‌شود. Strategy deprecated می‌تواند برای ثبت یک نتیجهٔ `unavailable` capture شود، اما اجازهٔ
خروجی accepted در مراحل بعد را ندارد.

### Market Context

`MarketContextDecisionReference` assessment immutable، checksum کامل آن، زمان `as_of`، expiry،
regime، confidence و نتیجهٔ مصرف‌پذیری را در زمان درخواست pin می‌کند. Context stale یا ناقص حذف
نمی‌شود؛ به‌صورت غیرقابل‌مصرف capture می‌شود تا رد fail-closed قابل audit باشد.

## 4. Decision Policy

`DecisionPolicyDefinition` نسخه‌دار و immutable است. هر نسخه فقط predecessor بلافصل خود را ارجاع
می‌دهد و checksum کامل دارد. قرارداد v1 موارد زیر را اجبار می‌کند:

- Market Context قابل‌مصرف؛
- Strategy فعال؛
- source و pair یکسان میان Dataset و Context؛
- ممنوعیت Dataset دارای داده بعد از `context.as_of`؛
- فقط modeهای Research، Shadow و Paper؛
- ممنوعیت Live Execution و external order submission.

thresholdهای سازگاری Strategy/Regime و Risk در این مرحله حدس زده نمی‌شوند. آن‌ها باید در مراحل
P5-03 و P5-06 با policy مستقل، تست قطعی و checksum اضافه شوند.

## 5. Decision Evaluation Intent

`DecisionEvaluationIntent` از چهار reference دقیق تشکیل می‌شود:

1. Dataset؛
2. Strategy؛
3. Market Context؛
4. Decision Policy.

هویت ارزیابی و idempotency key از checksum همین چهار ورودی و mode ساخته می‌شود. در نتیجه retry یک
intent منطقی همان ID را بازمی‌گرداند و تغییر هر input یک evaluation تازه می‌سازد. `requested_at`
باید دقیقاً با زمان capture شدن Market Context برابر باشد.

ساخت Intent در mismatchهای pair، source، mode یا look-ahead رد می‌شود. غیرقابل‌مصرف بودن Context
یا غیرفعال بودن Strategy عمداً ساخت Intent را متوقف نمی‌کند، چون worker آینده باید یک outcome
قابل audit با disposition برابر `unavailable` ثبت کند.

## 6. Reason Codeهای v1

reason codeهای اولیه شامل policy/mode، availability و expiry Context، boundary mismatch، mismatch
Dataset، Strategy غیرفعال یا ناسازگار، Signal خنثی، Candidate غیرقابل‌انتخاب، رد Risk، نبود
Portfolio و uncertainty بالاتر از حد هستند. افزودن یا تغییر معنا نیازمند schema/policy version تازه
است.

## 7. سازگاری و عدم دامنه

- مدل‌های Strategy، Signal، Candidate و Risk موجود تغییر نمی‌کنند.
- route یا payload عمومی تازه‌ای در P5-01 وجود ندارد.
- persistence و migration به P5-02 تعلق دارد.
- اجرای Strategy و تولید Signal به P5-03 تعلق دارد.
- job، retry و reclaim به P5-04 تعلق دارد.
- هیچ credential، account، wallet، deposit، withdrawal یا live-order field مجاز نیست.

## 8. گیت خروج P5-01

- [x] Dataset، Strategy و Market Context reference نسخه‌دار و tamper-evident هستند.
- [x] Decision Policy دارای lineage نسخه و checksum قطعی است.
- [x] Evaluation Intent دارای ID و idempotency key قطعی است.
- [x] mismatchهای mode، pair، source و look-ahead fail-closed هستند.
- [x] Context غیرقابل‌مصرف برای outcome audit قابل capture است.
- [x] disposition و reason codeهای Stageها فریز شده‌اند.
- [x] مرز `offline_only` و ممنوعیت external order در schema enforce می‌شود.
- [x] قراردادها immutable و `extra="forbid"` هستند.
- [x] تست round-trip و checksum tampering وجود دارد.

گام مجاز بعدی `P5-02 — Persistence تصمیم و Evidence` است. افزودن worker یا اتصال Strategy به Context
پیش از persistence immutable و migration تست‌شده مجاز نیست.
