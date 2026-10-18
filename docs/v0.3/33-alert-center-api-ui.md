# P4-04 — Alert Center، Acknowledge و Snooze

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P4-05**

تاریخ تصمیم: `2026-10-18`

مبنای کد: P4-03 در commit
`4fff8d950db042a14c65b8907c2edbf96f73a0a9`

این مرحله Alertهای durable مرحلهٔ قبل را به Inbox عملیاتی دو‌زبانه متصل می‌کند. اپراتور می‌تواند هشدار
را تأیید یا برای مدت محدود snooze کند و هر تغییر به‌صورت durable و audit‌پذیر ثبت می‌شود. این اکشن‌ها
صرفاً وضعیت Inbox را تغییر می‌دهند و هیچ سفارش، پیام بیرونی یا اتصال credentialدار ایجاد نمی‌کنند.

## 1. مدل lifecycle

`AlertDraft` همچنان immutable باقی می‌ماند. وضعیت قابل‌تغییر اپراتور در جدول مستقل
`alert_inbox_states` نگه‌داری می‌شود و وضعیت نمایشی در زمان read محاسبه می‌شود:

| وضعیت | شرط |
| --- | --- |
| `active` | تأیید نشده، منقضی نشده و snooze فعال ندارد |
| `snoozed` | تأیید نشده، منقضی نشده و `snoozed_until` در آینده است |
| `acknowledged` | acknowledgement durable دارد |
| `expired` | تأیید نشده و زمان اعتبار Alert پایان یافته است |

acknowledgement نهایی است و snooze قبلی را پاک می‌کند. Alert تأییدشده یا منقضی snooze نمی‌شود. درخواست
دوبارهٔ acknowledge idempotent است و action تکراری تولید نمی‌کند.

## 2. audit trail و transaction

هر تغییر موفق علاوه بر state جاری، یک رکورد append-only در `alert_actions` می‌نویسد. action شامل نوع،
actor، زمان، انتهای snooze و checksum کل payload است. state و action در یک transaction commit می‌شوند؛
در نتیجه حالت جدید بدون evidence یا evidence بدون state باقی نمی‌ماند.

migration ابتدا برای Alertهای موجود state اولیه می‌سازد. مسیر publish جدید نیز Alert و state اولیه را در
همان transaction P4-03 ثبت می‌کند.

## 3. API

| متد | مسیر | مسئولیت |
| --- | --- | --- |
| `GET` | `/api/v1/alerts` | فهرست صفحه‌بندی‌شده با فیلتر status و severity |
| `GET` | `/api/v1/alerts/summary` | شمارش disjoint وضعیت‌های Inbox |
| `GET` | `/api/v1/alerts/{alert_id}` | جزئیات Alert و state جاری |
| `POST` | `/api/v1/alerts/{alert_id}/acknowledge` | ثبت acknowledgement idempotent |
| `POST` | `/api/v1/alerts/{alert_id}/snooze` | تعویق بین ۵ دقیقه تا ۲۴ ساعت |

payload اکشن فقط actor محدود و duration عددی را می‌پذیرد. Alert ناموجود `404` و اکشن ناسازگار روی Alert
منقضی یا تأییدشده `409` با error code پایدار برمی‌گرداند. ورودی نامعتبر با handler سراسری sanitize
می‌شود.

## 4. رابط کاربری

مسیرهای `/fa/alerts` و `/en/alerts` این امکانات را ارائه می‌کنند:

- summary چهار وضعیت و تعداد کل؛
- فیلتر status و severity؛
- کارت responsive با severity، وضعیت، pair، regime، confidence و زمان‌ها؛
- اکشن‌های همیشه‌قابل‌دسترسی acknowledge و snooze با touch target مناسب؛
- loading، empty، error و action-error state؛
- disclosure بسته برای IDها، checksum و lineage فنی؛
- ناوبری desktop و mobile در گروه Strategy & Decision.

صفحه با Server Component دادهٔ اولیه را می‌گیرد و فقط بخش تعاملی Client Component است. تمام readها و
mutationها `no-store` هستند و پس از اکشن، catalog و summary از backend تازه‌سازی می‌شوند.

## 5. مرز P4-04

این مرحله عمداً quiet hours، suppression ناشی از cooldown/snooze پیش از publish، expiry cleanup، email،
SMS، push و webhook را اضافه نمی‌کند. سیاست publication و expiry در P4-05 تکمیل می‌شود.

## 6. معیار خروج P4-04

- [x] هر Alert منتشرشده state اولیهٔ durable دارد.
- [x] وضعیت‌های active، snoozed، acknowledged و expired به‌صورت disjoint محاسبه می‌شوند.
- [x] acknowledge idempotent و snooze زمان‌دار است.
- [x] state و audit action اتمیک ثبت می‌شوند.
- [x] API فهرست، summary، detail و دو mutation را ارائه می‌کند.
- [x] Alert Center فارسی و انگلیسی، responsive و قابل استفاده با keyboard است.
- [x] loading، empty، error و lineage disclosure پوشش داده شده‌اند.
- [x] هیچ live execution یا delivery بیرونی اضافه نشده است.

گام بعدی `P4-05 — Quiet Hours، Expiry و Publication Policies` است.
