# TB2-019 — قرارداد داشبورد ریسک پژوهشی

داشبورد Risk یک projection فقط‌خواندنی از `CandidateJournalEntry` و رویدادهای
`SimulatedPortfolio.timeline` است. این مرحله جدول یا migration تازه، endpoint تغییر وضعیت،
اتصال حساب و عملیات سفارش‌گذاری اضافه نمی‌کند.

## API و محدوده گزارش

`GET /api/v1/research/risk` سه فیلتر اختیاری می‌پذیرد:

| پارامتر | قرارداد |
| --- | --- |
| `from_time` | زمان timezone-aware؛ تصمیم‌هایی با `risk_assessment.evaluated_at >= from_time` |
| `to_time` | زمان timezone-aware؛ تصمیم‌هایی با `risk_assessment.evaluated_at <= to_time` |
| `portfolio_id` | شناسه یک پرتفوی شبیه‌سازی‌شده موجود؛ شناسه ناشناخته با 404 رد می‌شود |

هر دو سر بازه بسته‌اند. `to_time < from_time` و زمان بدون timezone با 422 رد می‌شوند. اگر
فیلتر Portfolio ارسال نشود، projection همه پرتفوی‌های شبیه‌سازی‌شده ثبت‌شده را پوشش می‌دهد.

## تصمیم‌ها و علل رد

- مخرج `approval_rate` فقط attemptهایی است که واقعاً `CandidateRiskAssessment` دارند؛ Candidate
  ردشده از ارزیابی یا skipped وارد مخرج نمی‌شود.
- `evaluated = approved + rejected` و برای داده خالی `approval_rate = null` است؛ صفر درصد فقط
  زمانی نمایش داده می‌شود که حداقل یک تصمیم ارزیابی‌شده وجود داشته باشد و هیچ‌کدام پذیرفته نشده
  باشند.
- پاسخ همیشه هر هشت عضو `CandidateRiskCheckName` را با ترتیب ثابت برمی‌گرداند.
- یک تصمیم می‌تواند چند check ناموفق داشته باشد، اما برای reconciliation دقیقاً یک علت اصلی دارد:
  اولین check ناموفق در ترتیب ثابت سیاست. همه checkهای ناموفق نیز روی همان `decision_event` حفظ
  می‌شوند. بنابراین جمع `rejection_reasons.rejected_decisions` دقیقاً با `rejected_count` برابر است.
- شناسه journal، Candidate، Portfolio و زمان هر تصمیم در `decision_events` باقی می‌ماند تا UI از
  دسته علت به رویداد و سپس به lineage کاندید و گزارش پرتفوی لینک دهد.

## Budget، exposure، concentration و drawdown

| سنجه | تعریف نسخه `risk-dashboard-v1` |
| --- | --- |
| بودجه تخصیص‌یافته | جمع `risk_budget` فقط برای تصمیم‌هایی که واقعاً موقعیت شبیه‌سازی‌شده باز کرده‌اند |
| ریسک مصرف‌شده | جمع `simulation.quantity × assessment.unit_price_risk` همان موقعیت‌ها |
| نسبت مصرف | ریسک مصرف‌شده تقسیم بر بودجه تخصیص‌یافته؛ بدون موقعیت بازشده `null` |
| exposure | جمع `price × quantity` موقعیت‌های باز در آخرین رویداد هر Portfolio تا `to_time` |
| concentration | exposure بزرگ‌ترین جفت معاملاتی تقسیم بر مجموع equity همان snapshotها |
| drawdown | بدترین افت peak-to-trough هر Portfolio؛ equity آخرین رویداد پیش از `from_time` baseline است و سپس رویدادهای داخل بازه بررسی می‌شوند |

Exposure و concentration با `CandidateRiskPolicy.max_notional_fraction` و drawdown با
`CandidateRiskPolicy.max_risk_fraction` مقایسه می‌شوند. پاسخ مقدار سنجه، سقف و وضعیت
`within_limit` را جداگانه برمی‌گرداند. اگر equity مثبت یا رویداد قابل استفاده موجود نباشد، نسبت
مربوط `null` است و UI آن را به‌عنوان داده ناموجود نشان می‌دهد، نه صفر گمراه‌کننده.

## مرز ایمنی و قابلیت ممیزی

- endpoint فقط GET است؛ POST روی همین مسیر مجاز نیست.
- محاسبات فقط از payloadهای immutable journal و timeline ذخیره‌شده انجام می‌شوند.
- UI هیچ کنترل Buy/Sell/Open/Close، credential یا مسیر سفارش واقعی ندارد و برچسب پژوهشی
  فقط‌خواندنی را نمایش می‌دهد.
- `dashboard_version`، قواعد بازه و قاعده snapshot در خود پاسخ API ثبت می‌شوند تا مصرف‌کننده برای
  تفسیر گزارش به حدس متکی نباشد.
