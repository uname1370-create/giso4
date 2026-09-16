# استقرار گیسو روی Ubuntu 24.04 (سرور ایران) — راهنمای گام‌به‌گام

> پیش‌فرض‌ها: دامنه `gisosadeghi.ir` روی IP سرور ست شده، کاربر `rs2013`،
> مسیر پروژه `/home/rs2013/sadeghiai`. اگر فرق دارد، در دستورات جایگزین کنید.
> همهٔ دستورات با `sudo` اجرا می‌شوند مگر گفته شود.

---

## گام ۱ — پکیج‌های سیستم (Python 3.12، Nginx، Certbot)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.12 python3.12-venv python3-pip \
                    nginx certbot python3-certbot-nginx \
                    git curl sqlite3
# ماژول brotli برای nginx (اختیاری — اگر نبود، brotli را در کانفیگ کامنت کنید)
sudo apt install -y libnginx-mod-brotli 2>/dev/null || echo "brotli: از سورس نصب کنید یا کامنت"
python3.12 --version   # باید Python 3.12.x چاپ کند
```

---

## گام ۲ — کلون پروژه + محیط مجازی + وابستگی‌ها

```bash
sudo mkdir -p /home/rs2013 && cd /home/rs2013
sudo git clone https://github.com/uname1370-create/Giso2.git sadeghiai
sudo chown -R rs2013:rs2013 /home/rs2013/sadeghiai
cd /home/rs2013/sadeghiai
python3.12 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
# تست سازگاری روی سرور (بیس‌لاین: ۴۶۸ پاس / ۶۲ شکست محیطی)
./venv/bin/pip install pytest
SECRET_KEY=test-only-key-32chars-minimum-abc ./venv/bin/python -m pytest -q giso/tests/ | tail -2
```

---

## گام ۳ — انتقال امن پوشهٔ `giso/data` (دیتابیس) از سرور قبلی

> ⚠️ دیتابیس در git نیست (gitignore). بدون این گام سایت با دیتابیس خالی بالا می‌آید.
> قبل از انتقال، روی سرور قدیم سرویس‌ها را نگه‌دارید تا فایل WAL یکدست کپی شود:

```bash
# ── روی سرور قبلی ──
cd /path/to/sadeghiai
# ۱) checkpoint برای یکدست‌سازی WAL:
sqlite3 giso/data/giso.db "PRAGMA wal_checkpoint(TRUNCATE);"
# ۲) بستهٔ امن (بدون لو رفتن در مسیرهای عمومی):
tar -czf /root/giso-data-$(date +%F).tar.gz giso/data/
# ۳) انتقال رمزگذاری‌شده ( scp روی SSH خودش رمزنگار است):
scp /root/giso-data-*.tar.gz rs2013@IP_سرور_جدید:/home/rs2013/

# ── روی سرور جدید ──
cd /home/rs2013/sadeghiai
tar -xzf /home/rs2013/giso-data-*.tar.gz     # giso/data/ را در پروژه باز می‌کند
rm /home/rs2013/giso-data-*.tar.gz           # پاک‌کردن آرشیو
sqlite3 giso/data/giso.db "PRAGMA integrity_check;"   # باید: ok
chown -R rs2013:rs2013 giso/data
```

---

## گام ۴ — فایل امن `/etc/giso/web.env`

```bash
sudo mkdir -p /etc/giso
sudo nano /etc/giso/web.env
```

محتوا (مقادیر واقعی را بگذارید):

```ini
# کلید نشست — حتماً رشتهٔ تصادفی بلند (security.py به کلید <۳۲ کاراکتر هشدار می‌دهد)
SECRET_KEY=OUTPUT_OF: openssl rand -hex 32

# Base URL سفارشی Gemini — ورکر کلودفلر (deploy/cloudflare-gemini-worker.js)
GEMINI_BASE_URL=https://sadeghiai.uname1370.workers.dev

