# P4-05 — Quiet Hours، Expiry و Publication Policies

وضعیت: **پیاده‌سازی‌شده و آمادهٔ P4-06**

تاریخ تصمیم: `2026-10-18`

مبنای کد: P4-04 در commit
`0b0eedd34fd27ec79a900ddc200b19ebdf63fe21`

این مرحله آخرین guardهای لازم میان match شدن Rule و انتشار Alert در Inbox را durable می‌کند. هر تصمیم
انتشار به نسخه دقیق policy، وضعیت cooldown/deduplication، snooze فعال و زمان واقعی اجرای worker متصل
است. هیچ delivery بیرونی، credential یا سفارش واقعی ایجاد نمی‌شود.

## 1. سیاست نسخه‌دار انتشار

`AlertPublicationPolicy` یک تاریخچهٔ append-only با checksum دارد. نسخهٔ `0` default داخلی و بدون
Quiet Hours است؛ نخستین تغییر اپراتور نسخهٔ `1` را می‌سازد و نسخه‌های قبلی را بازنویسی نمی‌کند.

Policy شامل این فیلدهاست:

- فعال یا غیرفعال بودن Quiet Hours؛
- دقیقه شروع و پایان روز با پشتیبانی از بازهٔ عبوری از نیمه‌شب؛
- نام IANA منطقه زمانی مانند `Asia/Tehran`؛
- اجازه عبور Alertهای `critical` از Quiet Hours؛
- actor، زمان تغییر و checksum محتوای کامل.

## 2. ترتیب fail-closed انتشار

worker ابتدا شرط‌های پایهٔ P4-03 را بررسی می‌کند. فقط outcomeای که در غیر این صورت publishable است از
guardهای P4-05 عبور می‌کند:

1. اگر source در زمان واقعی اجرای worker منقضی شده باشد، `source_expired`؛
2. اگر Alert مشابه همان Rule و stream داخل dedup window باشد، `duplicate`؛
3. اگر cooldown آخرین Alert همان Rule و stream فعال باشد، `cooldown_active`؛
4. اگر Alert قبلی همان stream هنوز snooze فعال داشته باشد، `snoozed`؛
5. اگر زمان محلی داخل Quiet Hours باشد، `quiet_hours`.

هر suppression در `AlertEvaluationRecord` ثبت می‌شود. علاوه بر آن،
`alert_publication_decisions` نسخه و checksum policy، Alert قبلی، `blocked_until` و زمان واقعی تصمیم را
نگه می‌دارد. Evaluation و Publication Decision در یک transaction نوشته می‌شوند. retry پس از commit
همان Evaluation قبلی را برمی‌گرداند و تغییر بعدی Policy نتیجه را بازنویسی نمی‌کند.

## 3. semantics انقضا

Alertهای immutable پس از expiry حذف یا بازنویسی نمی‌شوند. sweep انقضا فقط یک evidence یکتا و append-only
در `alert_expiry_records` می‌سازد. اجرای دوباره idempotent است و batch بین ۱ تا ۱۰۰۰ رکورد محدود می‌شود.
بنابراین Inbox همچنان status منقضی را محاسبه می‌کند و audit trail نیز زمان دقیق عبور از مرز expiry را
دارد.

اجرای CLI:

```bash
PYTHONPATH=src python scripts/manage_alert_expiry.py plan \
  --requested-by operator:maintenance

PYTHONPATH=src python scripts/manage_alert_expiry.py execute \
  --requested-by operator:maintenance \
  --batch-limit 100
```

## 4. API و UI

| متد | مسیر | مسئولیت |
| --- | --- | --- |
| `GET` | `/api/v1/alerts/publication-policy` | دریافت آخرین نسخه یا default داخلی |
| `POST` | `/api/v1/alerts/publication-policy` | ساخت revision جدید policy |
| `GET` | `/api/v1/alerts/expiry` | summary انقضاهای ثبت‌شده و معوق |
| `POST` | `/api/v1/alerts/expiry/sweep` | materialize کردن evidence انقضا در batch محدود |

Alert Center فارسی و انگلیسی اکنون فرم قابل‌دسترسی Quiet Hours، منطقه زمانی، critical bypass و کارت
چرخه انقضا دارد. mutationها `no-store` هستند، touch target مناسب دارند و وضعیت موفق/خطا با `aria-live`
اعلام می‌شود.

## 5. مرز P4-05

این مرحله Shadow/Paper outcome، سفارش شبیه‌سازی‌شده، journal عملکرد، drift، false-positive، email، SMS،
push و webhook را اضافه نمی‌کند. Alert همچنان فقط ابزار تصمیم درون‌برنامه‌ای است.

## 6. معیار خروج P4-05

- [x] Quiet Hours timezone-aware و عبوری از نیمه‌شب است.
- [x] Critical bypass صریح و قابل‌تنظیم است.
- [x] policyها immutable، نسخه‌دار و checksum-bound هستند.
- [x] dedup window، cooldown و snooze روی Rule و stream صحیح enforce می‌شوند.
- [x] expiry در زمان اجرای worker fail-closed بررسی می‌شود.
- [x] Publication Decision همراه Evaluation اتمیک و audit‌پذیر است.
- [x] expiry sweep محدود، idempotent و non-destructive است.
- [x] API و UI دو‌زبانهٔ policy/expiry آماده‌اند.
- [x] هیچ قابلیت live execution یا delivery بیرونی اضافه نشده است.

گام بعدی `P4-06 — Shadow/Paper Alert Evaluation بدون سفارش واقعی` است.
