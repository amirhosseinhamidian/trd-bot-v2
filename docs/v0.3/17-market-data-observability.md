# P2-06 — Market Data Freshness/Health API and UI

وضعیت: **پیاده‌سازی‌شده؛ full CI روی SHA نهایی در انتظار اجرای مالک مخزن**

تاریخ تصمیم: `2026-10-14`

مبنای کد: P2-05 در commit
`6bb2d17`

این مرحله وضعیت ماندگار Watchlist، provider، Window، Watermark، صف و Replay را به یک projection
فقط‌خواندنی و sanitizeشده تبدیل می‌کند. endpoint و رابط کاربری هیچ عملیات polling، replay یا
معامله‌ای را آغاز نمی‌کنند.

## 1. قرارداد Freshness و Lag

برای هر جریان Watchlist، آخرین Window نهایی بین routeهای همان جریان انتخاب می‌شود:

- `data_age_seconds = now - latest_finalized_window_end`؛
- `lag_seconds = max(0, data_age_seconds - timeframe_duration)`؛
- جریان تا زمانی `fresh` است که lag از `finalized_freshness_p95_seconds` policy همان timeframe
  عبور نکرده باشد؛
- نبود Window نهایی با وضعیت صریح `no_data` نمایش داده می‌شود و با مقدار صفر اشتباه گرفته نمی‌شود.

کسر مدت timeframe باعث می‌شود کندل جاری که هنوز بسته نشده، به‌اشتباه stale محسوب نشود.

## 2. Health جریان و Provider

هر جریان یکی از وضعیت‌های `healthy`، `degraded`، `paused` یا `no_data` دارد. موارد زیر جریان فعال
را degraded می‌کنند:

- نبود route فعال و سالم؛
- شکست آخرین Poll؛
- عبور از بودجه Freshness؛
- عقب‌افتادن Poll بیش از یک cadence؛
- وجود Window واجد شرایط نهایی‌سازی.

برای هر route فقط state، health، زمان آخرین test و error code امن منتشر می‌شود. پیام خام provider،
credential و payload در projection وجود ندارد.

## 3. Backlog و Replay

خلاصهٔ backlog شامل موارد زیر است:

- jobهای queued/running دریافت و replay؛
- Watchlistهای overdue و Windowهای در انتظار finalization؛
- decisionهای revision-required که هنوز درخواست replay ندارند؛
- replayهای فاقد revision، replayهای ناموفق و تعداد revisionهای کامل‌شده.

لیست replayهای اخیر فقط lineage ID، reason، وضعیت job، error code امن و revision/version نهایی را
نمایش می‌دهد. payload، error message و هویت worker عمداً حذف شده‌اند.

## 4. API و رابط کاربری

`GET /api/v1/monitoring/market-data` قرارداد versioned با schema
`market-data-monitoring-v1` برمی‌گرداند. صفحهٔ Monitoring این projection را همراه summary قبلی به
صورت موازی می‌خواند و در کارت‌های responsive فارسی/انگلیسی نمایش می‌دهد:

- خلاصهٔ stream، stale، Poll backlog و Replay backlog؛
- کارت هر جریان با health، freshness، lag/target و routeها؛
- چرخهٔ replayهای اخیر بدون action یا mutation.

شناسه‌های بلند break می‌شوند، اعداد operational در جهت LTR باقی می‌مانند و نمایش موبایل به جدول
سنگین وابسته نیست.

## 5. مرز امنیت و عملکرد

- endpoint فقط `GET` است؛
- هیچ live order، credential، wallet، deposit یا withdrawal اضافه نشده است؛
- داده‌ها از جداول ماندگار موجود خوانده می‌شوند و schema/migration تازه‌ای لازم نیست؛
- queryها bounded هستند و لیست replay به 20 مورد اخیر محدود است؛
- هیچ payload یا پیام خطای خام از job/provider به API یا UI راه ندارد.

## 6. گیت خروج P2-06

- [x] Freshness و Lag بر اساس آخرین Window نهایی و policy محاسبه می‌شوند.
- [x] Health جریان، وضعیت routeها و علت‌های عملیاتی اصلی قابل مشاهده‌اند.
- [x] Poll، Finalization و Replay backlog در یک projection خواندنی جمع می‌شوند.
- [x] Replay/Revision اخیر بدون payload، worker identity یا error message منتشر می‌شود.
- [x] endpoint فقط‌خواندنی و قرارداد frontend/backend هماهنگ است.
- [x] UI فارسی/انگلیسی، responsive و بدون action معاملاتی است.
- [x] تست‌های backend، API، client، UI و critical journey اضافه شده‌اند.
- [ ] full backend/frontend CI روی SHA نهایی سبز شود.

گام بعدی `P2-07 — Retention and Safe Purge` است؛ در آن policyهای retention فریز‌شده به purge
دسته‌ای، قابل ممیزی و ایمن برای Raw/Event/Window/Watermark و Replay evidence متصل می‌شوند.