# توکن ربات بله
GISO_BOT_TOKEN=توکن_واقعی_ربات_بله
```

```bash
sudo chmod 600 /etc/giso/web.env
sudo chown root:root /etc/giso/web.env
# کلید تصادفی: openssl rand -hex 32
```

---

## گام ۵ — سرویس‌های systemd (وب و ربات)

```bash
cd /home/rs2013/sadeghiai/deploy
# اگر کاربر/مسیر شما فرق دارد، User= و WorkingDirectory= و ExecStart= را ویرایش کنید:
sudo cp giso-web.service giso-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now giso-web giso-bot
systemctl status giso-web --no-pager | head -5   # باید active (running)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5001/   # باید 200
```

> ⚠️ طبق `deploy/README.md`: لانچر `python main.py` و systemd را **هم‌زمان** اجرا نکنید.
> اگر سیستم آموزشی (`web/` پورت 5000 و edu-bot) هم لازم است: `edu-web.service` و `edu-bot.service` را همین‌طور نصب کنید.

---

## گام ۶ — Nginx + HTTPS با certbot

```bash
cd /home/rs2013/sadeghiai/deploy
sudo cp nginx-giso.conf /etc/nginx/sites-available/giso
sudo ln -sf /etc/nginx/sites-available/giso /etc/nginx/sites-enabled/giso
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# گواهی Let's Encrypt (از ایران هم روی پورت ۸۰/۴۴۳ کار می‌کند):
sudo certbot --nginx -d gisosadeghi.ir -d www.gisosadeghi.ir \
     --redirect --agree-tos -m ایمیل_شما@example.com
# تمدید خودکار تست:
sudo certbot renew --dry-run
```

---

## گام ۷ — چک‌لیست تست نهایی و عیب‌یابی

**چک‌لیست (بعد از هر دو گام ۵ و ۶):**

```bash
curl -s -o /dev/null -w "home: %{http_code} (%{time_total}s)\n"        https://gisosadeghi.ir/
curl -s -o /dev/null -w "admin-redirect: %{http_code}\n"               https://gisosadeghi.ir/admin/
curl -s -o /dev/null -w "user-redirect: %{http_code}\n"                https://gisosadeghi.ir/dashboard
curl -s -o /dev/null -w "gzip: %{content_type}\n" -H "Accept-Encoding: gzip" https://gisosadeghi.ir/ -D - | grep -i content-encoding
curl -s -o /dev/null -w "static-cache: %{http_code}\n" -D - https://gisosadeghi.ir/static/css/style.css | grep -i cache-control
curl -s https://sadeghiai.uname1370.workers.dev/v1beta/__health        # باید: ok
systemctl is-active giso-web giso-bot                                  # هر دو: active
```

وارد پنل ادمین شوید → تب هوش مصنوعی → تست اتصال پروایدر gemini
(درخواست‌ها باید از ورکر عبور کنند؛ در لاگ‌ها `journalctl -u giso-web -f` خطای DNS/timeout به googleapis نباید باشد).

**عیب‌یابی سریع:**

| علامت | علت احتمالی | درمان |
|---|---|---|
| `502 Bad Gateway` | سرویس وب خوابیده | `systemctl status giso-web` + `journalctl -u giso-web -n 50` |
| صفحه لاگین کوکی نمی‌گیرد | HTTPS نیست ولی `FLASK_ENV=production` کوکی Secure می‌سازد (`giso/config.py:47-50`) | certbot را کامل کنید؛ موقتاً با `https://127.0.0.1` تست نکنید |
| چت AI کار نمی‌کند | ورکر یا کلید API | `curl https://sadeghiai.uname1370.workers.dev/v1beta/__health`؛ مقدار `GEMINI_BASE_URL` در `/etc/giso/web.env`؛ بعد از تغییر: `sudo systemctl restart giso-web giso-bot` |
| `database is locked` | کپی ناقص WAL یا دو پروسه هم‌زمان | فقط systemd اجرا باشد؛ `PRAGMA wal_checkpoint(TRUNCATE);` |
| ری‌استارت دستی از پنل کار نکرد | زیر systemd مکانیزم flag متفاوت است | `sudo systemctl restart giso-web` (flag در `giso/data/giso-restart.flag` برای لانچر main.py است) |
| ربات پیام نمی‌دهد | توکن/نتورک بله | `journalctl -u giso-bot -f`؛ تست `curl https://tapi.bale.ai/bot$GISO_BOT_TOKEN/getMe` |

