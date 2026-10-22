# P5-06 — Risk Gate و Position Sizing آفلاین

وضعیت: **پیاده‌سازی‌شده برای ورود به P5-07**

این مرحله Candidate برتر و پذیرفته‌شدهٔ P5-05 را با policy ریسک نسخه‌دار بررسی می‌کند و در صورت
قبولی، اندازهٔ موقعیت پیشنهادی را فقط بر اساس سرمایهٔ مرجع شبیه‌سازی‌شده محاسبه می‌کند. هیچ Portfolio
واقعی یا شبیه‌سازی‌شده‌ای در این مرحله تغییر نمی‌کند و هیچ سفارش خارجی ساخته یا ارسال نمی‌شود.

## 1. شرط ورود و semantics

Risk Gate فقط پس از Outcome برابر `accepted` برای Stage `candidate_ranking` اجرا می‌شود. Ranking
خالی یا deferred وارد این Stage نمی‌شود. فقط Candidate رتبهٔ اول ارزیابی می‌شود و identity، checksum
و lineage کامل Ranking در Risk record ثبت می‌گردد.

نتیجهٔ Stage یکی از دو حالت است:

- `accepted`: تمام کنترل‌ها عبور کرده‌اند و position sizing آفلاین وجود دارد؛
- `rejected / risk_policy_rejected`: حداقل یک کنترل رد شده و هیچ position sizing منتشر نمی‌شود.

## 2. سیاست نسخهٔ اول

`decision-risk-v1` ثابت و tamper-evident است:

| محدودیت | مقدار |
| --- | --- |
| سرمایهٔ مرجع در quote asset | ۱۰٬۰۰۰ |
| حداکثر ریسک هر موقعیت | ۱٪ سرمایهٔ مرجع |
| حداکثر notional | ۱۰٪ سرمایهٔ مرجع |
| حداقل امتیاز Ranking | ۰٫۳۰ |
| حداقل Reward/Risk | ۱٫۵ |
| دقت Quantity | ۸ رقم اعشار، گرد کردن رو به پایین |

سرمایهٔ مرجع account balance نیست و از هیچ حساب یا API صرافی خوانده نمی‌شود. صرفاً یک ورودی ثابت
Policy برای قابل‌بازتولید بودن محاسبهٔ آفلاین است.

## 3. کنترل‌های Risk Gate

کنترل‌ها همیشه با ترتیب ثابت و evidence مقدار واقعی/حد policy ثبت می‌شوند:

1. Candidate هنوز در بازهٔ اعتبار immutable خود باشد؛
2. امتیاز Ranking از حداقل policy کمتر نباشد؛
3. Reward/Risk از حداقل policy کمتر نباشد؛
4. maximum loss از risk budget تجاوز نکند؛
5. notional از exposure cap تجاوز نکند.

خطای integrity، lineage یا persistence به `rejected` تجاری تبدیل نمی‌شود و برای worker به‌عنوان خطای
غیرقابل retry بالا می‌آید.

## 4. محاسبهٔ Position Sizing

ابتدا دو سقف quantity محاسبه می‌شود:

- `risk_budget / unit_price_risk`؛
- `notional_cap / entry_price`.

کمترین مقدار انتخاب و با دقت هشت رقم اعشار رو به پایین گرد می‌شود. سپس notional و maximum loss از
همان quantity دوباره محاسبه و در Contract اعتبارسنجی می‌شوند. خروجی شامل quote asset، entry،
invalidation، target، quantity، notional، maximum loss و checksum مستقل است.

## 5. Persistence و worker

Migration `20261020_0035` جدول append-only `decision_risk_gates` را اضافه می‌کند. هر Evaluation حداکثر
یک Risk Gate دارد و به Outcome مرحلهٔ `risk_gate`، Ranking checksum، نسخه و checksum Policy و
assessment immutable متصل است.

Runner پایدار P5-04 پس از Candidate Ranking پذیرفته‌شده، Risk Gate را در همان transaction اجرا
می‌کند. cancellation پس از Risk Gate کل Strategy، Candidate و Risk evidence همان اجرا را rollback
می‌کند. retry و lease reclaim رکورد موجود را بدون duplicate بازمی‌گرداند.

## 6. مرز امنیتی و عدم دامنه

- فقط Candidate و Ranking immutable خوانده می‌شوند؛
- هیچ account balance، credential، API key، wallet، deposit یا withdrawal وجود ندارد؛
- Position sizing صرفاً پیشنهاد evidence برای Paper/Shadow آینده است؛
- approval باعث open position، reserve cash یا submit order نمی‌شود؛
- `offline_only=true` و `external_order_submission_allowed=false` در Contract، ORM و DB enforce
  می‌شوند.

## 7. گیت خروج P5-06

- [x] Policy ریسک نسخه‌دار، ثابت و tamper-evident است.
- [x] فقط Candidate برتر Ranking پذیرفته‌شده ارزیابی می‌شود.
- [x] تمام کنترل‌ها ordered و explainable هستند.
- [x] quantity با risk budget و notional cap محدود می‌شود.
- [x] Risk rejection هیچ position sizing قابل مصرفی منتشر نمی‌کند.
- [x] Evidence اتمیک، append-only و idempotent است.
- [x] migration، downgrade، SQLite و PostgreSQL round-trip پوشش داده شده‌اند.
- [x] cancellation، retry و reclaim بدون duplicate باقی می‌مانند.
- [x] هیچ مسیر live execution یا external order اضافه نشده است.

گام مجاز بعدی `P5-07 — Paper/Shadow Portfolio Decision Application` است. آن مرحله می‌تواند Risk Gate
پذیرفته‌شده را به lifecycle پرتفوی شبیه‌سازی‌شده متصل کند، اما مرز live execution همچنان بسته خواهد
ماند.
