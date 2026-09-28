# TB2-023 — Monitoring v2 و شواهد بازیابی

## تصمیم دامنه

`TB2-022` طبق roadmap قابلیت اختیاری Research UX است و برای انتشار فعلی defer شد. این مرحله
Monitoring موجود را با قرارداد `operational-monitoring-v1` گسترش می‌دهد و هیچ endpoint سفارش،
عملیات معامله یا جدول تازه‌ای اضافه نمی‌کند. projection هنگام `GET /api/v1/monitoring/summary`
فقط از state ماندگار زیر ساخته می‌شود:

- سلامت آخرین تست Connectionهای عمومی Market Data؛
- auditهای immutable Import/Refresh؛
- envelope صف PostgreSQL و leaseهای worker.

## معنا و بازه محاسبات

- `queued/running/succeeded/failed/cancelled` از شمار کامل رکوردهای صف می‌آید.
- `stuck` فقط job با وضعیت `running` و `lease_expires_at <= generated_at` است. این علامت نیاز به
  reclaim یا بررسی worker است؛ به‌تنهایی رکورد را mutate نمی‌کند.
- نرخ شکست Import از حداکثر ۱۰۰ audit جدید محاسبه می‌شود و `sample_size` مخرج را آشکار می‌کند.
  بازه خالی `null` است، نه صفر گمراه‌کننده.
- میانگین مدت از حداکثر ۱۰۰ job terminal دارای start/finish معتبر ساخته می‌شود و
  `recent_terminal_sample_size` همراه آن می‌آید.
- علت‌های شکست با `error_code` پایدار aggregate می‌شوند. متن provider، payload صف،
  idempotency key و worker ID در projection وجود ندارند.

وجود job گیرکرده وضعیت کلی را `critical` می‌کند. Connection ناسالم، Import ناموفق یا job شکست‌خورده
وضعیت را دست‌کم `warning` می‌کند. recommendationهای معماری قبلی همچنان در همین status لحاظ می‌شوند.

## UI و بازیابی

صفحه Monitoring کارت‌های Connection/Import/Queue، jobهای اخیر و علت‌های شکست را read-only نشان
می‌دهد. عملیات `cancel` و `retry` همچنان فقط از API عمومی job و با lifecycle موجود انجام می‌شوند؛
UI این مرحله دکمه mutation تازه‌ای نمی‌سازد. پس از restart، صفحه از DB دوباره ساخته می‌شود و به
حافظه process وب وابسته نیست.

## مرزهای باقی‌مانده

فایل خام CSV/JSON/Parquet ذخیره نمی‌شود؛ بنابراین فرستادن بایت فایل در JSON صف ممنوع می‌ماند و
انتقال آن به worker نیازمند staging محدود، checksum-bound، expiry و cleanup است. همچنین routeهای
قدیمی Experiment/Walk-Forward هنوز از FastAPI `BackgroundTasks` استفاده می‌کنند. هر دو مورد در
TB2-024 به‌عنوان gate صریح پذیرفته، اصلاح یا با تصمیم release ثبت می‌شوند؛ این سند آن‌ها را بسته
اعلام نمی‌کند.

## آزمون پذیرش مرحله

1. Connection ناسالم باید code امن و status هشدار بسازد؛ هیچ متن حساس نمایش داده نشود.
2. lease منقضی باید بدون mutation رکورد به‌عنوان stuck و status بحرانی دیده شود.
3. یک Import موفق و یک شکست‌خورده نرخ `0.5` با مخرج دو بسازند؛ بازه خالی `null` بماند.
4. علت شکست job aggregate و recent job بدون payload/worker identity در API/UI نمایش داده شود.
5. backend lint/type/test و frontend format/lint/test/build روی SHA مرحله سبز باشند؛ restart واقعی،
   migration-from-zero و PostgreSQL concurrency در TB2-024 دوباره اجرا شوند.
