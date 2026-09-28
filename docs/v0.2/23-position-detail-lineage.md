# TB2-021 — Position Detail و lineage کامل

## هدف و مرز

این مرحله برای هر Position شبیه‌سازی‌شده یک صفحهٔ مستقل و projection نسخه‌دار فقط‌خواندنی می‌سازد. این مسیر هیچ order، mutation، backfill یا اجرای معامله‌ای ندارد و فقط دادهٔ تاریخی persistشده را به هم متصل می‌کند.

## قرارداد API

`GET /api/v1/research/portfolios/{portfolio_id}/positions/{position_id}/detail`

- پاسخ `position-detail-v1` شامل snapshot کامل Position، `as_of` پرتفوی، Dataset، وضعیت lineage، Candidate و decision evidence قابل اثبات، هفت node مرتب و eventهای همان Position است.
- Position باید متعلق به Portfolio مسیر باشد؛ Portfolio یا Position ناشناخته `404` است.
- روش‌های نوشتن روی endpoint وجود ندارند و `POST` برابر `405` است.
- `interpretation=historical_research_only` مرز محصول را صریح می‌کند.

## قواعد تطبیق و fail-closed

1. journal فقط وقتی منطبق است که هر دو `portfolio_id` و `position_id` برابر باشند.
2. تکرار دقیق همان `journal_id` یک بار محاسبه می‌شود.
3. چند journal متفاوت یا payload ناسازگار برای یک شناسه، وضعیت `conflict` می‌دهد.
4. نبود journal وضعیت `unavailable` می‌دهد؛ Dataset و خود Position قابل نمایش می‌مانند، اما Experiment، Signal، Candidate، Risk و علت Exit حدس زده نمی‌شوند.
5. eventها مستقیماً از timeline پرتفوی، فقط با `position_id` یکسان و با ترتیب `sequence_number` ارائه می‌شوند.

## UI و پیمایش

- کارت Position در Portfolio Detail به route مستقل Position لینک دارد.
- node موقعیت و خروج در Candidate lineage به همین route لینک می‌شوند.
- صفحهٔ Position حسابداری ورود/خروج، کارمزد، P&L، شواهد رتبه و checkهای ریسک، علت خروج و eventهای persisted را به فارسی و انگلیسی نمایش می‌دهد.
- هیچ دکمهٔ buy/sell/open/close یا عملیات live در صفحه وجود ندارد.

## پذیرش

- سناریوی بسته باید Dataset → Experiment → Signal → Candidate → Risk → Position → Exit را کامل نمایش دهد.
- `realized_pnl = gross_realized_pnl - entry_fee - exit_fee` و event خروج باید با Position یکسان باشند.
- حذف journal نباید شناسه یا outcome ساختگی تولید کند.
- journalهای متعارض باید `conflict` شوند و هیچ Candidate یا decision evidence انتخاب نشود.
- دسترسی Position از Portfolio و Candidate هر دو باید به URL canonical یکسان برسد.

این مرحله migration ندارد؛ projection از payloadهای موجود Portfolio و Candidate Journal ساخته می‌شود.
