# Nexora UI Phase 6 — Quality, Regression & Release

این سند، گیت انتشار فاز نهایی بازطراحی رابط Nexora را روی شاخه
`refactor/nexora-ui-foundation` ثبت می‌کند. مبنای P6، کامیت `30b2ece` پس از پذیرش P5-08 است و
هدف نهایی، تثبیت UI Foundation پیش از تدوین پروپوزال TRD BOT v0.3.0 است.

## برنامه مرحله‌ای P6

| مرحله     | محدوده                                                                             | وضعیت       |
| --------- | ---------------------------------------------------------------------------------- | ----------- |
| **P6-01** | قرارداد مرکزی ۲۱ route، regression پایداری ۴۲ مسیر fa/en و baseline چک‌لیست انتشار | ✅ انجام شد |
| **P6-02** | smoke مسیرهای بحرانی کاربر در فارسی و انگلیسی                                      | ✅ انجام شد |
| **P6-03** | smoke تم روشن/تیره، تغییر دوطرفه locale و کنترل hydration                          | ⏳          |
| **P6-04** | smoke responsive/visual در عرض‌های `360`، `390`، `768`، `1024` و `1440`            | ⏳          |
| **P6-05** | accessibility smoke، پیمایش کامل keyboard و focus order                            | ⏳          |
| **P6-06** | regression قرارداد Backend API، CORS و رفتار base URL                              | ⏳          |
| **P6-07** | حذف dead code، copy و componentهای legacy/بدون‌مصرف                                | ⏳          |
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

## گیت خروج P6

P6 فقط زمانی بسته می‌شود که feature parity نسخه v0.2.0، پایداری routeها، ماتریس responsive و تمام
گیت‌های frontend CI هم‌زمان سبز باشند. پس از آن UI Foundation فریز و ورودی پروپوزال TRD BOT
v0.3.0 خواهد شد.
