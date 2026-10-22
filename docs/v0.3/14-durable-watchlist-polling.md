# P2-03 — Worker ماندگار Polling برای Watchlist

وضعیت: **پیاده‌سازی‌شده؛ evidence نهایی PostgreSQL و CI در انتظار اجرای مالک مخزن**

تاریخ تصمیم: `2026-10-14`

مبنای کد: P2-02 در commit
`1697ba04c9c35bfe8e6298f3f566aa132567a35d`

این مرحله Watchlist نزدیک به real-time را به Background Job ماندگار و ingestion اتمیک P2-02
متصل می‌کند. ترتیب provider فریز‌شده `Kraken → Binance` است و هر fallback در Poll Run ثبت
می‌شود؛ fallback پنهان مجاز نیست.

## 1. مرز قابلیت

- یک Watchlist entry دقیقاً یک Crypto Spot pair و timeframe را زمان‌بندی می‌کند؛
- هر entry دو connection عمومی، سالم و فعال با ترتیب `kraken-public` سپس `binance-public` دارد؛
- cadence از `market-data-service-level-policy-v1` خوانده و همراه entry ذخیره می‌شود؛
- scheduler فقط slotهای due را به job نوع `market_data_poll` تبدیل می‌کند؛
- worker همان lease، retry، heartbeat، reclaim و cancellation زیرساخت Background Job را استفاده
  می‌کند؛
- دادهٔ معتبر از مرز اتمیک Raw/Event/Inbox/Decision/Window/Outbox عبور می‌کند.

این مرحله finalization پنجره، replay داده دیررس، API/UI وضعیت polling و retention purge را انجام
نمی‌دهد؛ این موارد به‌ترتیب در P2-04 تا P2-07 بسته می‌شوند.

## 2. Persistence جدید

| جدول | نقش | invariant اصلی |
| --- | --- | --- |
| `market_data_watchlist` | stream، route order و slot بعدی polling | stream یکتا، cadence مثبت و `Kraken → Binance` در payload نسخه‌دار |
| `market_data_provider_budgets` | token bucket مشترک workerها | سقف sustained و burst از policy فریز‌شده |
| `market_data_poll_runs` | evidence نهایی هر job attempt | تلاش‌های مرتب provider، انتخاب نهایی، count تصمیم‌ها و failure امن |

`market_data_poll_runs` پیام خام exception یا credential نگه نمی‌دارد. فقط error code پایدار و پیام
عملیاتی sanitize‌شده ثبت می‌شود.

## 3. Cadence و enqueue اتمیک

`SqlAlchemyMarketDataPollingScheduler` rowهای فعال و due را با `FOR UPDATE SKIP LOCKED` می‌گیرد.
ساخت job و جلو بردن `next_poll_at` در یک transaction انجام می‌شود. idempotency key شامل Watchlist
ID و slot زمان‌بندی است؛ در نتیجه اجرای هم‌زمان scheduler یک slot را دو بار منتشر نمی‌کند.

اگر scheduler مدتی خاموش باشد، slot بعدی به اولین cadence آینده منتقل می‌شود و صفی از jobهای
قدیمی ساخته نمی‌شود. lookback محدود worker فاصلهٔ ایجادشده را پوشش می‌دهد.

## 4. Request budget

پیش از هر تماس provider، token bucket ماندگار بررسی می‌شود:

- sustained: حداکثر ۱۰ درخواست در دقیقه؛
- burst: حداکثر ۳ درخواست؛
- retry-after محلی از نرخ refill محاسبه می‌شود؛
- تمام workerها state مشترک PostgreSQL را می‌بینند؛
- سقف concurrency عملیاتی با baseline یک worker حفظ می‌شود؛ افزایش worker concurrency نیازمند
  بازبینی capacity و lease جداگانه است.

تمام providerها همچنان timeout، retry و `Retry-After` محدود adapter خود را رعایت می‌کنند. تمام‌شدن
budget یک provider به‌عنوان attempt مستقل ثبت می‌شود و فقط اجازهٔ امتحان route بعدی را تحت budget
مستقل همان route می‌دهد؛ اگر هیچ route قابل استفاده نباشد job با نتیجهٔ retryable به صف برمی‌گردد.

