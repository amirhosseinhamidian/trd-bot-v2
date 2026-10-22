# P5-07 — Portfolio Intelligence محدود برای Paper/Shadow

وضعیت: **پیاده‌سازی‌شده برای ورود به P5-08**

این مرحله Risk Gate پذیرفته‌شدهٔ P5-06 را در متن یک Portfolio شبیه‌سازی‌شده بررسی می‌کند و فقط
evidence و پیشنهاد ثبت می‌کند. هیچ position باز یا بسته نمی‌شود، موجودی واقعی خوانده نمی‌شود و هیچ
سفارش خارجی ساخته یا ارسال نمی‌گردد.

## 1. ورودی Portfolio

فقط modeهای `paper` و `shadow` قابل تحلیل‌اند. سرویس به‌صورت قطعی Portfolio فعال هم‌mode و هم‌Dataset
را که snapshot آن در آیندهٔ زمان تصمیم نیست انتخاب می‌کند:

- دقیقاً یک Portfolio: snapshot immutable همان Portfolio مصرف می‌شود؛
- بدون Portfolio: baseline خالی با سرمایهٔ مرجع `10,000` مربوط به P5-06 ساخته می‌شود؛
- بیش از یک Portfolio منطبق: نتیجه fail-closed و `portfolio_unavailable` است؛
- mode برابر `research`: نتیجه صریح `portfolio_unavailable` است.

baseline فقط داخل evidence این مرحله وجود دارد و رکوردی در `simulated_portfolios` ایجاد نمی‌کند.

## 2. Policy نسخهٔ اول

`decision-portfolio-v1` ثابت و tamper-evident است:

| کنترل | مقدار |
| --- | --- |
| حداکثر Gross Exposure | ۲۵٪ Equity شبیه‌سازی‌شده |
| حداکثر Concentration یک دارایی | ۲۰٪ Equity |
| حداکثر Absolute Correlation | ۰٫۸۵ |
| حداکثر زیان سناریویی | ۲٪ Equity |
| Drawdown محرک خروج ریسکی | ۱۵٪ |
| شوک‌های سناریو | ۱۰٪-، ۵٪-، ۵٪+ و ۱۰٪+ |

نسخه و checksum Policy داخل هر record ثبت می‌شود. تغییر هر limit نیازمند نسخهٔ تازه است.

## 3. Exposure و Concentration

برای positionهای باز، notional جاری از `quantity × current_price` محاسبه می‌شود. سپس notional پیشنهادی
P5-06 بدون تغییر Portfolio به snapshot افزوده می‌گردد تا موارد زیر به دست آیند:

- Gross exposure فعلی؛
- Gross exposure پس از Candidate؛
- exposure fraction فعلی و پیش‌بینی‌شده؛
- concentration دارایی پایه پس از Candidate.

Ledger شبیه‌سازی نسخهٔ فعلی فقط یک position باز هم‌زمان را پشتیبانی می‌کند؛ بنابراین وجود position باز
کنترل capacity را رد می‌کند و Candidate دوم اعمال نمی‌شود.

## 4. Correlation محدود و صریح

این نسخه از correlation ساختگی استفاده نمی‌کند:

- Portfolio خالی: `not_applicable` و کنترل correlation مجاز است؛
- position هم‌Pair: directional correlation دقیق همان Pair برابر `+1` یا `-1` ثبت می‌شود؛
- Pair دیگر: چون Dataset pin‌شده سری بازده آن دارایی را ندارد، `unavailable` ثبت و تصمیم fail-closed
  می‌شود.

Correlation آماری چنددارایی و covariance matrix متعلق به Portfolio Intelligence کامل آینده است.

## 5. Scenario Analysis و اثر Candidate

چهار شوک ثابت روی همهٔ positionهای باز و Candidate پیشنهادی اعمال می‌شوند. برای هر سناریو موارد زیر
ثبت می‌گردند:

- PnL positionهای موجود؛
- PnL Candidate؛
- Equity پیش‌بینی‌شده؛
- loss fraction نسبت به Equity snapshot.

بدترین loss fraction با سقف Policy مقایسه می‌شود. تمام محاسبات از snapshot، sizing و regime pin‌شده
انجام می‌شوند و clock، network یا account state ندارند.

## 6. پیشنهاد پذیرش، رد و خروج

پیشنهاد Candidate برای Paper/Shadow فقط در صورت عبور همهٔ کنترل‌های ordered زیر `accept` است:

1. Portfolio فعال؛
2. ظرفیت Ledger؛
3. exposure؛
4. concentration؛
5. correlation؛
6. scenario loss؛
7. سازگاری جهت Candidate با regime.

رد Candidate با reason code اختصاصی `portfolio_policy_rejected` ثبت می‌شود. برای position موجود نیز:

- عبور drawdown یا exposure از limit → `exit_risk`؛
- ناسازگاری جهت position با regime pin‌شده → `exit_regime`؛
- در غیر این صورت → `hold`.

این خروجی‌ها recommendation هستند و transition واقعی Ledger ایجاد نمی‌کنند.

## 7. Persistence و worker

Migration `20261020_0036` جدول append-only `decision_portfolio_intelligence` را اضافه می‌کند. رکورد به
Outcome مرحلهٔ `portfolio_simulation`، checksum کامل Risk Gate، snapshot، Candidate، Policy و تحلیل
متصل است.

Runner پایدار پس از Risk Gate پذیرفته‌شده، P5-07 را در همان transaction اجرا می‌کند. cancellation
پس از این مرحله تمام evidence همان اجرا را rollback می‌کند. retry و lease reclaim رکورد موجود را بدون
duplicate بازمی‌گردانند.

## 8. مرز دامنه

- فقط Portfolio شبیه‌سازی‌شده مصرف می‌شود؛
- هیچ asset واقعی، broker account، wallet، credential یا exchange balance وجود ندارد؛
- هیچ order intent، execution request یا external side effect ساخته نمی‌شود؛
- `offline_only=true` و `external_order_submission_allowed=false` در Contract، ORM و DB enforce
  می‌شوند؛
- مدیریت چنددارایی، correlation آماری، rebalancing و Portfolio Intelligence کامل خارج از این مرحله‌اند.

## 9. گیت خروج P5-07

- [x] Exposure و concentration فعلی و پس از Candidate ثبت می‌شوند.
- [x] Correlation ناموجود جعل نمی‌شود و fail-closed است.
- [x] Scenario analysis قطعی و نسخه‌دار است.
- [x] پیشنهاد Paper/Shadow با کنترل‌های توضیح‌پذیر ثبت می‌شود.
- [x] خروج مبتنی بر risk و تغییر regime فقط به‌صورت recommendation ثبت می‌شود.
- [x] Evidence اتمیک، append-only، idempotent و tamper-evident است.
- [x] Research و ambiguity به‌صورت `portfolio_unavailable` ثبت می‌شوند.
- [x] هیچ Portfolio یا سفارش واقعی تغییر نمی‌کند.

گام مجاز بعدی `P5-08 — API و رابط کاربری` است که این evidence را در صفحات موجود Strategy، Signal،
Candidate، Risk و Portfolio نمایش می‌دهد.
