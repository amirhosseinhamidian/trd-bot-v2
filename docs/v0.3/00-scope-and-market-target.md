# P0-01 — تثبیت محدوده و بازار هدف نسخهٔ سوم

وضعیت: **فریز شده برای ادامهٔ Phase 0**

تاریخ تصمیم: `2026-10-09`

شاخهٔ توسعه: `feature/v0.3-market-intelligence`

مبنای کد: `refactor/nexora-ui-foundation` در commit
`9fa1821c3c6bb9ac2eb3874fb2acf9cb22e12562`

این سند نخستین گیت اجرایی پروپوزال `Nexora / TRD BOT v0.3.0` است. هدف آن جلوگیری از
گسترش کنترل‌نشدهٔ دامنه پیش از طراحی قرارداد رویداد، SLO و ظرفیت است. فریز این سند به معنی
تکمیل Phase 0 یا آماده بودن سامانه برای دادهٔ زنده نیست.

## 1. تصمیم محصول

`TRD BOT v0.3.0` یک نسخهٔ **Market Intelligence نزدیک به real-time برای Research و Shadow**
است. سیستم بازار را به‌صورت مستمر مشاهده و تفسیر می‌کند، شواهد تصمیم را نگه می‌دارد و فقط در
زمان لازم توجه کاربر را جلب می‌کند؛ اما سفارش واقعی ایجاد، ارسال، اصلاح یا لغو نمی‌کند.

مرزهای ثابت نسخه:

- `Nexora` پلتفرم مشترک و `TRD BOT` محصول فعال تحقیق و تصمیم‌یاری معامله است.
- محصول در v0.3 همچنان `single-user` و `research-first` باقی می‌ماند.
- مسیر بلوغ مجاز `Research -> Shadow -> Paper` است.
- `Live Execution`، اتصال حساب معاملاتی و credential دارای مجوز معامله خارج از دامنه‌اند.
- معماری پایه همان modular monolith فعلی است؛ جداسازی سرویس فقط با نیاز واقعی scale، isolation
  یا deployment توجیه می‌شود.

## 2. بازار هدف

بازار مرجع v0.3 **Crypto Spot** است. این انتخاب ادامهٔ مستقیم قراردادهای داده، providerها،
Dataset، Strategy، Candidate، Risk و Paper/Shadow موجود است و ریسک توسعهٔ هم‌زمان چند بازار را
کاهش می‌دهد.

| موضوع | تصمیم فریز شده |
| --- | --- |
| کلاس دارایی | رمزارز |
| نوع بازار | Spot |
| حالت استفاده | Research، Shadow و Paper؛ بدون Live |
| منبع داده | endpointهای عمومی و فقط‌خواندنی providerهای allowlisted |
| providerهای موجود | `binance-public`، `kraken-public` و `nobitex-public` |
| بازه‌های موجود | `15m`، `1h`، `4h` و `1d` |
| زمان مرجع | UTC و event time مستقل از processing time |
| کاربر هدف | معامله‌گر یا پژوهشگر مستقل با نیاز به کنترل و evidence روشن |

در این نسخه «نزدیک به real-time» به معنی دریافت و پردازش پیوسته با polling یا stream کنترل‌شده
و SLO قابل اندازه‌گیری است؛ نه tick trading، HFT یا تضمین latency صرافی. انتخاب adapter اصلی،
cadence هر timeframe و universe اولیه پس از ثبت baseline واقعی providerها در ادامهٔ Phase 0
نهایی می‌شود و نباید در کد به یک provider یا quote currency خاص hard-code شود.

فلزات، سهام و داده‌های اقتصاد کلان فقط می‌توانند بعداً به شکل منبع تحقیقاتی read-only بررسی
شوند. ورود هر بازار تازه به مسیر Signal/Candidate/Risk نیازمند قرارداد مستقل calendar، liquidity،
quality و risk همان بازار است.

## 3. قابلیت‌های داخل محدوده

قابلیت‌های v0.3 باید دست‌کم یکی از سه نتیجه را ایجاد کنند: بهبود تازگی داده، غنی‌تر شدن context
تصمیم یا هدایت دقیق‌تر توجه کاربر.

