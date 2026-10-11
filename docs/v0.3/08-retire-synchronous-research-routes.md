# P1-04 — Retire Synchronous Research Routes

وضعیت: **تکمیل‌شده در کد؛ آمادهٔ پذیرش CI**

تاریخ تصمیم: `2026-10-11`

این مرحله cutover عملیات سنگین Research به worker durable را کامل می‌کند. شش route قدیمی برای
سازگاری آدرس حذف فیزیکی نشده‌اند، اما در runtime تولیدی همیشه `410 Gone` برمی‌گردانند و دیگر
Research Pipeline یا Walk-Forward Executor را در request process اجرا نمی‌کنند.

## مسیرهای بازنشسته

| route قدیمی | جایگزین durable |
| --- | --- |
| `POST /api/v1/research/ema-crossover` | `POST /api/v1/research/experiment-executions` |
| `POST /api/v1/research/experiments/ema-crossover` | `POST /api/v1/research/experiment-executions` |
| `POST /api/v1/research/experiments/ema-crossover/from-dataset` | `POST /api/v1/research/experiment-executions` |
| `POST /api/v1/research/walk-forward/ema-crossover` | `POST /api/v1/research/walk-forward-executions` |
| `POST /api/v1/research/walk-forward/runs/ema-crossover` | `POST /api/v1/research/walk-forward-executions` |
| `POST /api/v1/research/walk-forward/runs/ema-crossover/from-dataset` | `POST /api/v1/research/walk-forward-executions` |

routeهای inline که candle دریافت می‌کردند، client را ملزم می‌کنند ابتدا Dataset را persist/import
کند و سپس شناسهٔ Dataset را به endpoint durable بدهد. پاسخ retirement شامل کد ثابت، endpoint
جایگزین و گام‌های migration است.

## قرارداد deprecation

تمام مسیرهای بالا:

- در OpenAPI با `deprecated=true` مشخص شده‌اند؛
- پاسخ `410` مستند دارند؛
- `Cache-Control: no-store` می‌فرستند؛
- header استاندارد `Deprecation` و تاریخ `Sunset` دارند؛
- با `Link: <...>; rel="successor-version"` جایگزین durable را معرفی می‌کنند.

کد خطای پایدار:

```json
{
  "detail": {
    "code": "legacy_synchronous_research_route_retired",
    "message": "Synchronous research execution is retired. Submit a durable background job and poll its execution resource instead.",
    "replacement_endpoint": "/api/v1/research/experiment-executions",
    "migration_steps": [
      "Submit the stored dataset ID and versioned strategy parameters to the durable experiment execution endpoint."
    ]
  }
}
```

## محدوده‌ای که synchronous باقی می‌ماند

این cutover فقط mutationهای محاسباتی سنگین را می‌بندد. endpointهای GET، catalog، summary،
analytics، report/export و replay verification خواندنی عمداً حفظ شده‌اند. previewهای read-only
Market Data نیز خارج از محدوده P1-04 هستند.

بدنه‌های قدیمی برای regression contractهای تاریخی فقط با override صریح dependency در test suite
قابل اجرا هستند. این override تنظیم runtime یا feature flag تولیدی نیست و از HTTP قابل فعال‌سازی
نیست. guard معماری نیز مانع استفاده دوباره frontend از هر شش URL بازنشسته می‌شود.

## Storage و migration

تغییر schema یا migration دیتابیس لازم نیست. این مرحله فقط routing، OpenAPI و client contract را
تغییر می‌دهد.

## معیار خروج P1-04

- [x] هر شش mutation سنگین synchronous در production با `410 Gone` بسته شده‌اند.
- [x] هر route جایگزین durable و migration steps قابل‌پردازش دارد.
- [x] OpenAPI و headerهای deprecation/sunset کامل‌اند.
- [x] frontend دیگر هیچ URL بازنشسته‌ای را فراخوانی نمی‌کند.
- [x] endpointهای خواندنی و سبک دست‌نخورده باقی مانده‌اند.
- [x] regressionهای تاریخی فقط با opt-in صریح تست اجرا می‌شوند.
- [x] schema دیتابیس بدون تغییر است.

مرحلهٔ بعد `P1-05` است: یکپارچه‌سازی allowlist، retry، cancellation و lease policy تمام workerها.
