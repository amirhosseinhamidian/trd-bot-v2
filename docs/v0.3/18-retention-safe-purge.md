# P2-07 — Retention and Safe Purge

وضعیت: **پیاده‌سازی‌شده؛ evidence نهایی PostgreSQL و CI در انتظار اجرای مالک مخزن**

تاریخ تصمیم: `2026-10-15`

مبنای کد: P2-06 در commit
`435a05458d81a684e8e89a5b0cc9c7b29fba3284`

این مرحله policy فریز‌شدهٔ retention را به یک عملیات صریح، محدود، قابل ممیزی و fail-closed متصل
می‌کند. migration فقط ساختار کنترل و audit را اضافه می‌کند و در زمان deploy هیچ داده‌ای را حذف
نمی‌کند.

## 1. بازه‌های حذف

| داده | حداقل عمر پیش از eligibility | محافظت تکمیلی |
| --- | ---: | --- |
| Raw observation | 30 روز | رکورد جدیدتر انتخاب نمی‌شود |
| Normalized event | 90 روز | تا وجود Outbox یا Decision حذف نمی‌شود |
| Inbox receipt | 180 روز | فقط بر اساس `last_seen_at` |
| Outbox تحویل‌شده | 7 روز | فقط وضعیت `delivered` |
| Outbox ناموفق | 30 روز | فقط وضعیت `failed` |
| Window موقت | 30 روز پس از finalization | فقط نسخهٔ `provisional` |
| Replay request و revision evidence | 365 روز | فقط job نهایی و پس از حذف revision |
| Watermark بدون مرجع | 365 روز | هیچ Decision، Finalization یا Revision به آن متصل نباشد |
| Window نهایی | هرگز | در purge خودکار انتخاب نمی‌شود |

Dataset و نتیجه‌های Experiment/Walk-Forward خارج از این عملیات‌اند و هیچ سیاستی در این مرحله برای
حذف آن‌ها اضافه نشده است.

## 2. قرارداد plan و execute

- هر اجرا یک سقف مشترک `1..500` رکورد برای تمام scopeها دارد؛
- `plan` دقیقاً همان query و ترتیب deterministic اجرای واقعی را به کار می‌برد، ولی هیچ رکوردی حذف
  نمی‌کند؛
- `execute` فقط با تأیید صریح نسخهٔ policy مجاز است؛
- حذف dependencyها در چند batch همگرا می‌شود: ابتدا Outbox/Revision/Request/Decision و در اجرای
  بعدی parentهای بدون مرجع؛
- تعداد deleteشده باید دقیقاً با plan همان transaction برابر باشد؛ در غیر این صورت کل batch
  rollback می‌شود؛
- singleton lock، تغییر hold و هر batch purge را serialize می‌کند.

## 3. Legal/Incident Hold

Hold از نوع `legal` یا `incident` دارای دلیل، ثبت‌کننده و زمان ماندگار است. وجود حتی یک hold فعال،
هم `plan` و هم `execute` را قبل از انتخاب داده متوقف می‌کند. نتیجهٔ blocked با شناسهٔ holdها ثبت
می‌شود. آزادسازی hold نیز actor و timestamp را در همان history نگه می‌دارد.

## 4. Audit و خطا

هر درخواست completed، blocked یا transaction-failed یک run مستقل در
`market_data_retention_runs` ثبت می‌کند. audit شامل policy، mode، requester، cutoffها، count هر
scope، سقف batch، outcome و error code امن است؛ شناسه یا payload داده‌های حذف‌شده در آن ذخیره
نمی‌شود. اگر ثبت audit شکست بخورد عملیات با خطا متوقف می‌شود.

Migration `20261015_0024` سه جدول اضافه می‌کند:

- `market_data_retention_control` برای lock سراسری؛
- `market_data_retention_holds` برای lifecycle ماندگار hold؛
- `market_data_retention_runs` برای audit append-only عملیات.

## 5. اجرای عملیاتی

ابتدا migration را روی محیط هدف اجرا کنید و سپس همیشه plan را ببینید:

```bash
PYTHONPATH=src alembic upgrade head

PYTHONPATH=src python scripts/manage_market_data_retention.py plan \
  --requested-by 'operator:amir' \
  --batch-limit 100
```

اجرای حذف به تأیید دقیق policy نیاز دارد:

```bash
PYTHONPATH=src python scripts/manage_market_data_retention.py execute \
  --requested-by 'operator:amir' \
  --batch-limit 100 \
  --confirm-policy-version market-data-service-level-policy-v1
```

کنترل hold و مشاهدهٔ audit:

```bash
PYTHONPATH=src python scripts/manage_market_data_retention.py place-hold \
  --kind incident \
  --reason 'incident-2026-10-15' \
  --requested-by 'operator:amir'

PYTHONPATH=src python scripts/manage_market_data_retention.py list-holds
PYTHONPATH=src python scripts/manage_market_data_retention.py list-runs --limit 20

PYTHONPATH=src python scripts/manage_market_data_retention.py release-hold \
  --hold-id 'market-retention-hold-...' \
  --requested-by 'operator:amir'
```

برای drain کردن backlog، plan و execute را batch‌به‌batch تکرار کنید تا `selected.total` صفر شود.

## 6. مرز امنیت

- CLI هیچ secret یا credential را در audit نمی‌پذیرد یا منتشر نمی‌کند؛
- هیچ live order، wallet، deposit یا withdrawal اضافه نشده است؛
- finalized Windowها و Watermarkهای دارای lineage محافظت می‌شوند؛
- requestهای replay فاقد job نهایی و decisionهای replay بدون request حذف نمی‌شوند؛
- failure دیتابیس فقط با error code ثابت منتشر می‌شود و جزئیات driver در audit قرار نمی‌گیرد.

## 7. گیت خروج P2-07

- [x] dry-run و execute از plan و سقف batch مشترک استفاده می‌کنند.
- [x] Hold فعال هر دو mode را fail-closed متوقف می‌کند.
- [x] Window نهایی و lineage فعال Replay/Watermark حذف نمی‌شوند.
- [x] dependencyها با ترتیب امن و در batchهای همگرا پاک می‌شوند.
- [x] rollback تراکنشی مانع حذف ناقص می‌شود.
- [x] run و lifecycle hold به‌صورت ماندگار و sanitizeشده قابل مشاهده‌اند.
- [x] migration فقط schema/audit را اضافه می‌کند و purge ضمن deploy ندارد.
- [x] تست‌های SQLite، migration و مسیر PostgreSQL اضافه شده‌اند.
- [ ] full backend و PostgreSQL CI روی SHA نهایی سبز شود.

گام بعدی `P2-08 — Phase Two Acceptance and Freeze` است؛ در آن چرخهٔ migration، recovery،
deduplication، provider fallback، SLO، security boundary و CI به‌صورت یک evidence نهایی freeze
می‌شوند.
