# P5-05 — ساخت و رتبه‌بندی قطعی Candidate

وضعیت: **پیاده‌سازی‌شده برای ورود به P5-06**

این مرحله Signalهای پذیرفته‌شدهٔ P5-03 را به Candidateهای immutable و قابل audit تبدیل می‌کند و
رتبه‌بندی توضیح‌پذیر آن‌ها را در همان transaction اجرای پایدار P5-04 ثبت می‌کند. هیچ Risk approval،
تغییر Portfolio، ارتباط با صرافی یا ارسال سفارش واقعی در P5-05 وجود ندارد.

## 1. شرط ورود

Candidate فقط زمانی ساخته می‌شود که Outcome مرحلهٔ `strategy_evaluation` برابر `accepted` باشد.
Evaluationهای `rejected`، `deferred` یا `unavailable` مرحلهٔ Candidate جعلی دریافت نمی‌کنند. این قاعده
هم در service و هم در Repository enforce شده است و ترتیب Stageهای P5-02 را حفظ می‌کند.

## 2. سیاست نسخهٔ اول

`decision-candidate-v1` یک policy ثابت و tamper-evident است:

| مؤلفه | مقدار |
| --- | --- |
| اعتبار Candidate | ۴ Candle از `intent.requested_at` |
| نسبت Reward/Risk هدف | ۲٫۰ |
| وزن قدرت Signal | ۰٫۶۰ |
| وزن Confidence مربوط به Market Context | ۰٫۴۰ |

نسخه، پارامترها و checksum Policy داخل هر Candidate و Ranking record ثبت می‌شوند. تغییر هر مقدار
نیازمند Policy version تازه است.

## 3. ساخت Candidate

هر Signal جهت‌دار باید دقیقاً به یک Candle در Dataset immutable متصل شود. قیمت بسته‌شدن Candle،
entry است؛ low برای Long و high برای Short نقش invalidation را دارد و target با نسبت ۲٫۰ محاسبه
می‌شود. Signal خنثی، Candle گم‌شده، lineage متفاوت یا مرجع Dataset ناسازگار اجازهٔ استنتاج تصمیم
ندارد.

هویت Candidate از `evaluation_id`، `signal_id` و checksum Policy ساخته می‌شود. payload کامل شامل
Strategy، Dataset، Pair، Timeframe، زمان مشاهده، بازهٔ اعتبار، جهت، امتیاز Signal، Confidence Context
و trade plan است و checksum مستقل دارد.

## 4. رتبه‌بندی قطعی

امتیاز نهایی جمع وزن‌دار و quantized دو مؤلفهٔ زیر است:

1. قدر مطلق قدرت Signal؛
2. Confidence همان Market Context pin‌شده در Intent.

مرتب‌سازی ابتدا بر اساس امتیاز نزولی و در تساوی بر اساس `candidate_id` صعودی انجام می‌شود. rankها
پیوسته‌اند و تمام componentها همراه مقدار خام، وزن و مقدار وزن‌دار ذخیره می‌شوند. نبود Candidate قابل
ساخت با Outcome برابر `deferred` و reason code برابر `candidate_not_selectable` ثبت می‌شود؛ runtime
failure به تصمیم تجاری تبدیل نمی‌شود.

## 5. Persistence و اجرای پایدار

Migration `20261020_0034` جدول `decision_candidate_rankings` را اضافه می‌کند. هر Evaluation حداکثر
یک Ranking record دارد و این رکورد به Outcome مرحلهٔ `candidate_ranking` و Intent متصل است. تعداد
Signal، Candidate و موارد حذف‌شده، Candidate برتر، Policy checksum، زمان رتبه‌بندی و payload کامل
برای audit ذخیره می‌شوند.

Runner پایدار P5-04 پس از Strategy evaluation پذیرفته‌شده، Candidate ranking را در همان transaction
اجرا می‌کند. cancellation یا failure باعث rollback هر دو Stage می‌شود و retry یا lease reclaim همان
evidence را بدون duplicate برمی‌گرداند.

## 6. مرز امنیتی و عدم دامنه

- فقط Dataset، Strategy evidence و Market Context از پیش ذخیره‌شده خوانده می‌شوند؛
- Candidate هنوز پیشنهاد تحقیقاتی است و Risk approval محسوب نمی‌شود؛
- هیچ credential، account، wallet، balance، deposit، withdrawal یا live-order field وجود ندارد؛
- `offline_only=true` و `external_order_submission_allowed=false` در Contract، ORM و DB enforce
  می‌شوند؛
- Risk gate به P5-06 و Portfolio simulation به مراحل بعدی تعلق دارد.

## 7. گیت خروج P5-05

- [x] فقط Strategy evaluation پذیرفته‌شده وارد Candidate stage می‌شود.
- [x] هر Signal به Candle و Dataset دقیق خود متصل است.
- [x] Candidate ID، payload و Policy tamper-evident هستند.
- [x] trade plan بدون clock، network یا account state ساخته می‌شود.
- [x] امتیازدهی و tie-break کاملاً قطعی و توضیح‌پذیر است.
- [x] حالت بدون Candidate به‌صورت fail-closed و audit-friendly ثبت می‌شود.
- [x] Ranking record اتمیک، append-only و idempotent است.
- [x] migration، downgrade، SQLite و PostgreSQL round-trip پوشش داده شده‌اند.
- [x] worker cancellation، retry و reclaim semantics قبلی را حفظ می‌کند.

گام مجاز بعدی `P5-06 — Risk Gate and Position Sizing` است. آن مرحله فقط Candidateهای رتبه‌بندی‌شده
را با policy ریسک نسخه‌دار بررسی می‌کند و همچنان هیچ سفارش واقعی ارسال نخواهد کرد.