### Observe

- polling یا streaming نزدیک به real-time برای Research/Shadow؛
- watchlist و market universe؛
- freshness، lag و provider health قابل مشاهده؛
- ثبت raw observation و normalization قابل audit.

### Contextualize

- Dataset و Feature Set چندبازهٔ زمانی با alignment صریح؛
- Market Regime قطعی و نسخه‌دار برای trend/range/volatility؛
- confidence، evidence، window، expiry و algorithm version برای هر assessment؛
- replay از دادهٔ ثبت‌شده بدون الزام تماس دوباره با provider.

### Decide

- استفاده از Strategy، Signal، Candidate ranking و Risk gate موجود روی context جاری؛
- نمایش علت پذیرش، رد یا uncertainty؛
- exposure، concentration، correlation و scenario برای پرتفوی شبیه‌سازی‌شده؛
- حفظ lineage از observation تا decision و outcome.

### Notify

- Alert rule نسخه‌دار با severity، expiry و source event؛
- deduplication، suppression، acknowledgement، snooze و quiet hours؛
- Notification Inbox در لایهٔ Nexora با منطق تولید alert در domain صاحب قابلیت؛
- جلوگیری از انتشار alert مبتنی بر دادهٔ stale یا ناقص و ثبت علت suppression.

### Learn

- Shadow pipeline بدون سفارش واقعی؛
- Outcome Journal برای lifecycle تصمیم و alert؛
- سنجش drift، performance و false-positive؛
- daily brief و export حداقلی برای بازبینی انسانی.

بدهی‌های ضروری v0.2، شامل worker migration و export baseline، در P1 تعیین تکلیف می‌شوند و پیش
از شروع Live Data Foundation باید گیت‌های v0.2 دوباره سبز باشند.

## 4. موارد صریحاً خارج از محدوده

- اتصال حساب صرافی یا کارگزاری؛
- دریافت یا نگهداری API key/secret دارای مجوز معامله؛
- ارسال، اصلاح یا لغو سفارش واقعی؛
- کیف پول، واریز، برداشت، custody یا انتقال وجه؛
- copy trading، شبکهٔ اجتماعی یا strategy marketplace؛
- اپلیکیشن native موبایل؛
- همکاری سازمانی و چندکاربرهٔ کامل؛
- پشتیبانی معاملاتی هم‌زمان از همهٔ بازارهای مالی؛
- تضمین سود یا توصیهٔ مالی شخصی‌سازی‌شده بدون evidence و uncertainty؛
- ML regime production پیش از dataset برچسب‌خورده، benchmark، calibration و drift monitoring؛
- ساخت کامل Portfolio Intelligence یا Asset Registry برای دارایی‌های مالی و فیزیکی.

هیچ endpoint، route، فرم یا job عمومی با مفهوم live order، trade execution، withdrawal یا
credential معامله نباید در v0.3 اضافه شود. آزمون `tests/test_release_security_boundary.py` این
مرز را در API، OpenAPI، frontend و provider catalog محافظت می‌کند.

## 5. جریان ارزش مرجع

1. کاربر provider و market universe را انتخاب و جریان Research/Shadow را فعال می‌کند.
2. سیستم observation را normalize و quality-check می‌کند و window نسخه‌دار می‌سازد.
3. Feature Set و Regime Assessment چندبازه‌ای با confidence و evidence تولید می‌شوند.
4. Strategyهای منتشرشده ارزیابی و خروجی وارد Signal، Candidate ranking و Risk gate می‌شود.
5. فقط رویداد دارای freshness، importance و preference معتبر به Alert تبدیل می‌شود.
6. کاربر evidence را بررسی و در صورت تمایل lifecycle را در Shadow یا Paper دنبال می‌کند.
7. Outcome به Journal بازمی‌گردد تا drift، performance و rule quality قابل ارزیابی باشد.

هر مرحله باید `status`، input reference و output version مستقل داشته باشد. شکست یک مرحله مجاز
نیست دادهٔ قبلی را تغییر دهد یا خروجی مرحلهٔ بعد را معتبر جلوه دهد.

