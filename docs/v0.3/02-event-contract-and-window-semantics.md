# P0-03 — قرارداد Event و Window Semantics

وضعیت: **فریز شده برای P0-04 و پیاده‌سازی P2**

تاریخ تصمیم: `2026-10-09`

مبنای کد: `feature/v0.3-market-intelligence`

این مرحله قرارداد دامنهٔ جریان دادهٔ v0.3 را بدون افزودن migration، broker، polling loop یا endpoint
جدید تثبیت می‌کند. مدل‌های این مرحله pure و immutable هستند تا پیش از انتخاب persistence یا runtime
قابل تست باشند.

## 1. تصمیم معماری

نسخهٔ اول Live Data Foundation در همان modular monolith و PostgreSQL فعلی ساخته می‌شود. جداسازی
ماژول با Event، idempotency و outbox/inbox boundary انجام می‌شود؛ نه با افزودن زودهنگام Kafka، Redis
یا microservice.

قرارداد کد در `src/trd_bot/market_data/events.py` قرار دارد و شامل این مدل‌هاست:

- `MarketDataEvent`؛
- `MarketDataWatermark`؛
- `MarketDataWindowSnapshot`؛
- `MarketDataEventDecision`؛
- policy خالص `decide_market_data_event`.

این مدل‌ها قرارداد آیندهٔ persistence را تعریف می‌کنند، اما خودشان هیچ state خارجی را تغییر
نمی‌دهند.

## 2. Event Envelope نسخهٔ اول

`market-data-event-v1` یک observation نرمال‌شدهٔ OHLCV را حمل می‌کند.

| فیلد | معنا |
| --- | --- |
| `schema_version` | نسخهٔ envelope؛ مقدار ثابت `market-data-event-v1` |
| `event_id` | شناسهٔ deterministic برای محتوای همان window |
| `kind` | در v1 فقط `candle_observed` |
| `source` | provider عمومی و allowlisted |
| `pair` | هویت canonical بازار |
| `timeframe` | `15m`، `1h`، `4h` یا `1d` |
| `event_time` | زمان رخداد دامنه؛ برای candle برابر `close_time` |
| `observed_at` | processing/receipt time؛ برابر `candle.received_at` |
| `payload_version` | در v1 برابر `ohlcv-candle-v1` |
| `payload_checksum` | SHA-256 محتوای candle بدون receipt time |
| `idempotency_key` | window identity + payload checksum |
| `candle` | payload نرمال‌شدهٔ immutable |

Envelope اطلاعات routing را در کنار payload نگه می‌دارد، اما validator اجازهٔ اختلاف source، pair،
timeframe یا timestamp میان این دو را نمی‌دهد.

## 3. دو هویت متفاوت

برای جلوگیری از مخلوط شدن duplicate و correction دو هویت جدا وجود دارد:

### Window identity

از `source + pair + timeframe + open_time + close_time` ساخته می‌شود. همهٔ نسخه‌های موقت، نهایی
یا اصلاح‌شدهٔ یک بازه `window_id` یکسان دارند.

### Event idempotency identity

از `window_id + payload_checksum` ساخته می‌شود. در نتیجه:

- تحویل دوبارهٔ محتوای یکسان با `observed_at` متفاوت duplicate است؛
- اصلاح قیمت یا حجم همان بازه Event تازه می‌سازد؛
- اصلاح payload، Window تازه جعل نمی‌کند و روی همان lineage باقی می‌ماند.

Receipt time عمداً وارد payload checksum نمی‌شود؛ در غیر این صورت retry شبکه به اشتباه Event تازه
محسوب می‌شد.

## 4. Event Time و Processing Time

- همهٔ timestampها باید timezone-aware باشند و در مدل به UTC normalize می‌شوند.
- `event_time` برای candle برابر `close_time` است.
- `observed_at` زمان دریافت/پردازش است و نباید به‌جای event time برای windowing استفاده شود.
- اختلاف event time و processing time به‌عنوان lag قابل اندازه‌گیری است، نه خطایی که پنهان شود.
- provisional candle ممکن است پیش از `close_time` مشاهده شود؛ بنابراین قرارداد عمومی الزام
  `observed_at >= event_time` ندارد.
- سیاست clock-skew و future timestamp در P0-04 عددگذاری می‌شود.

## 5. Watermark

`market-data-watermark-v1` فقط برای یک stream دقیق با هویت
`source + pair + timeframe` معتبر است.

```text
watermark_time = high_water_event_time - allowed_lateness
```

قواعد:

1. `high_water_event_time` بیشترین event time مشاهده‌شده است.
2. Event قدیمی‌تر مجاز نیست watermark را عقب ببرد.
3. زمان محاسبهٔ watermark نیز نباید عقب برود.
4. Event متعلق به stream دیگر با خطای صریح رد می‌شود.
5. `event_time <= watermark_time` دیررس است؛ تساوی نیز late محسوب می‌شود.
6. مقدار `allowed_lateness` در این مرحله hard-code نمی‌شود و P0-04 آن را برای هر timeframe تعیین
   می‌کند.

Watermark یک حقیقت provider نیست؛ projection پردازشی سیستم است و باید همراه stream و policy
نسخه‌دار persist شود.

## 6. Window lifecycle

`market-data-window-v1` دو state دارد:

- `provisional`؛
- `finalized`.

هر تغییر محتوایی یا تغییر state یک **نسخهٔ immutable تازه** می‌سازد. Snapshot قبلی overwrite
نمی‌شود.

شرایط finalization:

