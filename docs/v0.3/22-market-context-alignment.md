# P3-03 — Multi-timeframe Alignment و Dataset Assembly

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P3-04**

تاریخ تصمیم: `2026-10-16`

مبنای کد: P3-02 در commit ریموت
`c4647360872cf4c6ac0514de36fa0dffb7b28f7a`

این مرحله finalized windowهای P2 را در یک مرز event-time مشترک هم‌تراز می‌کند و فقط در صورت کامل
بودن تمام history مورد نیاز، manifest ورودی P3 را می‌سازد. هنوز هیچ feature یا regime محاسبه
نمی‌شود؛ این دو مسئولیت به‌ترتیب متعلق به P3-04 و P3-05 هستند.

## 1. قرارداد alignment

تابع pure `align_market_context_windows` ورودی‌های زیر را می‌گیرد:

- source و pair دقیق؛
- `as_of` روی مرز کامل `1h` در UTC؛
- finalized window snapshotها؛
- feature-set نسخه‌دار و lookbackهای آن؛
- زمان اجرای alignment.

خروجی `MarketContextAlignmentResult` برای هر سه timeframe پوشش مستقل و یک status کلی دارد. ترتیب
همیشه `1h`، سپس `4h` و سپس `1d` است تا serialize، checksum و replay قطعی باقی بماند.

## 2. مرزهای event-time

برای هر timeframe، آخرین window قابل‌مصرف در `floor(as_of, timeframe)` پایان می‌یابد. بازه‌ها
left-closed/right-open هستند و window بعد از `as_of` حتی اگر در دیتابیس موجود باشد مصرف نمی‌شود.

مثلاً برای `as_of = 2026-10-16T12:00:00Z`:

| Timeframe | آخرین window مورد انتظار |
| --- | --- |
| `1h` | `[11:00, 12:00)` |
| `4h` | `[08:00, 12:00)` |
| `1d` | `[2026-10-15T00:00, 2026-10-16T00:00)` |

هیچ forward-fill، backfill یا استفاده از candle باز انجام نمی‌شود. sourceها نیز با هم ترکیب
نمی‌شوند.

## 3. محاسبهٔ history مورد نیاز

`required_market_context_window_counts` برای هر timeframe بیشترین `lookback_windows` بین featureهای
همان timeframe را انتخاب می‌کند. حتی اگر feature-set فعلاً برای یک timeframe requirement نداشته
باشد، یک window برای قرارداد پایهٔ `1h + 4h + 1d` الزامی است.

این تصمیم باعث می‌شود P3-04 بتواند هر feature را فقط از suffix دقیق manifest محاسبه کند و برای
جمع‌آوری داده query جداگانه یا مبهم نداشته باشد.

## 4. وضعیت‌های صریح

| Status | معنی | Manifest |
| --- | --- | --- |
| `ready` | تمام windowهای لازم پیوسته و تا مرز مورد انتظار موجودند | ساخته و قابل ثبت است |
| `stale` | history کافی و پیوسته است ولی آخرین window از مرز مورد انتظار عقب است | ساخته نمی‌شود |
| `insufficient_data` | داده وجود ندارد، history کوتاه است یا داخل بازه gap وجود دارد | ساخته نمی‌شود |

کدهای علت پایدار عبارت‌اند از:

- `no_finalized_windows`
- `insufficient_history`
- `window_gap`
- `stale_latest_window`

اگر چند timeframe مشکل داشته باشند، `insufficient_data` بر `stale` اولویت دارد. هیچ نتیجهٔ ناقص یا
partially-ready به مصرف‌کننده داده نمی‌شود.

## 5. انتخاب نسخه و reproducibility

برای هر `window_id` فقط بالاترین نسخهٔ finalized انتخاب می‌شود. نسخهٔ provisional جدیدتر روی این
انتخاب اثر ندارد. reference نهایی شامل ID، version، event ID، payload checksum، bounds و زمان
finalization است.

زمان creation manifest از خود ورودی‌ها به‌شکل deterministic تعیین می‌شود: بیشینهٔ `as_of` و آخرین
finalization time. بنابراین retry در زمانی دیگر همان manifest را تولید می‌کند و با uniqueness
مرحلهٔ P3-02 conflict ساختگی ندارد.

## 6. DB assembler

`SqlAlchemyMarketContextAssembler` برای هر timeframe فقط به‌اندازهٔ lookback لازم row می‌خواند و با
`NOT EXISTS` بالاترین finalized version هر window را جدا می‌کند. query بر source، pair، market type،
timeframe و cutoff دقیق محدود است.

اگر نتیجه ready باشد، assembler همان manifest را با `SqlAlchemyMarketContextStore` stage می‌کند.
این کلاس عمداً commit نمی‌کند؛ transaction، retry و failure policy در P3-06 به worker واگذار
می‌شوند. نتیجهٔ stale یا insufficient هیچ رکورد manifest ایجاد نمی‌کند.

## 7. تضمین‌های تست‌شده

- بزرگ‌ترین lookback هر timeframe انتخاب می‌شود؛
- ورودی نامرتب به manifest مرتب و deterministic تبدیل می‌شود؛
- آخرین finalized revision انتخاب و provisional نادیده گرفته می‌شود؛
- دادهٔ stale، history کوتاه و gap از هم تفکیک می‌شوند؛
- ورودی provisional یا mixed-source به‌صورت fail-closed رد می‌شود؛
- retry با زمان اجرای متفاوت همان manifest را stage می‌کند؛
- assembler خارج از transaction caller commit انجام نمی‌دهد؛
- alignment غیرآماده هیچ manifest ناقصی ذخیره نمی‌کند.

## 8. مرز امنیتی

این مرحله فقط public market-data windowها و lineage محاسباتی را می‌خواند. هیچ credential، exchange
account، wallet، deposit، withdrawal یا live-order surface اضافه نشده است.

## 9. معیار خروج P3-03

- [x] alignment دقیق `1h + 4h + 1d` بر اساس event-time پیاده شده است.
- [x] lookback از feature-set نسخه‌دار مشتق می‌شود.
- [x] فقط آخرین finalized version هر window مصرف می‌شود.
- [x] gap، stale و insufficient با علت machine-readable گزارش می‌شوند.
- [x] فقط نتیجهٔ ready یک manifest کامل می‌سازد.
- [x] manifest در retry deterministic و persistence آن idempotent است.
- [x] query دیتابیس bounded و transaction ownership بیرون assembler است.
- [x] تست‌های pure و persistence مسیرهای اصلی و failure را پوشش می‌دهند.
- [x] محدودهٔ public read-only حفظ شده است.

گام بعدی `P3-04 — Deterministic Feature Set v1` است.
