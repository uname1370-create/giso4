# نگهبان خودکار (systemd) — استقرار سرویس‌های ساده‌چی/گیسو

این چهار فایل، هر سرویس را به‌صورت **مستقل** با systemd اجرا می‌کنند. اگر هر سرویس
کرش کند، systemd خودکار در ۵ ثانیه دوباره بالا می‌آورد؛ بعد از **ریبوت سرور** هم
خودکار اجرا می‌شود.

> ⚠️ **مهم:** یا از `python main.py` (لانچر دستی با watcher داخلی) استفاده کنید
> **یا** از systemd — هر دو را هم‌زمان اجرا نکنید (روی پورت/توکن تداخل می‌شود).
> روی سرور دائمی، systemd توصیه می‌شود.

## فایل‌ها

| فایل | سرویس | پورت/کار |
|---|---|---|
| `giso-web.service` | سایت گیسو | پورت 5001 |
| `giso-bot.service` | ربات گیسو | توکن از `GISO_BOT_TOKEN` یا bot.db |
| `edu-web.service` | سایت اصلی آموزش | پورت 5000 |
| `edu-bot.service` | ربات اصلی آموزش | — |

## پیش‌نیازها

1. پروژه روی سرور، مثلاً در `/home/rs2013/sadeghiai`
2. یک virtualenv با نصب requirements:
   ```bash
   python3 -m venv /home/rs2013/sadeghiai/venv
   /home/rs2013/sadeghiai/venv/bin/pip install -r /home/rs2013/sadeghiai/requirements.txt
   ```
3. در هر فایل `.service` این مقادیر را با مقادیر سرور خود تنظیم کنید:
   `User=`، `WorkingDirectory=`، مسیرهای `ExecStart=`/`PYTHONPATH=`
   (اگر مسیر پروژه‌چیز دیگری غیر از `/home/rs2013/sadeghiai` است).
4. وب‌سرورها (`giso-web.service` و `edu-web.service`) به‌جای Flask dev
   از **Waitress** استفاده می‌کنند (در `requirements.txt` است؛ threads=8 با
   fallback خودکار به `app.run` در صورت نبود). این یعنی ظرفیت بالاتر بدون
   تغییر کد/مسیرها؛ سرویس‌های `deploy/` و لانچر `main.py` هم نیاز به تغییر
   ندارند چون هر دو همین `python <app>.py` را اجرا می‌کنند.
4. برای `giso-web.service` کلید امن نشست را در فایل امن `sudo nano /etc/giso/web.env` بگذارید:
   ```bash
   SECRET_KEY=یک_رشته_تصادفی_بلند_و_امن
   # اختیاری (فقط اگر وب‌سرور به توکن ربات نیاز دارد):
   # GISO_BOT_TOKEN=توکن_واقعی_ربات
   ```
   سپس دسترسی فایل را فقط root کنید:
   ```bash
   sudo chmod 600 /etc/giso/web.env
   ```
   ⚠️ این فایل **باید قبل از start ساخته شود**: اگر `SECRET_KEY` تنظیم نباشد،
   `giso/config.py` در حالت production خطا می‌دهد و سرویس بالا نمی‌آید
   (`SECRET_KEY must be set in production`).
   🔒 چرا `EnvironmentFile` امن‌تر از `Environment=` inline است: راز در ریپو git
   نمی‌ماند، در `systemctl cat`/خروجی سرویس نمایش داده نمی‌شود، دسترسی‌اش با
   `chmod 600` محدود می‌شود و بدون تغییر فایل سرویس قابل چرخش است.
   📝 توجه: پروژه فعلاً از SQLite استفاده می‌کند (`giso/config.py`) و متغیر
   `DATABASE_URL` خوانده نمی‌شود؛ در این فایل فقط `SECRET_KEY` (و در صورت نیاز
   `GISO_BOT_TOKEN`) معتبر است.
5. برای `giso-bot.service` توکن را در فایل امن `sudo nano /etc/giso/bot.env` بگذارید:
   ```bash
   GISO_BOT_TOKEN=توکن_واقعی_ربات
   ```
   و مطمئن شوید دسترسی فایل فقط root باشد:
   ```bash
   sudo chmod 600 /etc/giso/bot.env
   ```
   (اگر فایل موجود نباشد، سرویس بدون خطا اجرا می‌شود و توکن از `giso_config` در
   bot.db خوانده می‌شود — اولویت همیشه `GISO_BOT_TOKEN` است.)
6. در production حتماً `FLASK_ENV=production` ست باشد (`deploy/giso-web.service`
   همین‌طور پیش‌فرض دارد): این باعث می‌شود `SESSION_COOKIE_SECURE=True` فعال شود
   (`giso/config.py:47-50`) و کوکی‌های نشست فقط روی HTTPS ارسال شوند.
   ⚠️ چون `FLASK_ENV=production` است، `SECRET_KEY` حتماً باید در `/etc/giso/web.env`
   تنظیم شود وگرنه سرویس طبق طراحی بالا نمی‌آید (`SECRET_KEY must be set in production`).

## فعال‌سازی (یک‌بار)

```bash
sudo cp deploy/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable giso-web giso-bot edu-web edu-bot
sudo systemctl start  giso-web giso-bot edu-web edu-bot
```

بررسی وضعیت:
```bash
systemctl status giso-web giso-bot edu-web edu-bot --no-pager
journalctl -u giso-bot -f          # لاگ زندهٔ ربات گیسو
```

## تست ری‌استارت خودکار

```bash
# شبیه‌سازی کرش ناگهانی سرویس:
sudo kill -9 $(systemctl show -p MainPID --value giso-bot)

# ۵ تا ۱۰ ثانیه صبر کنید، سپس:
sleep 8
systemctl is-active giso-bot          # باید active باشد (PID جدید)
journalctl -u giso-bot -n 15          # لاگ شروع دوباره
```

برای سایت‌ها:
```bash
sudo kill -9 $(pgrep -f "giso/app.py" | head -1); sleep 8
systemctl is-active giso-web          # active
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/   # 200/302
```

## تست ریبوت (در پنجرهٔ تعمیر)

```bash
sudo reboot
# بعد از بالا آمدن سرور:
systemctl is-active giso-web giso-bot edu-web edu-bot   # همه باید active باشند
```

## مدیریت

```bash
sudo systemctl restart giso-bot      # ری‌استارت دستی
sudo systemctl stop giso-web         # توقف
sudo systemctl disable edu-web       # غیرفعال کردن دائمی یک سرویس
```

## یادداشت معماری

- دو دیتابیس `giso/data/giso.db` و `bot_edu/data/bot.db` بین سرویس‌ها مشترک‌اند
  و هر دو سرویس گیسو و آموزش به آن‌ها دسترسی دارند (WAL + busy_timeout=15s).
- اگر bot.db موقتاً قفل باشد، گیسو کرش نمی‌کند؛ اتصال None برمی‌گرداند و از
  مسیر امن/کش ادامه می‌دهد.
- گیسو برای توکن ربات اول `GISO_BOT_TOKEN` را می‌خواند، بعد `giso_config` در bot.db.
