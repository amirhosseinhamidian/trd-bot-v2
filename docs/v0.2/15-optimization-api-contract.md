# TB2-012 — قرارداد API اجرای Optimization

## مرز مرحله

این مرحله API تولیدی ایجاد و مشاهده Optimization را فعال می‌کند، اما محاسبه trialها را داخل request
یا background task موقت FastAPI اجرا نمی‌کند. اتصال به صف durable و worker مستقل متعلق به TB2-013
است. بنابراین create در این مرحله یک رکورد `queued` معتبر می‌سازد و با HTTP 201 برمی‌گرداند.

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
| 409 | `optimization_execution_conflict` | رکورد execution قابل persist نبود. |
| 404 | `optimization_execution_not_found` | detail درخواستی موجود نیست. |

validation ساختاری FastAPI/Pydantic همچنان قرارداد استاندارد 422 برنامه را دارد.

## persistence و lifecycle

API از `SqlAlchemyOptimizationExecutionRepository` با session request-scoped استفاده می‌کند؛ الگوی
قدیمی `next(get_database_session())` حذف شده است. migration جدید لازم نیست، چون جدول و indexهای
`20260831_0014_optimization_executions.py` از قبل وجود دارند.

TB2-013 باید create و enqueue را در مرز تراکنشی امن هماهنگ کند، handler allowlisted بسازد و فقط
worker را مجاز به transitionهای lifecycle و ثبت trialها کند. در آن مرحله پاسخ create به HTTP 202
تغییر می‌کند.
