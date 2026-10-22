# P3-08 — Market Context Product API and UI

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P3-09**

تاریخ تصمیم: `2026-10-17`

مبنای کد: P3-07 در commit محلی `78a6952`

این مرحله assessmentهای immutable ساخته‌شده در P3-05/P3-06 را به یک API محصولی فقط‌خواندنی و
صفحهٔ دو‌زبانه «زمینه بازار» متصل می‌کند. مرز اصلی طراحی fail-closed است: assessment قدیمی یا منقضی
برای توضیح و audit قابل مشاهده می‌ماند، اما هرگز به‌عنوان context قابل‌مصرف معرفی نمی‌شود.

## 1. قرارداد مصرف

`MarketContextProductView` با schema نسخهٔ `market-context-product-view-v1` یک assessment کامل را
همراه تصمیم مصرف فعلی منتشر می‌کند:

- `evaluated_at`: زمان ارزیابی availability؛
- `expected_as_of`: floor ساعتی UTC در همان زمان؛
- `consumable`: تصمیم قطعی و fail-closed؛
- `unavailable_reasons`: علت‌های مرتب و نسخه‌پذیر؛
- `boundary_lag_seconds`: فاصلهٔ assessment تا مرز فعلی؛
- `seconds_until_expiry`: زمان اعتبار باقی‌مانده، بدون مقدار منفی؛
- `assessment`: regime، confidence، evidence و lineage immutable.

`consumable=true` فقط وقتی صادر می‌شود که:

1. وضعیت assessment برابر `ready` باشد؛
2. `assessment.as_of` دقیقاً با `expected_as_of` برابر باشد؛
3. `expires_at` بعد از `evaluated_at` باشد.

دلایل عدم مصرف عبارت‌اند از `assessment_not_ready`، `assessment_expired` و `boundary_mismatch`.
validator خود مدل این تصمیم، lag و expiry را دوباره محاسبه می‌کند؛ بنابراین پاسخ ناسازگار قابل ساختن
نیست.

## 2. query فقط‌خواندنی

`SqlAlchemyMarketContextProductReader` آخرین assessment هر کلید
`source + base_asset + quote_asset + market_type` را با window function انتخاب می‌کند. query:

- pagination محدود `1..100` دارد؛
- با source، pair و market type قابل فیلتر است؛
- نتیجه را بر اساس جدیدترین boundary مرتب می‌کند؛
- هیچ assessment را recompute یا mutate نمی‌کند؛
- detail را فقط از ID immutable assessment می‌خواند.

فیلتر pair باید base و quote را با هم داشته باشد. assetها uppercase و source trim می‌شوند.

## 3. API محصولی

دو endpoint فقط‌خواندنی اضافه شده‌اند:

| Method | Path | کاربرد |
| --- | --- | --- |
| `GET` | `/api/v1/market-context` | آخرین context هر stream با pagination و فیلتر |
| `GET` | `/api/v1/market-context/{assessment_id}` | یک assessment immutable با availability فعلی |

catalog از قرارداد عمومی `Page` استفاده می‌کند. assessment ناشناخته `404` و pair filter ناقص `422`
می‌دهد. هیچ endpoint برای اجرای job، retry یا عملیات معاملاتی در این مرز اضافه نشده است.

## 4. تجربهٔ کاربری

مسیرهای `/fa/market-context` و `/en/market-context` به گروه «استراتژی و تصمیم‌گیری» اضافه شده‌اند.
در viewport اول هر کارت فقط اطلاعات تصمیمی اصلی را نشان می‌دهد:

- source و pair؛
- وضعیت قابل‌مصرف یا غیرقابل‌مصرف؛
- trend و volatility؛
- confidence و progress قابل‌دسترسی؛
- boundary، زمان assessment و expiry؛
- دلیل روشن برای هر context غیرقابل‌مصرف.

feature valueها، نسخهٔ محاسبه، تعداد windowهای مرجع، شناسه‌ها و checksumها داخل
`AdvancedDisclosure` قرار دارند. layout در موبایل تک‌ستونه است، شناسه‌های بلند wrap می‌شوند و در
نمای بزرگ کارت‌ها دو ستونه‌اند. صفحه pagination، loading overlay، retry امن و empty state دارد.

## 5. معنی محصولی regime

UI ترجمهٔ قطعی labelها را بدون تفسیر معاملاتی نمایش می‌دهد:

- trend: `trending_up`، `trending_down`، `ranging` یا `undetermined`؛
- volatility: `low`، `normal`، `high` یا `undetermined`؛
- confidence: confidence خود الگوریتم regime، نه احتمال سود یا توصیهٔ معامله.

هشدار صفحه صریحاً اعلام می‌کند که market context سیگنال خرید/فروش نیست. این مرحله هنوز context را
وارد ranking، risk یا portfolio execution نمی‌کند.

## 6. امنیت و سازگاری

- پاسخ‌ها فقط public market data مشتق‌شده و lineage بازتولید را دارند.
- credential، account، wallet، deposit، withdrawal و live order وجود ندارد.
- API هیچ payload یا worker identity از صف durable را منتشر نمی‌کند.
- navigation و inventory عمومی routeها به 22 صفحه در هر locale ارتقا یافته است.
- endpointهای جدید در قرارداد OpenAPI مصرف‌شده توسط frontend ثبت شده‌اند.

## 7. معیار خروج P3-08

- [x] تصمیم consumable به‌صورت fail-closed و قابل validation است.
- [x] catalog آخرین assessment هر stream را با pagination برمی‌گرداند.
- [x] source/pair/market filters نرمال و محدود هستند.
- [x] detail immutable و 404 مشخص دارد.
- [x] evidence و lineage برای explainability قابل مشاهده‌اند.
- [x] صفحه فارسی و انگلیسی، responsive و keyboard-accessible است.
- [x] خلاصه تصمیم در viewport اول و جزئیات خام در Advanced قرار دارند.
- [x] هیچ اکشن trade/order/evaluate/retry به API محصولی اضافه نشده است.
- [x] تست‌های domain، reader، API، client، render، route و navigation افزوده شده‌اند.
- [x] محدودهٔ `crypto-spot-public-read-only` حفظ شده است.

گام بعدی `P3-09 — Golden Market Context Benchmark and Acceptance Evidence` است.
