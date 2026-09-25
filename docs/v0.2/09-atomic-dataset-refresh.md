# TB2-005 — تراکنش اتمیک Dataset و Version Lineage

این مرحله ریسک `R-04` مبنا را می‌بندد: ثبت Snapshot و رکورد موفق Import/Refresh دیگر دو
commit مستقل نیست. داده ابتدا fetch و validate می‌شود و سپس Snapshot canonical و audit record در
یک مرز تراکنشی ثبت می‌شوند.

## قرارداد commit

- سرویس historical import فقط Dataset معتبر را می‌سازد و persistence انجام نمی‌دهد.
- `HistoricalDatasetCommitter` تنها مسیر ثبت نتیجهٔ موفق Import و Refresh است.
- پیاده‌سازی SQLAlchemy، Dataset row و MarketDataImport row را روی همان request-scoped Session
  stage می‌کند و فقط یک‌بار commit می‌کند.
- اگر stage یا commit تاریخچه شکست بخورد، کل transaction rollback می‌شود؛ Snapshot جدید نباید
  بدون History باقی بماند.
- failureهای fetch، quality و preview mismatch چون Snapshot موفقی ندارند، مثل قبل به‌صورت audit
  failure مستقل ثبت می‌شوند.

این تغییر به migration تازه نیاز ندارد. unique index موجود روی
`(root_import_id, version_number)` آخرین guard دیتابیس برای شماره نسخه است.

## قرارداد Refresh هم‌زمان

درخواست Refresh هنوز پیش از fetch بررسی سریع latest بودن را انجام می‌دهد، اما این بررسی برای جلوگیری
از race کافی نیست. Committer درست پیش از write نیز latest successful version را می‌خواند:

1. در PostgreSQL ردیف lineage با `FOR UPDATE` خوانده می‌شود؛
2. `parent_import_id` و `version_number` پیشنهادی باید دقیقاً ادامهٔ latest باشند؛
3. unique index از ثبت دو نسخهٔ یکسان جلوگیری می‌کند؛
4. اگر writer دیگری زودتر lineage را جلو برده باشد، transaction rollback و پاسخ HTTP 409 است؛
5. تلاش بازنده با `error_code=refresh_conflict`، بدون `version_number` و بدون Snapshot یتیم ثبت
   می‌شود.

پیام پایدار conflict این است:

```text
dataset refresh lost a concurrency race; reload version history
```

کاربر باید version history را reload کند و فقط latest successful version را دوباره Refresh کند.

## قرارداد محتوای مشترک و provenance

هویت Dataset محتوایی و مبتنی بر checksum است. اگر دو Connection یا دو Import محتوای یکسان برگردانند:

- فقط یک Snapshot canonical ذخیره می‌شود؛
- Importی که برای اولین بار Snapshot را می‌سازد، provenance سازنده و root/version 1 را دارد؛
- Importهای بعدی audit record مستقل شامل Connection، Provider، requested range و زمان خود را نگه
  می‌دارند؛
- Import بعدی برای همان محتوا root/version تازه ادعا نمی‌کند؛
- Refresh هر lineage می‌تواند به Snapshot محتوایی موجود اشاره کند، بدون overwrite کردن provenance
  یا نتایج پژوهشی Snapshot قبلی.

در نتیجه provenance Snapshot دربارهٔ سازندهٔ canonical content است و provenance هر تلاش از
MarketDataImportRecord بازسازی می‌شود.

از TB2-006، `quality_report` کامل هر تلاش نیز داخل payload همان `MarketDataImportRecord` ثبت
می‌شود. بنابراین Refresh بدون تغییر محتوا می‌تواند Snapshot canonical قبلی را reuse کند، اما score و
policy ارزیابی تازه همچنان در version history قابل ممیزی می‌مانند.

## شواهد پذیرش

تست‌های این مرحله باید بدون شبکهٔ زنده این موارد را پوشش دهند:

1. ثبت موفق Snapshot و History در یک commit؛
2. rollback Snapshot هنگام failure تزریق‌شده در History؛
3. استفادهٔ مجدد از Snapshot برای checksum برابر همراه دو audit record مستقل؛
4. تخصیص root/version 1 فقط به Import سازنده؛
5. رد stale refresh پیش از ایجاد Snapshot یتیم؛
6. ثبت API conflict با HTTP 409 و `refresh_conflict` بدون مصرف شماره نسخه؛
7. حفظ رفتار refresh بدون تغییر محتوا و refresh با محتوای تازه؛
8. ثابت‌ماندن Snapshot و Experimentهای نسخه‌های قبلی.

آزمون thread/process هم‌زمان واقعی و PostgreSQL در گیت نهایی TB2-024 تکرار می‌شود؛ تست SQLite این
مرحله rollback و compare-and-swap را پوشش می‌دهد، نه رفتار قفل ردیفی PostgreSQL را.
