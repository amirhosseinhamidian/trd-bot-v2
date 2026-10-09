# Nexora UI Phase 6 — Quality, Regression & Release

این سند، گیت انتشار فاز نهایی بازطراحی رابط Nexora را روی شاخه
`refactor/nexora-ui-foundation` ثبت می‌کند. مبنای P6، کامیت `30b2ece` پس از پذیرش P5-08 است و
هدف نهایی، تثبیت UI Foundation پیش از تدوین پروپوزال TRD BOT v0.3.0 است.

## برنامه مرحله‌ای P6

| مرحله     | محدوده                                                                             | وضعیت       |
| --------- | ---------------------------------------------------------------------------------- | ----------- |
| **P6-01** | قرارداد مرکزی ۲۱ route، regression پایداری ۴۲ مسیر fa/en و baseline چک‌لیست انتشار | ✅ انجام شد |
| **P6-02** | smoke مسیرهای بحرانی کاربر در فارسی و انگلیسی                                      | ✅ انجام شد |
| **P6-03** | smoke تم روشن/تیره، تغییر دوطرفه locale و کنترل hydration                          | ✅ انجام شد |
| **P6-04** | smoke responsive/visual در عرض‌های `360`، `390`، `768`، `1024` و `1440`            | ✅ انجام شد |
| **P6-05** | accessibility smoke، پیمایش کامل keyboard و focus order                            | ✅ انجام شد |
| **P6-06** | regression قرارداد Backend API، CORS و رفتار base URL                              | ✅ انجام شد |
| **P6-07** | حذف dead code، copy و componentهای legacy/بدون‌مصرف                                | ✅ انجام شد |
| **P6-08** | release notes، migration notes، گیت نهایی و Freeze رابط Nexora                     | ⏳          |

## قرارداد پایداری routeها

- منبع واحد inventory در `frontend/src/platform/route-contract.ts` نگهداری می‌شود.
- ۲۱ صفحه زیر `[locale]` باید بدون حذف یا تغییر نام باقی بمانند.
- برای localeهای `fa` و `en` در مجموع ۴۲ الگوی public یکتا تولید می‌شود.
- نام پارامترهای dynamic بخشی از قرارداد عمومی است و تغییر آن regression محسوب می‌شود.
- تمام pageها باید locale نامعتبر را با `notFound()` رد کنند.
- درخواست بدون prefix باید مطابق `defaultLocale` به مسیر فارسی هدایت شود.

## مسیرهای بحرانی پذیرش

1. Overview و ورود به مراحل Research
2. Dataset catalog و Dataset detail
3. Experiment detail، Walk-forward detail و analytics
4. Candidate و Risk، شامل وضعیت تصمیم و علت رد
5. Historical Portfolio catalog، Portfolio detail و Position detail
6. Connections و Monitoring
7. تغییر دوطرفه locale و theme
8. navigation موبایل با touch و keyboard

## ماتریس گیت انتشار

| گیت               | فرمان یا شاهد                                                | وضعیت              |
| ----------------- | ------------------------------------------------------------ | ------------------ |
| Format            | `npm run format:check`                                       | الزامی در هر مرحله |
| Lint              | `npm run lint`                                               | الزامی در هر مرحله |
| Unit/Component    | `npm test`                                                   | الزامی در هر مرحله |
| Production build  | `npm run build`                                              | الزامی در هر مرحله |
| Route parity      | ۲۱ فایل / ۴۲ الگوی fa/en                                     | پوشش P6-01         |
| Critical journeys | smoke در fa/en                                               | P6-02              |
| Theme/locale      | light/dark و fa/en                                           | P6-03              |
| Responsive        | `360/390/768/1024/1440`                                      | P6-04              |
| Accessibility     | keyboard، focus، landmark و نام قابل‌دسترسی                  | P6-05              |
| API integration   | contract، CORS و base URL                                    | P6-06              |
| Visual baseline   | screenshot از Shell و صفحات بحرانی در صورت افزودن Playwright | P6-04/P6-08        |