## 6. قراردادهای سازگاری

- routeهای فعلی، APIهای `/api/v1` و قراردادهای UI فریز شدهٔ Nexora بدون migration صریح شکسته
  نمی‌شوند.
- Snapshotها، Strategy versionها، Experimentها و Journalهای موجود immutable باقی می‌مانند.
- هر payload تازه دارای schema version و هر handler تازه allowlisted و idempotent است.
- fallback پنهان مجاز نیست؛ fallback باید status و evidence قابل مشاهده داشته باشد.
- event time، watermark، late arrival و window finalization پیش از پیاده‌سازی ingestion جدید
  قرارداد صریح خواهند داشت.
- هیچ قابلیت v0.3 مجاز نیست credential معاملاتی را از UI، API، environment contract یا log
  درخواست کند.

## 7. تقسیم Phase 0

| مرحله | خروجی | گیت خروج |
| --- | --- | --- |
| P0-01 | محدوده، بازار هدف و مرز ایمنی | همین سند فریز و security boundary سبز |
| P0-02 | baseline کد، بدهی v0.2 و inventory ظرفیت | هر بدهی owner و phase مشخص دارد |
| P0-03 | event contract، schema و ADRهای ingestion/window | نمونه payload و failure semantics پذیرفته شده |
| P0-04 | SLO، retention، provider budget و capacity benchmark | اعداد قابل اندازه‌گیری روی محیط مرجع ثبت شده |
| P0-05 | acceptance matrix و freeze نهایی Phase 0 | همهٔ تصمیم‌ها شاهد، owner و مرحله دارند |

## 8. تصمیم‌های عمداً باز

موارد زیر در P0-01 حدس زده یا در کد hard-code نمی‌شوند:

- provider اصلی و fallback order؛
- watchlist اولیه و pair mapping میان providerها؛
- polling cadence و امکان stream برای هر provider؛
- freshness SLO، watermark و late-arrival budget؛
- retention مربوط به raw observation و provisional window؛
- ظرفیت queue، نرخ ingest، latency و هزینهٔ ذخیره‌سازی؛
- thresholdهای Regime، Alert و Portfolio scenario؛
- ورود Copilot توضیحی read-only به محدودهٔ تحویل v0.3.

## 9. معیار خروج P0-01

- [x] Crypto Spot به‌عنوان بازار مرجع v0.3 تثبیت شد.
- [x] Research/Shadow/Paper از Live Execution تفکیک شد.
- [x] قابلیت‌های داخل و خارج محدوده ثبت شدند.
- [x] user، provider و timeframe baseline مشخص شدند.
- [x] قراردادهای سازگاری و امنیت به تست موجود متصل شدند.
- [x] تصمیم‌های باز به مراحل بعدی Phase 0 ارجاع شدند.
- [x] گیت‌های بررسی این مرحله ثبت شدند.

## 10. شاهد بررسی

روی checkout این مرحله:

- `frontend`: تعداد `91` فایل تست و `429` تست با موفقیت اجرا شد.
- `python -m compileall -q src tests`: بدون خطای syntax اجرا شد.
- بررسی ایستای مرز امنیتی، routeهای backend/frontend و نام فیلدهای credential ممنوع را بدون
  violation گزارش کرد.
- `git diff --check`: بدون خطای whitespace اجرا شد.

محیط اجرای فعلی dependencyهای Python پروژه و `pytest` را همراه نداشت؛ بنابراین اجرای مستقیم
`tests/test_release_security_boundary.py` و `tests/test_release_version.py` در این checkout ممکن
نشد. این محدودیت محیطی باید در CI یا محیط توسعهٔ مالک مخزن با همان commit دوباره بررسی شود. این
پچ فقط مستندات را تغییر می‌دهد و هیچ فایل runtime، API، database یا frontend را تغییر نمی‌دهد.

پس از سبز شدن گیت‌های این مرحله، گام مجاز بعدی فقط `P0-02 — baseline و debt/capacity
inventory` است؛ شروع Live Data Foundation پیش از بسته شدن کل Phase 0 و P1 مجاز نیست.