- candle باید بسته باشد؛
- `window_end <= watermark_time` باشد؛
- watermark و window متعلق به یک stream باشند؛
- finalization time معتبر و پس از creation time باشد.

Finalization نسخه را یک واحد افزایش می‌دهد. فراخوانی دوباره روی window نهایی خطاست؛ عملیات
idempotent باید پیش از finalization از snapshot جاری و decision journal استفاده کند.

## 7. ماتریس تصمیم

| وضعیت Event | Window موجود | نتیجه | رفتار |
| --- | --- | --- | --- |
| on-time و payload تازه | ندارد | `accepted/new_window` | ساخت provisional version 1 |
| هر زمان و payload یکسان | provisional یا finalized | `duplicate` | بدون نسخهٔ تازه |
| on-time و payload اصلاح‌شده | provisional | `accepted/provisional_update` | پیشنهاد نسخهٔ بعد |
| payload اصلاح‌شده | finalized | `revision_required/finalized_window_conflict` | عدم mutation و Replay صریح |
| Event غیرتکراری late | هر حالت | `revision_required/late_arrival` | عدم mutation عادی و Replay صریح |

اولویت duplicate بالاتر از late است؛ redelivery دیرهنگام محتوای یکسان نباید Replay بی‌دلیل بسازد.
در مقابل، Event دیررس تازه—even اگر window فعلی وجود نداشته باشد—نمی‌تواند بی‌صدا نتایج قبلی را
تغییر دهد.

## 8. Failure و status semantics

| وضعیت | معنای پایدار | mutation عادی |
| --- | --- | --- |
| `accepted` | Event on-time و قابل اعمال روی window غیرنهایی | مجاز با نسخهٔ تازه |
| `duplicate` | همان window و همان payload قبلاً دیده شده | ممنوع |
| `revision_required` | داده دیررس یا تعارض با snapshot نهایی | ممنوع تا Replay/Revision workflow |
| validation error | schema، checksum، identity یا stream ناسازگار | ممنوع |

هیچ fallback پنهانی وجود ندارد. provider fallback، correction، late event و replay باید status و
evidence مستقل داشته باشند. Exception خام provider یا payload حساس نباید وارد response عمومی شود.

## 9. Outbox/Inbox boundary

P2 باید این قرارداد را با persistence اتمیک پیاده کند:

1. Inbox یا جدول Event append-only، idempotency key را unique می‌کند.
2. ثبت raw/normalized observation و تصمیم ingestion در یک transaction قابل audit انجام می‌شود.
3. Event accepted برای مرحلهٔ بعد از outbox منتشر می‌شود.
4. consumer با event ID و payload version idempotent است.
5. failure مرحلهٔ بعد status خودش را تغییر می‌دهد و Event قبلی را overwrite نمی‌کند.
6. redelivery پس از crash باید همان نتیجهٔ duplicate یا ادامهٔ امن را بسازد.

انتخاب نام جدول، partitioning، retention، batch size و broker در P0-03 انجام نمی‌شود. این تصمیم‌ها
به P0-04 و implementation P2 وابسته‌اند.

## 10. Compatibility و migration

- مدل `OHLCVCandle` فعلی payload canonical v1 باقی می‌ماند.
- Historical Import و Datasetهای موجود بدون backfill ساختگی خواندنی می‌مانند.
- افزودن Event store در P2 فقط با migration از DB خالی و بدون بازنویسی Snapshotهای v0.2 مجاز است.
- Dataset نهایی از provisional candle ساخته نمی‌شود.
- schema version جدید باید consumer قدیمی را fail-closed کند؛ حدس زدن payload ممنوع است.
- هیچ endpoint سفارش، account connection یا credential معاملاتی به این قرارداد مرتبط نیست.

## 11. تست‌های قرارداد

`tests/test_market_data_events.py` این سناریوها را پوشش می‌دهد:

- redelivery با receipt time متفاوت همان event identity را حفظ می‌کند؛
- correction همان window و event identity متفاوت دارد؛
- envelope ناسازگار fail می‌شود؛
- watermark boundary، monotonicity و stream isolation؛
- پذیرش window on-time؛
- duplicate بدون ساخت نسخه؛
- correction روی provisional با نسخهٔ بعد؛
- finalization به نسخهٔ immutable تازه؛
- ممنوعیت finalization candle باز یا window نارس؛
- late arrival و correction پس از finalization نیازمند Replay صریح.

## 12. تصمیم‌های باز برای P0-04

- allowed lateness هر timeframe و provider؛
- حداکثر clock skew؛
- freshness SLO برای provisional و finalized data؛
- مدت retention برای raw event، inbox، outbox و revision evidence؛
- batch size، polling cadence و rate-limit budget؛
- حد backlog و queue wait مجاز؛
- زمان‌بندی Replay و سقف correction rate؛
- معیار انتخاب provider اصلی و fallback.

## 13. معیار خروج P0-03

- [x] Event envelope و payload version فریز شدند.
- [x] event time و processing time تفکیک شدند.
- [x] idempotency و correction identity مستقل شدند.
- [x] watermark monotonic و late boundary تعریف شد.
- [x] provisional/finalized lifecycle و immutability تعریف شد.
- [x] late/correction بدون mutation پنهان به Replay متصل شد.
- [x] outbox/inbox boundary بدون فناوری زودهنگام مشخص شد.
- [x] قراردادها با تست‌های domain پوشش داده شدند.

گام بعدی `P0-04 — SLO، Retention، Provider Budget and Capacity Benchmark` است. عددهای SLO فقط
پس از اجرای benchmark روی محیط مرجع فریز می‌شوند.