افزودن Playwright در P6-01 انجام نمی‌شود؛ baseline تصویری طبق پروپوزال فقط در صورتی اجباری است که
toolchain آن در پروژه اضافه شود.

## شاهد پذیرش P6-01

- inventory تکراری از تست معماری حذف و به قرارداد مرکزی متصل شد.
- تعداد ۲۱ route و ۴۲ الگوی localeدار، uniqueness و مسیرهای ریشه تست می‌شوند.
- ۹ مسیر dynamic با نام دقیق پارامترهای عمومی regression-protect شده‌اند.
- guard مربوط به locale نامعتبر روی تمام ۲۱ page بررسی می‌شود.
- رفتار redirect مسیر بدون locale به `defaultLocale` تحت تست قرارداد قرار گرفت.

## شاهد پذیرش P6-02

- شش سفر بحرانی کاربر به‌صورت route-level در هر دو locale فارسی و انگلیسی اجرا می‌شوند.
- ۱۵ صفحه حیاتی و در مجموع ۳۰ نقطه ورود localeدار تحت smoke خودکار قرار دارند.
- Overview و activity، کاتالوگ و جزئیات Dataset، و کاتالوگ/جزئیات/analytics مربوط به Experiment و
  Walk-forward پوشش داده می‌شوند.
- Candidate catalog/detail، شواهد lineage و Risk status با داده پرتفوی بررسی می‌شوند.
- Historical Portfolio از catalog تا detail و Position evidence اجرا می‌شود.
- Connections و Monitoring ضمن کنترل wiring داده، locale صحیح را تا screen نهایی حفظ می‌کنند.
- تست‌ها علاوه بر render contract، آرگومان‌های شناسه و pagination مهم را در مرز route و API کنترل
  می‌کنند.

## شاهد پذیرش P6-03

- تمام ۲۱ route در هر دو جهت `fa → en` و `en → fa` جابه‌جا و سپس به مسیر مبدأ بازگردانده می‌شوند.
- مسیرهای تو‌در‌تو و شناسه‌های URL-encoded هنگام تغییر locale بدون تغییر باقی می‌مانند.
- منطق تغییر locale از Shell جدا و به یک قرارداد pure و قابل‌آزمون منتقل شد.
- ThemeToggle با ترجیح `light` که پیش از hydration اعمال شده، در هر دو زبان واقعاً hydrate می‌شود و
  هیچ هشدار mismatch تولید نمی‌کند.
- تغییر `light → dark` پس از hydration، هم‌زمان DOM، `color-scheme`، متن دسترس‌پذیر و storage را
  به‌روزرسانی می‌کند.
- bootstrap تم با `beforeInteractive` و تنها suppression مجاز روی document root تحت regression
  test قرار گرفت.

## شاهد پذیرش P6-04

- ماتریس release برای عرض‌های دقیق `360`، `390`، `768`، `1024` و `1440` به یک قرارداد مرکزی تبدیل
  شد.
- حالت‌های mobile، tablet، desktop و wide و مرز دقیق breakpointهای `768`، `1024` و `1440` تحت
  regression test هستند.
- Shell در هر پنج viewport با قرارداد bottom navigation، tablet drawer یا fixed sidebar smoke
  می‌شود؛ gutter، فضای پایین موبایل و حداکثر عرض محتوا نیز کنترل می‌شوند.
- قراردادهای fluid layout برای Overview، Dataset، Experiment، Walk-forward، Candidate، Risk،
  Portfolio، Connections و Monitoring بررسی می‌شوند و استفاده از `100vw`، `w-screen` یا مخفی‌کردن
  overflow در سطح صفحه ممنوع است.
- مسیرهای نموداری Experiment، Walk-forward و Portfolio در موبایل stacked selector و summary متنی را
  حفظ می‌کنند.
- Playwright یا مرورگر headless در toolchain پروژه وجود ندارد؛ بنابراین مطابق پروپوزال screenshot
  baseline در این مرحله ایجاد نشده و هیچ ادعای visual-diff پیکسلی ثبت نمی‌شود.

