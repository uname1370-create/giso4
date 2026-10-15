# راهنمای یک‌فایل: نصب محیط گیسو در VS Code و اجرای Cline با Gemini

ریشهٔ پروژه روی سیستم شما:
`C:\Users\Sadeghy\Desktop\giso 3`

همهٔ دستورها در **PowerShell** داخل پوشهٔ بالا اجرا می‌شوند.

---

## بخش ۱: پیش‌نیاز

1. **Python 3.11** (نسخه‌ای که پروژه با آن ساخته و تست شده). بررسی:
   ```powershell
   py -3.11 --version
   ```
   اگر پیدا نشد، Python 3.11 (64-bit) را از python.org نصب کنید و گزینهٔ **Add python.exe to PATH** را تیک بزنید.
2. **VS Code** با افزونه‌های **Python** (Microsoft) و **Cline**.
3. **کلید Gemini API** از Google AI Studio. این کلید را فقط در تنظیمات Cline وارد کنید، نه در هیچ فایلی.

---

## بخش ۲: ساخت محیط Python (.venv)

۱. VS Code را باز کنید: **File → Open Folder** و پوشهٔ `C:\Users\Sadeghy\Desktop\giso 3` را انتخاب کنید.
۲. ترمینال را باز کنید (Ctrl + `) و این دستورها را **به ترتیب** بزنید:

```powershell
cd "C:\Users\Sadeghy\Desktop\giso 3"
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

۳. نصب نیازهای اصلی پروژه:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

۴. نصب بخش landmarks برای ابرو و لب. **فایل `requirements-landmarks.txt` را مستقیم با `pip -r` نصب نکنید،** چون خط `mediapipe` داخلش وابستگی‌هایی می‌آورد که OpenCV اصلی را خراب می‌کند. به‌جایش این دو دستور را بزنید:

```powershell
.\.venv\Scripts\python.exe -m pip install "absl-py" "attrs>=19.1.0" "flatbuffers>=2.0" "matplotlib==3.8.4" "numpy<2" "opencv-python-headless==4.11.0.86" "protobuf>=4.25.3,<5"
.\.venv\Scripts\python.exe -m pip install --no-deps "mediapipe==0.10.21"
```

۵. بررسی نصب:

```powershell
.\.venv\Scripts\python.exe -c "import flask, cv2, mediapipe; print('OK', cv2.__version__, mediapipe.__version__)"
.\.venv\Scripts\python.exe -m pip show opencv-contrib-python
```

نتیجهٔ مورد انتظار: خط اول `OK` و نسخه‌ها را نشان می‌دهد؛ دستور دوم باید بگوید **Package(s) not found**. اگر پکیج contrib پیدا شد، نصب را متوقف کنید و این راهنما را اجرا نکنید.

۶. انتخاب interpreter در VS Code: **Ctrl + Shift + P → Python: Select Interpreter → `.venv`** (مسیر `.\.venv\Scripts\python.exe`).

> **اگر PowerShell اجازهٔ فعال‌سازی `.venv` را نداد:** این دستور را یک‌بار بزنید و دوباره تلاش کنید:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

---

## بخش ۳: اجرای برنامه و تست (اختیاری)

**تنظیم SECRET_KEY:** برنامه بدون این متغیر در حالت production اجرا نمی‌شود. مقدار را خودتان انتخاب کنید (رشتهٔ بلند و تصادفی) و در فایل ذخیره نکنید:

```powershell
$env:SECRET_KEY="یک-رشتهٔ-بلند-و-تصادفی-خودتان"
```

**اجرای سایت گیسو** (پورت 5001):

```powershell
.\.venv\Scripts\python.exe giso\app.py
```

آدرس: `http://127.0.0.1:5001`

**اجرای تست‌ها** (در همان ترمینال که `SECRET_KEY` تنظیم شده):

```powershell
.\.venv\Scripts\python.exe -m pytest giso\tests -q -p no:cacheprovider
```

کلیدهای provider (مثل Gemini) باید در `giso\data\.env` باشند. این فایل را هرگز به گیت یا کسی ندهید.

---

## بخش ۴: تنظیم Cline با Gemini

۱. در VS Code افزونهٔ **Cline** را نصب کنید.
۲. در Cline: **Settings** → **API Provider** را **Gemini** بگذارید و کلید API خودتان را وارد کنید.
۳. پوشهٔ پروژه باز باشد. فایل `satrtp.md` در ریشهٔ پروژه دستورهای ایجنت را دارد؛ Cline باید آن را اول بخواند.

---

## بخش ۵: متن آمادهٔ نصب برای Cline (کپی کنید و در چت Cline بچسبانید)

```text
Read satrtp.md in the project root first.

Task: set up the Python environment for this project on Windows.
Project root: C:\Users\Sadeghy\Desktop\giso 3

Rules:
- Use only the .venv in the project root. Run commands with .\.venv\Scripts\python.exe.
- Install only the packages listed in the steps below. Do not install anything else.
- Do not edit requirements.txt or requirements-landmarks.txt.
- Do not install opencv-contrib-python. If it appears in any output, stop and report.
- Do not write any API key, token or SECRET_KEY into any file. Do not print the contents of giso\data\.env.
- Do not start the web server and do not call any AI API.
- If a command fails, stop, show the full error, and wait for my instruction. Do not try alternative packages.

Steps:
1. Check that Python 3.11 is available: py -3.11 --version. If not, stop and report.
2. If .venv does not exist, create it: py -3.11 -m venv .venv
3. .\.venv\Scripts\python.exe -m pip install --upgrade pip
4. .\.venv\Scripts\python.exe -m pip install -r requirements.txt
5. .\.venv\Scripts\python.exe -m pip install "absl-py" "attrs>=19.1.0" "flatbuffers>=2.0" "matplotlib==3.8.4" "numpy<2" "opencv-python-headless==4.11.0.86" "protobuf>=4.25.3,<5"
6. .\.venv\Scripts\python.exe -m pip install --no-deps "mediapipe==0.10.21"
7. Verify: .\.venv\Scripts\python.exe -c "import flask, cv2, mediapipe; print(cv2.__version__, mediapipe.__version__)"
8. Verify: .\.venv\Scripts\python.exe -m pip show opencv-contrib-python   (must report "not found")
9. Run: .\.venv\Scripts\python.exe -m pip check   (report any warnings; do not fix them without asking)

Report to me in Persian: each step with PASS or FAIL, the installed versions of flask, opencv-python-headless, mediapipe and numpy, and the full output of any failure.
```

---

## بخش ۶: مشکل‌های رایج

| مشکل | راه‌حل |
|---|---|
| `py -3.11` پیدا نمی‌شود | Python 3.11 را نصب کنید؛ یا از `where python` مسیر درست را پیدا کنید |
| `Activate.ps1` اجرا نمی‌شود | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `cv2` خطای libGL می‌دهد | `opencv-contrib-python` نصب شده است. `pip uninstall -y opencv-contrib-python` و سپس `pip install --force-reinstall "opencv-python-headless==4.11.0.86"` |
| `RuntimeError: SECRET_KEY must be set` | متغیر `SECRET_KEY` را در همان ترمینال تنظیم کنید (بخش ۳) |
| `pip install` کند یا timeout | دوباره اجرا کنید؛ اگر شبکه قطع‌وصل دارد، کمی بعد تلاش کنید |

---

> **یادداشت:** پس از تأیید شما، فایل `requirements-landmarks.txt` اصلاح می‌شود (خط mediapipe حذف) تا دستور نصب خلاصه‌تر شود. تا آن زمان همین دستورهای بخش ۲ معتبر هستند.
