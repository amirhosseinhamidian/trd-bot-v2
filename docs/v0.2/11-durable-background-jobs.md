# TB2-008 — foundation کارهای پس‌زمینه بادوام

## تصمیم معماری

صف روی PostgreSQL موجود نگهداری می‌شود و broker تازه‌ای به استقرار تحمیل نمی‌کند. هر job
یک envelope نسخه‌دار با `kind` allowlisted و payload JSON دارد. API عمومی اجازه enqueue
کردن callable یا kind دلخواه را نمی‌دهد؛ domain serviceهای مراحل بعد job می‌سازند.
responseهای API نیز payload، idempotency key و شناسه worker را افشا نمی‌کنند و payload باید
فقط شامل identifier/config غیرحساس باشد، نه credential یا بایت فایل.

`SELECT ... FOR UPDATE SKIP LOCKED` claim هم‌زمان workerها را جدا می‌کند. SQLite فقط برای
unit/migration test استفاده می‌شود؛ تضمین concurrency نهایی باید روی PostgreSQL آزموده شود.

## lifecycle

- `queued`: آماده claim پس از `run_after`، بدون lease
- `running`: دارای `lease_owner` و `lease_expires_at`، attempt افزایش‌یافته
- `succeeded`: progress برابر ۱۰۰ و result reference اختیاری
- `failed`: error code/message پایدار پس از failure غیرقابل retry یا اتمام budget
- `cancelled`: لغو پیش از claim فوری و حین اجرا به‌صورت cooperative

heartbeat فقط توسط مالک lease پذیرفته می‌شود، progress عقب نمی‌رود و stale worker پس از
انقضای lease حق ثبت نتیجه ندارد. job منقضی در attempt بعد reclaim می‌شود؛ اگر budget تمام
شده باشد با `attempts_exhausted` terminal می‌شود.

## idempotency و retry

ترکیب `(kind, idempotency_key)` یکتا است. enqueue تکراری همان job را برمی‌گرداند. failure
قابل retry تا `max_attempts` دوباره queued می‌شود و `run_after` امکان backoff می‌دهد.
retry دستی فقط برای failed مجاز است و یک attempt تازه به budget اضافه می‌کند؛ history همان
job حفظ می‌شود.

پیام خطای handler در API عمومی generic است تا متن exception داخلی یا دادهٔ حساس افشا نشود.
جزئیات عملیاتی باید در log محدودشده و خارج از payload عمومی ثبت شوند.

## API و worker

- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel`
- `POST /api/v1/jobs/{job_id}/retry`

worker مستقل:

```bash
python scripts/run_background_worker.py
python scripts/run_background_worker.py --once
```

registry handlerهای Experiment، Walk-Forward و Import/Refresh دادهٔ Provider را allowlist
می‌کند. enqueueهای قدیمی FastAPI و اتصال Optimization در مراحل domain مربوط انجام می‌شوند تا
migration عملیاتی و rollback هر جریان مستقل بماند.

## معیار پذیرش

- enqueue هم‌کلید job دوم نمی‌سازد.
- دو worker یک job دارای lease معتبر را هم‌زمان claim نمی‌کنند.
- lease منقضی reclaim و stale worker رد می‌شود.
- progress پس از repository/session تازه قابل خواندن است.
- failure موقت تا budget requeue و سپس terminal می‌شود.
- queued cancel فوری و running cancel cooperative است.
- migration از DB خالی و downgrade کامل جدول را ایجاد/حذف می‌کند.

این سند نتیجه اجرای test یا migration را ادعا نمی‌کند؛ شواهد PostgreSQL و CI روی SHA کاربر
ثبت می‌شود.