## شاهد پذیرش P6-05

- walkthrough کیبورد Shell در هر دو زبان فارسی و انگلیسی اجرا می‌شود.
- ترتیب skip link → main content → اکشن اصلی → لینک شواهد تحت تست است و landmarkهای banner، main،
  sidebar و mobile navigation نام قابل‌دسترسی دارند.
- focus trap مربوط به tablet drawer و mobile menu در هر دو زبان، شامل wrap، خروج با Escape و بازگشت
  focus به trigger آزموده می‌شود.
- عناصر hidden، inert، disabled، `aria-disabled` و input مخفی از چرخه focus trap حذف می‌شوند و
  container خالی fallback امن دریافت می‌کند.
- positive `tabIndex` و `autoFocus` سفارشی در featureها ممنوع شده‌اند.
- تمام scroll regionهای جدول‌های feature دارای نام و قابلیت focus هستند و همه progressbarها نام،
  کمینه، بیشینه و مقدار جاری قابل‌دسترسی دارند.

## شاهد پذیرش P6-06

- مجموعه ۶۳ عملیات مصرف‌شده توسط frontend مستقیماً با OpenAPI برنامه تطبیق داده می‌شود؛ حذف route یا
  تغییر verb اکنون regression تست را شکست می‌دهد.
- شکاف واقعی قرارداد Experiment برطرف شد: endpoint نسخه‌دار و فقط‌خواندنی
  `GET /api/v1/research/experiments/{experiment_id}/analytics` داده‌های توزیع معامله، بازده ماهانه،
  دوره‌های drawdown و تعریف metricها را از نتیجه immutable آزمایش تولید می‌کند.
- fallback محلی، مقدار خالی/فاصله‌دار، حذف slash انتهایی، prefix نسبی و same-origin root برای
  `NEXT_PUBLIC_API_BASE_URL` تحت تست قرار گرفتند.
- خطاهای JSON و متنی transport با status و payload اصلی حفظ می‌شوند.
- preflight برای هر دو origin توسعه، متدهای `GET`/`POST` و header محتوای JSON آزموده می‌شود؛ origin
  ناشناس رد می‌شود و credential در CORS مجاز نیست.

## شاهد پذیرش P6-07

- سه facade قدیمی `lib/api/{client,types,portfolio-analytics}` حذف و تست‌های رفتاری مستقیماً به
  client و typeهای feature-owned متصل شدند.
- `LanguageSwitcher` قدیمی که با کنترل locale داخل Platform Shell جایگزین شده بود، همراه تست منسوخ
  آن حذف شد.
- client بدون‌مصرف جزئیات Job و عملیات متناظر آن از inventory مصرف frontend کنار گذاشته شد؛ typeهای
  Job که در Monitoring، Connection و Optimization مصرف واقعی دارند حفظ شدند.
- ۱۳ تست تکراری mapping facade حذف و با guard مرکزی معماری جایگزین شدند؛ در مجموع ۲۰ فایل legacy یا
  تکراری از درخت frontend پاک شد.
- graph وابستگی production اکنون از entry pointهای Next بررسی می‌شود و اضافه‌شدن module یتیم تست را
  شکست می‌دهد. فقط قراردادهای test-only مربوط به route و responsive به‌صورت صریح مستثنا هستند.
- تمام copyهای feature موجود از مسیر production قابل‌دسترسی‌اند. متن‌های `legacy` مربوط به نمایش
  رکوردهای قدیمی عمداً حفظ شدند، چون قرارداد سازگاری داده‌اند و dead copy نیستند.

## گیت خروج P6

P6 فقط زمانی بسته می‌شود که feature parity نسخه v0.2.0، پایداری routeها، ماتریس responsive و تمام
گیت‌های frontend CI هم‌زمان سبز باشند. پس از آن UI Foundation فریز و ورودی پروپوزال TRD BOT
v0.3.0 خواهد شد.
