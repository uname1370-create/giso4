# گزارش Load Test — آمادگی Production (سناریوی Master Guide §۱۳)

> محیط اجرا: sandbox توسعه (SQLite + تک‌فرایند in-process، بدون gunicorn/PG).
> اعداد Production با gunicorn چندورکر + PostgreSQL بهتر از این اعداد خواهد بود؛
> این گزارش سقف پایین (worst-case) را می‌سنجد. تاریخ: 2026-09-04.

## سناریوها و نتایج اندازه‌گیری‌شده

| سناریو | همروندی | تعداد درخواست | RPS | p50 | p95 | خطا | classificação |
|---|---|---|---|---|---|---|---|
| S1 سایت عمومی `GET /` | 20 thread | 200 | 9.6 | 1723ms | 3536ms | 0 | **Needs Optimization** |
| S2 صفحات سبک `GET /login` | 15 thread | 150 | 10.8 | 1116ms | 1989ms | 0 | **Needs Optimization** |
| S3 ستون وضعیت (کش ۲۰ث) | 8 thread | 40 | 354 | 2ms | 91ms | 0 | **Safe** |
| S4 درین صف broadcast (۵ delivery سایت) | worker تک‌رشته | 5 | ~10 msg/s | ~104ms/msg | — | 0 | **Safe** |

## تحلیل

- **Safe:** مسیرهای دارای کش (S3) و صف پس‌زمینه (S4) زیر بار سالم‌اند؛ هیچ 5xx در هیچ سناریو ثبت نشد.
- **Needs Optimization:** صفحه اصلی و صفحات سبک در sqlite تک‌فرایند زیر ۲۰ رشته کند می‌شوند (p95 تا ۳.۵ ثانیه). علت اصلی: قفل نوشتن SQLite + رندر سرور بدون کش HTML عمومی.
- **Critical Risk:** یافت نشد. خرابی AI/Bale طبق طراحی (فاز D) سایت را Down نمی‌کند؛ ستون وضعیت در sandbox بدون توکن، قرمز/زرد نشان داد و سرویس ادامه داد.

## توصیه‌های Production (به ترتیب اولویت)

1. **Gunicorn ≥ 4 worker** (sync یا gthread) طبق `deploy/UBUNTU_SETUP.md` — موازی‌سازی رندر و حذف bottleneck تک‌فرایند.
2. **PostgreSQL** (هم اکنون موتور تولید است) — حذف قفل نوشتن SQLite که عامل اصلی p95 سناریو S1/S2 است.
3. کش `Cache-Control: public, max-age=604800` برای `/static/` فعال است؛ برای صفحه اصلی در صورت نیاز، کش کوتاه‌مدت (۳۰–۶۰ ثانیه) در reverse proxy اضافه شود.
4. gzip فعال است (`giso/perf.py`)؛ HTTP/2 و fsock fastcgi buffers در nginx توصیه می‌شود.
5. صف broadcast: batch فعلی ۵تایی با 0.1s تأخیر ≈ 10 msg/s؛ برای کمپین‌های بزرگ‌تر، افزایش `limit` در `process_batch` یا worker دوم پس از پایش توصیه می‌شود.
6. مانیتورینگ: endpoint سبک `/admin/super-assistant/health` (کش ۲۰ث) برای health check خارجی مناسب است (timeout ≤ 3s).

## نتیجه نهایی

| حوزه | وضعیت |
|---|---|
| چند کاربر همزمان سایت | Needs Optimization → با gunicorn+PG برطرف می‌شود |
| درخواست AI موازی | Safe (کش + fallback؛ بدون crash) |
| فعالیت همزمان بات | Safe (send_bot_push_best-effort، صف مجزا) |
| ارسال Notification انبوه | Safe (خارج از HTTP، batch+retry) |