**نکات نگهداری:**
- بکاپ روزانه: از پنل ادمین (ماژول backup) یا `sqlite3 giso/data/giso.db ".backup /backups/giso-$(date +%F).db"` در cron.
- لاگ‌ها: `journalctl -u giso-web -u giso-bot -f`
- به‌روزرسانی کد: `git pull` → `./venv/bin/pip install -r requirements.txt` → `sudo systemctl restart giso-web giso-bot`

## گام ۸ — PostgreSQL (دیتابیس اصلی پروداکشن)

معماری مصوب: **PG نویسندهٔ یگانه** (دو دیتابیس `giso_db` و `bot_edu_db` با کلید جدا) و SQLite فقط برای توسعه/تست لوکال. تا وقتی `GISO_DB_ENGINE` ست نشود، همه‌چیز مثل قبل روی SQLite است.

### ۸-۱) نصب و ساخت دیتابیس‌ها
```bash
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres psql <<'SQL'
CREATE USER giso_app WITH PASSWORD 'رمز۱';
CREATE USER bot_app  WITH PASSWORD 'رمز۲';
CREATE USER giso_backup WITH PASSWORD 'رمز۳';
CREATE DATABASE giso_db    OWNER giso_app;
CREATE DATABASE bot_edu_db OWNER bot_app;
SQL
```
PG به‌صورت پیش‌فرض فقط روی localhost گوش می‌دهد — هیچ پورتی در فایروال باز نکنید.

### ۸-۲) کلیدهای env در `/etc/giso/web.env`
```
GISO_DB_ENGINE=postgres
GISO_PG_DSN=postgresql://giso_app:رمز۱@127.0.0.1:5432/giso_db
BOT_EDU_PG_DSN=postgresql://bot_app:رمز۲@127.0.0.1:5432/bot_edu_db
```

### ۸-۳) مهاجرت داده (یک‌بار، قبل از ری‌استارت)
```bash
cd /opt/giso   # مسیر پروژه
./venv/bin/pip install psycopg2-binary
# مهاجرت با کاربر ادمین PG (برای کپی امن دادهٔ دارای FK):
sudo -u postgres env \
  GISO_PG_DSN="postgresql://postgres@/giso_db?host=/var/run/postgresql" \
  BOT_EDU_PG_DSN="postgresql://postgres@/bot_edu_db?host=/var/run/postgresql" \
  ./venv/bin/python -m giso.db_pg_tools --migrate-all
```
خروجی سالم = `🟢 راستی‌آزمایی تعداد — همهٔ جدول‌ها مطابقت دارند` برای هر دو دیتابیس.
اگر `🟡 NOT VALID` دیدید یعنی دادهٔ قدیمی یتیم داشته (چیزی حذف نمی‌شود؛ نوشتن جدید کنترل می‌شود).

### ۸-۴) بکاپ خودکار
```bash
sudo cp deploy/pg_backup.sh /usr/local/bin/giso_pg_backup.sh
sudo chmod +x /usr/local/bin/giso_pg_backup.sh
echo '127.0.0.1:5432:*:giso_backup:رمز۳' | sudo tee /var/lib/postgresql/.pgpass
sudo chmod 600 /var/lib/postgresql/.pgpass && sudo chown postgres /var/lib/postgresql/.pgpass
# cron ساعتی:
echo '15 * * * * root /usr/local/bin/giso_pg_backup.sh >> /var/log/giso_pg_backup.log 2>&1' | sudo tee /etc/cron.d/giso-pg-backup
```

### ۸-۵) ری‌استارت و بازگشت اضطراری
```bash
sudo systemctl restart giso-web giso-bot
```
بازگشت اضطراری به SQLite: فقط خط `GISO_DB_ENGINE` را از web.env حذف کنید و سرویس‌ها را ری‌استارت کنید (فایل‌های SQLite دست‌نخورده باقی مانده‌اند).
