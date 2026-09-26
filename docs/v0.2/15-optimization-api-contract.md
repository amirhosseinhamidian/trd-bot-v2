# TB2-012 — قرارداد API اجرای Optimization

## مرز مرحله

این مرحله API تولیدی ایجاد و مشاهده Optimization را فعال کرد. از TB2-013 محاسبهٔ trialها نه داخل request
و نه در background task موقت FastAPI، بلکه در صف durable و worker مستقل انجام می‌شود. create با HTTP 202
یک submission شامل execution، خلاصهٔ job و پرچم `created` برمی‌گرداند.

## endpointها

```text
POST /api/v1/research/optimization-executions
GET  /api/v1/research/optimization-executions?limit=20&offset=0
GET  /api/v1/research/optimization-executions/{execution_id}
```

درخواست create فقط intent قابل اعتماد زیر را می‌پذیرد:

- `dataset_id` موجود؛
- `strategy_name` و `strategy_version` دقیق Registry؛
- `parameter_grid` صریح؛
- objective تاریخی؛
- `horizon_candles` و `backtest_config`.

ID اجرا، زمان‌ها، status، progress، experiment IDها، نتیجه برتر و خطا همگی server-owned هستند.
endpoint عمومی برای `start`، `complete` یا `fail` وجود ندارد.

## bounded planning و خطاها

`OptimizationPlanner` schema پارامتر همان StrategyVersion را اعمال و مقدارها را canonical می‌کند.
تعداد ترکیب‌های درخواستی پیش از اجرای trial حداکثر ۱۰۰ است؛ ترکیب‌های cross-parameter نامعتبر
در plan با `skipped_combinations` ثبت می‌شوند. plan بدون trial معتبر رد می‌شود.

خطاهای دامنه مسیر جدید detail ماشین‌خوان دارند:

| HTTP | code | معنی |
| --- | --- | --- |
| 404 | `dataset_not_found` | Dataset immutable موجود نیست. |
| 422 | `invalid_optimization_plan` | نسخه، grid، مقدار یا محدودیت plan معتبر نیست. |
| 409 | `optimization_execution_conflict` | execution و job به‌صورت اتمیک قابل enqueue نبودند. |
| 404 | `optimization_execution_not_found` | detail درخواستی موجود نیست. |

validation ساختاری FastAPI/Pydantic همچنان قرارداد استاندارد 422 برنامه را دارد.

## persistence و lifecycle

API از `SqlAlchemyOptimizationExecutionEnqueuer` با session request-scoped استفاده می‌کند و execution
و job را در یک transaction می‌نویسد. کلید idempotency از intent canonical ساخته می‌شود؛ تکرار همان
درخواست execution/job قبلی را با `created=false` برمی‌گرداند. migration جدید لازم نیست، چون جدول‌ها
و indexهای لازم از قبل وجود دارند. جزئیات lifecycle worker در سند TB2-013 ثبت شده است.
