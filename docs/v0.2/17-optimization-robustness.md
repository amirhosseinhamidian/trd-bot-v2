# TB2-014 — Robustness و Walk-Forward برای Optimization

## قرارداد ورودی و کران اجرا

هر درخواست جدید Optimization باید `walk_forward_config` صریح داشته باشد. Backend پیش از enqueue
همان Dataset immutable را plan می‌کند و فقط زمانی درخواست را می‌پذیرد که:

- حداقل ۳ و حداکثر ۱۲ fold زمانی کامل تولید شود؛
- test windowها طبق قرارداد موجود Walk-Forward هم‌پوشانی نداشته باشند؛
- حاصل `trial_count × fold_count` از ۳۰۰ اجرای validation بیشتر نشود.

شناسه plan، تعداد fold، workload، policy، score version و وزن‌های ثابت داخل execution snapshot
می‌شوند و در کلید idempotency حضور دارند. بنابراین تغییر fold config submission مستقلی می‌سازد.

## امتیاز نسخه‌دار

`optimization-robustness-score-v1` همهٔ مقدارها را به شکل Decimal و با breakdown قابل ممیزی ذخیره
می‌کند:

| مولفه | اثر |
| --- | ---: |
| objective میانگین خارج‌ازنمونه | `+ 0.45` |
| median excess return | `+ 0.15` |
| سهم foldهای با بازده مثبت | `+ 0.10` |
| سهم foldهای دارای معامله | `+ 0.10` |
| mean absolute deviation بازده foldها | `- 0.05` |
| بدترین max drawdown خارج‌ازنمونه | `- 0.05` |
| افت objective از in-sample به out-of-sample | `- 0.10` |

برای objective مربوط به max drawdown جهت مقدار قبل از scoring معکوس می‌شود. trial بدون حتی یک fold
دارای معامله با علت `insufficient_traded_folds` نگهداری، اما از ranking حذف می‌شود. اگر هیچ trial
واجد شرایط نباشد execution با `no_robust_trial` به‌صورت fail-closed تمام می‌شود.

ترتیب tie-break قطعی است: score، objective خارج‌ازنمونه، median excess، drawdown کمتر و در پایان
`experiment_id` واژه‌نامه‌ای.

## persistence و بازیابی

برای هر trial دو شاهد immutable وجود دارد: Experiment کامل روی Dataset و WalkForwardResearchRun روی
foldهای test. پس از ثبت هر دو، `OptimizationTrialEvaluation` همراه IDها در execution نوشته می‌شود.
اگر worker بعد از ذخیرهٔ یکی از شاهدها قطع شود، IDهای محتوایی در retry همان رکورد را reuse می‌کنند و
اجرا از `completed_trials` ادامه می‌یابد. progress داخل هر fold heartbeat می‌شود.

مدل‌های جدید داخل `payload_json` جدول موجود ذخیره می‌شوند؛ ستون و migration تازه لازم نیست. payload
قدیمی بدون robustness plan همچنان خوانده و با ranking legacy اجرا می‌شود، اما API از این مرحله فقط
executionهای robust ایجاد می‌کند.

## شواهد پذیرش مرحله

تست‌های مرحله باید plan سه-fold، سقف ۳۰۰ اجرا، golden overfit، رد no-trade، idempotency fold config،
resume پس از ذخیره Walk-Forward run و مسیر کامل SQLAlchemy worker را پوشش دهند. نتیجهٔ واقعی گیت‌ها
روی SHA کاربر ثبت می‌شود.