## 5. ترتیب provider و failure semantics

1. connection مربوط به Kraken دوباره از نظر enabled/healthy بودن بررسی می‌شود؛
2. budget گرفته و بازهٔ UTC هم‌تراز با candle درخواست می‌شود؛
3. پاسخ از نظر source/pair/timeframe، future skew و quality سخت‌گیرانه بررسی می‌شود؛
4. فقط در `provider failure`، `no data`، connection unavailable، budget محلی تمام‌شده یا quality
   rejection تلاش Binance با evidence مستقل انجام می‌شود؛
5. موفقیت Kraken هرگونه تماس Binance را ممنوع می‌کند؛
6. شکست هر دو route یک Poll Run شکست‌خورده و خطای امن برای retry policy job می‌سازد.

Poll Run شامل outcome هر route است؛ بنابراین operator می‌تواند بفهمد نتیجه از provider اصلی یا
fallback آمده است.

## 6. Watermark و ingestion

- بازهٔ درخواست به آخرین boundary بسته‌شدهٔ timeframe هم‌تراز می‌شود؛
- خروجی adapter به شکل `canonical-provider-observation-v1` و بدون حذف فیلد OHLCV ثبت می‌شود؛
- برای اولین observation هر provider/stream، Watermark revision اولیه با allowed lateness policy
  ساخته می‌شود؛
- همهٔ candleهای batch به ترتیب زمانی وارد ingestion اتمیک P2-02 می‌شوند؛
- پس از batch موفق، Watermark فقط رو به جلو و در revision تازه advance می‌شود؛
- crash و retry به‌کمک idempotency ingestion و job lease نتیجهٔ تکراری Window/Outbox نمی‌سازد.

Watermark هر provider مستقل است تا fallback دادهٔ Binance را به دروغ به provenance Kraken متصل
نکند.

## 7. اجرای runtime

Scheduler و worker باید در دو process مجزا و با همان PostgreSQL اجرا شوند:

```bash
PYTHONPATH=src python scripts/run_market_data_polling_scheduler.py
PYTHONPATH=src python scripts/run_background_worker.py
```

برای smoke تک‌مرحله‌ای:

```bash
PYTHONPATH=src python scripts/run_market_data_polling_scheduler.py --once
PYTHONPATH=src python scripts/run_background_worker.py --once
```

تا پیش از API/UI مرحله P2-06، ساخت و pause/resume کردن entry از service داخلی
`SqlAlchemyMarketDataWatchlistManager` انجام می‌شود.

## 8. Migration و سازگاری

- migration جدید `20261014_0021` بعد از `20261014_0020` قرار دارد؛
- kind جدید `market_data_poll` به allowlist و policy مرکزی Background Job اضافه شده است؛
- Historical Import نوع `market_data_import` بدون تغییر باقی مانده است؛
- PostgreSQL modular monolith حفظ شده و broker یا datastore جدید اضافه نشده است؛
- هیچ route، payload یا field مربوط به order، credential، wallet، deposit یا withdrawal اضافه نشده.

## 9. گیت خروج P2-03

- [x] Watchlist stream و provider order ماندگار و نسخه‌دار است.
- [x] scheduler cadence را بدون enqueue تکراری جلو می‌برد.
- [x] Poll job از lease/retry زیرساخت worker استفاده می‌کند.
- [x] token bucket سقف sustained و burst را اعمال می‌کند.
- [x] موفقیت Kraken مانع تماس fallback و شکست آن اجازهٔ Binance را می‌دهد.
- [x] provider attemptها و انتخاب fallback در Poll Run قابل audit هستند.
- [x] پاسخ نامعتبر، future skew و stream mismatch پیش از ingestion رد می‌شوند.
- [x] batch معتبر به ingestion اتمیک P2-02 و Watermark versioned متصل است.
- [ ] full backend و PostgreSQL CI روی SHA نهایی سبز شود.

گام بعدی `P2-04 — Window Lifecycle and Watermark Finalization` است؛ در آن windowهای provisional
پس از عبور Watermark به نسخهٔ finalized تبدیل و freshness outcome آنها ثبت می‌شود.
