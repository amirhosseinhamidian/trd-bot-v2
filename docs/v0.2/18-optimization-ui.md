# TB2-015 — رابط Optimization و شواهد Robustness

این مرحله قراردادهای TB2-012 تا TB2-014 را بدون افزودن مسیر اجرای معامله به رابط پژوهش متصل
می‌کند. رابط فقط intent محدود را به API می‌فرستد؛ lifecycle، plan canonical، وزن‌های score و انتخاب
برنده همچنان فقط در Backend ساخته می‌شوند.

## مسیرهای رابط

- `/{locale}/optimizations`: فرم ساخت، برآورد بار کاری و کاتالوگ executionهای ماندگار.
- `/{locale}/optimizations/{execution_id}`: وضعیت اجرا، plan، ranking پایداری، trialهای ردشده و
  پیکربندی قابل بازتولید.
- ناوبری فارسی و انگلیسی Dashboard به کاتالوگ Optimization متصل است.

## ساخت و ادامهٔ اجرا

فرم Dataset و StrategyVersionهای قابل اجرا را از API می‌گیرد و برای هر پارامتر یک grid صریح با
مقادیر جداشده با ویرگول می‌سازد. قبل از enqueue، رابط همان مرزهای قابل برآورد Backend را کنترل
می‌کند:

- حداکثر ۲۰ مقدار برای هر پارامتر و ۱۰۰ ترکیب درخواستی؛
- حذف ترکیب نامعتبر crossover از برآورد Trialهای معتبر؛
- ۳ تا ۱۲ Fold از روی تعداد candle و WalkForwardConfig؛
- حداکثر ۳۰۰ اجرای `trial × fold`؛
- محدودیت Strategy metadata و BacktestConfig.

این کنترل‌ها فقط feedback زودهنگام هستند و جای validation مستقل Backend را نمی‌گیرند. پاسخ ۲۰۲
شامل execution و job است. شناسه execution در query string ذخیره می‌شود تا reload صفحه polling را
ادامه دهد. پس از موفقیت، رابط به detail همان execution می‌رود؛ failure کد و پیام ثبت‌شده را بدون
ساخت نتیجهٔ مصنوعی نمایش می‌دهد.

## مشاهدهٔ نتیجه

کاتالوگ وضعیت `queued/running/succeeded/failed`، پیشرفت Trial، تعداد Fold، objective و بهترین
Experiment را نشان می‌دهد. detail در وضعیت فعال execution persisted را refresh می‌کند و در نتیجهٔ
نهایی موارد زیر را نمایش می‌دهد:

- ترکیب‌های canonical plan و تعداد requested/skipped/valid؛
- نسخه score و شمار evaluated/eligible/rejected؛
- in-sample و out-of-sample objective، median excess، fold مثبت/معامله‌دار، dispersion، drawdown،
  generalization gap و score نهایی هر Trial؛
- علت fail-closed برای Trial ردشده؛
- لینک Experiment و Walk-Forward run که evidence را ساخته‌اند؛
- BacktestConfig و WalkForwardConfig لازم برای بازسازی.

executionهای legacy که `robustness_plan` یا `robustness_ranking` ندارند همچنان خواندنی‌اند و رابط به
جای جعل evidence، نبود ranking را صریح اعلام می‌کند.

## آزمون پذیرش مالک مخزن

1. grid معتبر را enqueue کن، صفحه را هنگام `running` reload و ادامهٔ progress را بررسی کن.
2. grid با بیش از ۱۰۰ ترکیب، Fold خارج از بازه و workload بالای ۳۰۰ را در UI و API رد کن.
3. fixture golden شامل یک Trial واجد شرایط و یک Trial بدون معامله را اجرا کن؛ برنده، score و علت رد
   باید با payload persisted برابر باشند.
4. لینک‌های Experiment و Walk-Forward را باز کن و IDهای lineage را با evaluation همان Trial تطبیق
   بده.
5. payload legacy بدون robustness را render کن و نبود ranking را بدون crash یا مقدار ساختگی ببین.
