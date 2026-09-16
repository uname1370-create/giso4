"""
db.py — تعریف جدول‌های SQLite و مدیریت اتصال

وابستگی: stdlib + ai_brain (فقط برای re-export توابع AI).
ai_brain خودش هیچ چیزی را در سطح فایل از db import نمی‌کند (importها داخل
تابع‌اند)، پس زنجیرهٔ import حلقه نمی‌زند.
"""
import os
import sqlite3
import logging
import threading

logger = logging.getLogger(__name__)

_conn: sqlite3.Connection = None

# قفل نوشتن برای توابع AI (thread safety — مشابه config._lock)
_lock = threading.Lock()


from pathlib import Path
_DEFAULT_DB_PATH = str(Path(__file__).resolve().parent / "data" / "bot.db")

def get_conn() -> sqlite3.Connection:
    """برگرداندن اتصال فعال به دیتابیس."""
    if _conn is None:
        raise RuntimeError("دیتابیس مقداردهی نشده. ابتدا init_db() را صدا بزنید.")
    return _conn


def _close_global_conn():
    """بستن connection سراسری (برای عملیات restore که فایل را جایگزین می‌کند)."""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


def checkpoint_bot_db():
    """انتقال اطلاعات WAL به دیتابیس اصلی bot.db (پیش‌فرض)."""
    return checkpoint_db(_DEFAULT_DB_PATH)


def checkpoint_db(db_path=None):
    """
    انتقال اطلاعات WAL به دیتابیس اصلی.
    اول TRUNCATE (بهترین)؛ اگر به دلیل reader فعال busy بود، FULL را امتحان می‌کند.
    قبل از هر backup باید صدا زده بشه تا فایل .db کامل و قابل اتکا باشد.
    """
    if db_path is None:
        db_path = _DEFAULT_DB_PATH
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if result and int(result[0]) == 1:  # busy → reader فعال
                logger.warning(f"wal_checkpoint(TRUNCATE) busy ({db_path}); trying FULL")
                result = conn.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
                logger.info(f"wal_checkpoint(FULL) result: {result}")
            conn.commit()
        finally:
            conn.close()
        logger.info(f"checkpoint انجام شد: {db_path}")
        return True
    except Exception as e:
        logger.error(f"checkpoint error ({db_path}): {e}")
        return False


def auto_restore_bot_db(db_path=None):
    """
    اگر bot.db وجود نداشته باشد یا خالی باشد، از آخرین backup بازیابی کن.
    باید قبل از ساخت جدول‌ها (init_db) صدا زده بشه.
    """
    import shutil
    if db_path is None:
        db_path = _DEFAULT_DB_PATH
    db_path = str(db_path)

    # اگر دیتابیس هست و خالی نیست، کاری نکن
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        return False

    logger.warning("⚠️ bot.db وجود نداره یا خالیه! بررسی backup...")

    backup_dir = os.path.join(os.path.dirname(db_path), "backup")
    if not os.path.exists(backup_dir):
        logger.warning("پوشه backup نیست. دیتابیس جدید ساخته می‌شود.")
        return False

    bot_backups = sorted(
        [f for f in os.listdir(backup_dir)
         if f.startswith("bot_") and f.endswith(".db")],
        reverse=True,
    )
    if not bot_backups:
        logger.warning("هیچ backup bot.db پیدا نشد.")
        return False

    latest = os.path.join(backup_dir, bot_backups[0])
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        shutil.copy2(latest, db_path)
        logger.info(f"✅ bot.db از backup بازیابی شد: {bot_backups[0]}")
        return True
    except Exception as e:
        logger.error(f"خطا در بازیابی bot.db: {e}")
        return False


def auto_restore_giso_db(giso_db_path=None):
    """
    اگر giso.db وجود نداشته باشد یا خالی باشد، از آخرین backup بازیابی کن.
    باید قبل از init گیسو صدا زده بشه. در هر دو پوشه backup جستجو می‌کند
    (bot_edu/data/backup و giso/data/backup).
    """
    import shutil
    if giso_db_path is None:
        giso_db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "giso", "data", "giso.db",
        )
    giso_db = str(giso_db_path)

    # اگر دیتابیس هست و خالی نیست، کاری نکن
    if os.path.exists(giso_db) and os.path.getsize(giso_db) > 0:
        return False

    logger.warning("⚠️ giso.db وجود نداره یا خالیه! بررسی backup...")

    backup_dirs = [
        os.path.join(os.path.dirname(str(_DEFAULT_DB_PATH)), "backup"),  # bot_edu/data/backup
        os.path.join(os.path.dirname(giso_db), "backup"),                 # giso/data/backup
    ]

    for backup_dir in backup_dirs:
        if not os.path.exists(backup_dir):
            continue
        giso_backups = sorted(
            [f for f in os.listdir(backup_dir)
             if f.startswith("giso_") and f.endswith(".db")],
            reverse=True,
        )
        if giso_backups:
            latest = os.path.join(backup_dir, giso_backups[0])
            try:
                os.makedirs(os.path.dirname(giso_db), exist_ok=True)
                shutil.copy2(latest, giso_db)
                logger.info(f"✅ giso.db از backup بازیابی شد: {giso_backups[0]} (از {backup_dir})")
                return True
            except Exception as e:
                logger.error(f"خطا در بازیابی giso.db: {e}")

    logger.warning("هیچ backup giso.db پیدا نشد.")
    return False


def backup_bot_db_safe(destination_path):
    """
    backup ایمن bot.db با SQLite Backup API — کاملاً سازگار با WAL.
    این روش حتی با چند connection فعال، تمام اطلاعات (شامل WAL) را می‌گیرد.
    خروجی: (success: bool, message: str)
    """
    import os
    try:
        src_path = _DEFAULT_DB_PATH
        # قدم ۱: تلاش برای checkpoint (بهترین حالت)
        try:
            conn = sqlite3.connect(str(src_path))
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
            conn.close()
            logger.info("checkpoint قبل از backup موفق")
        except Exception as e:
            logger.warning(f"checkpoint قبل از backup ناموفق (ادامه می‌دهیم): {e}")

        # قدم ۲: backup با Backup API
        src = sqlite3.connect(str(src_path))
        dst = sqlite3.connect(str(destination_path))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()

        # قدم ۳: verify integrity
        verify = sqlite3.connect(str(destination_path))
        result = verify.execute("PRAGMA integrity_check").fetchone()
        verify.close()
        if not result or str(result[0]).lower() != 'ok':
            try:
                os.remove(str(destination_path))
            except Exception:
                pass
            return False, f"integrity check ناموفق: {result}"

        # قدم ۴: چک جداول ضروری
        verify = sqlite3.connect(str(destination_path))
        tables = [t[0] for t in verify.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        verify.close()
        required = ['users', 'settings']
        missing = [t for t in required if t not in tables]
        if missing:
            try:
                os.remove(str(destination_path))
            except Exception:
                pass
            return False, f"جداول ضروری موجود نیستند: {missing}"

        logger.info(f"backup کامل و verified: {destination_path}")
        return True, "backup موفق"
    except Exception as e:
        logger.error(f"backup_bot_db_safe error: {e}")
        return False, str(e)


def restore_bot_db_safe(source_path):
    """
    restore کامل bot.db از فایل بکاپ.
    شامل: verify مبدا، safety backup، checkpoint، overwrite، حذف WAL/SHM،
    verify جدید، reload کامل memory.
    خروجی: (success: bool, message: str)
    """
    import os
    import shutil
    import time as _time
    from datetime import datetime
    try:
        src_path = _DEFAULT_DB_PATH

        # قدم ۱: verify فایل مبدا
        try:
            check = sqlite3.connect(str(source_path))
            result = check.execute("PRAGMA integrity_check").fetchone()
            check.close()
            if not result or str(result[0]).lower() != 'ok':
                return False, f"فایل مبدا خراب است: {result[0]}"
        except Exception as e:
            return False, f"فایل مبدا قابل خواندن نیست: {e}"

        # قدم ۲: safety backup از bot.db فعلی
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_path = os.path.join(os.path.dirname(src_path), f"bot_prerestore_{timestamp}.db")
        try:
            src = sqlite3.connect(str(src_path))
            dst = sqlite3.connect(str(safety_path))
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
            logger.info(f"safety backup: {safety_path}")
        except Exception as e:
            return False, f"ساخت safety backup ناموفق: {e}"

        # قدم ۳: checkpoint و بستن connection ها
        try:
            conn = sqlite3.connect(str(src_path))
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"checkpoint قبل از restore: {e}")

        # قدم ۴: overwrite bot.db + حذف WAL/SHM با محافظت در برابر قفل ویندوز
        try:
            # بستن connection سراسری تا onode کهنه با فایل جدید تداخل نکند
            _close_global_conn()

            # ۰٫۵ ثانیه صبر تا ویندوز قفل روی WAL/SHM را رها کند (رفع WinError 32)
            _time.sleep(0.5)

            # تلاش برای dispose کردن engine/web (اگه در دسترس بود)
            try:
                import sys
                if 'web.app' in sys.modules:
                    _web_mod = sys.modules['web.app']
                    if hasattr(_web_mod, 'db') and hasattr(_web_mod.db, 'engine'):
                        _web_mod.db.engine.dispose()
                        logger.info("web engine dispose شد")
            except Exception as _we:
                logger.debug(f"web engine dispose skipped: {_we}")

            shutil.copy2(str(source_path), src_path)
            wal_path = src_path + "-wal"
            shm_path = src_path + "-shm"
            for p in (wal_path, shm_path):
                if os.path.exists(p):
                    # حذف با تلاش مکرر — در ویندوز قفل ممکن است چند لحظه بماند
                    for retry in range(5):
                        try:
                            os.remove(p)
                            logger.info(f"حذف: {p}")
                            break
                        except (OSError, PermissionError) as e:
                            if retry < 4:
                                _time.sleep(0.3)
                            else:
                                # اگه بعد از ۵ تلاش هم fail شد، لاگ بزن ولی ادامه بده
                                logger.warning(f"حذف {p} ناموفق (ادامه): {e}")
        except Exception as e:
            try:
                shutil.copy2(str(safety_path), src_path)
                return False, f"restore ناموفق، rollback انجام شد: {e}"
            except Exception as e2:
                return False, f"restore ناموفق و rollback هم شکست خورد: {e}, {e2}"

        # قدم ۵: verify DB جدید
        try:
            check = sqlite3.connect(str(src_path))
            result = check.execute("PRAGMA integrity_check").fetchone()
            check.close()
            if not result or str(result[0]).lower() != 'ok':
                shutil.copy2(str(safety_path), src_path)
                return False, f"DB جدید خراب است، rollback شد: {result[0]}"
        except Exception as e:
            try:
                shutil.copy2(str(safety_path), src_path)
            except Exception:
                pass
            return False, f"verify DB جدید ناموفق، rollback شد: {e}"

        # قدم ۶: reload کامل memory + بازسازی connection سراسری
        try:
            init_db(_DEFAULT_DB_PATH)
        except Exception as e:
            logger.warning(f"re-init db بعد از restore: {e}")
        try:
            from bot_edu.config import reload_all_from_db
            reload_all_from_db()
        except Exception as e:
            logger.warning(f"reload memory ناموفق (نیاز به ریستارت): {e}")

        logger.info("restore کامل موفق")
        return True, "restore موفق - پیشنهاد می‌شود ربات ریستارت شود"
    except Exception as e:
        logger.error(f"restore_bot_db_safe error: {e}")
        return False, str(e)


def _pg_conn_or_none():
    """اگر env روی PostgreSQL باشد اتصال PG (همان API sqlite3) می‌سازد، وگرنه None.

    import به‌صورت resilient: هم از پکیج giso (سایت) و هم با افزودن ریشهٔ repo
    به sys.path در اجرای flat خودِ ربات.
    """
    try:
        if os.environ.get("GISO_DB_ENGINE", "").strip().lower() not in ("postgres", "postgresql"):
            return None
        dsn = (os.environ.get("BOT_EDU_PG_DSN", "") or "").strip()
        if not dsn:
            return None
        try:
            from giso.db_engine import PgConn
        except ImportError:
            import sys as _sys
            _root = str(Path(__file__).resolve().parent.parent)
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            from giso.db_engine import PgConn
        return PgConn(dsn)
    except Exception:
        return None


def init_db(db_path: str = _DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    ساخت یا باز کردن دیتابیس SQLite، اعمال PRAGMA بهینه‌سازی و ایجاد جدول‌ها.
    باید قبل از setup_data() و قبل از شروع polling صدا زده شود.

    با GISO_DB_ENGINE=postgres و BOT_EDU_PG_DSN، اتصال PostgreSQL با همان API
    برمی‌گردد (schema از قبل با giso.db_pg_tools روی bot_edu_db ساخته شده است).
    """
    global _conn
    _pg = _pg_conn_or_none()
    if _pg is not None:
        _conn = _pg
        return _conn
    _BOT_EDU_DIR = Path(__file__).resolve().parent
    if not os.path.isabs(db_path):
        db_path = str((_BOT_EDU_DIR / db_path).resolve())

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    _conn = sqlite3.connect(db_path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row

    # بهینه‌سازی — WAL: خواندن و نوشتن همزمان بهتر می‌شود
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA synchronous=NORMAL")
    _conn.execute("PRAGMA foreign_keys=ON")

    _create_tables(_conn)
    _migrate_columns(_conn)

    # جدول‌های «مغز هوش مصنوعی» (ai_providers و ai_checks_log)
    # پس از بازآرایی، تعریف این جدول‌ها در ai_brain.py است.
    try:
        from ai_brain import init_ai_tables as _init_brain_tables
        _init_brain_tables(_conn)
    except Exception as e:
        logger.warning(f"جدول‌های مغز هوش مصنوعی ساخته نشد: {e}")

    # جدول‌های ماژول «یار هوشمند شغلی» (ai_mentor)
    # import داخل تابع انجام می‌شود تا زنجیرهٔ import ماژول‌های سطح‌بالا نشکند:
    # ai_mentor.ai_db خودش db را import می‌کند، پس import سطح فایل حلقه می‌ساخت.
    try:
        from ai_mentor.ai_db import (
            init_ai_tables as _init_mentor_tables,
            init_chat_history_table as _init_mentor_chat,
            init_model_routing_table as _init_mentor_routing,
            init_payment_tables as _init_mentor_payment,
            init_phase3_tables as _init_mentor_phase3,
            init_phase4_tables as _init_mentor_phase4,
            init_trend_history_table as _init_mentor_trend_hist,
            init_user_profiles_table as _init_mentor_profiles,
        )
        _init_mentor_tables(_conn)
        _init_mentor_profiles(_conn)
        _init_mentor_payment(_conn)
        _init_mentor_routing(_conn)
        _init_mentor_chat(_conn)
        _init_mentor_trend_hist(_conn)
        _init_mentor_phase3(_conn)
        _init_mentor_phase4(_conn)
    except Exception as e:
        # نبود یا خطای این ماژول نباید جلوی بالا آمدن ربات را بگیرد
        logger.warning(f"جدول‌های یار هوشمند ساخته نشد: {e}")

    # جدول‌های مدیریت ربات گیسو
    try:
        from giso_admin import init_giso_tables
        init_giso_tables(_conn)
    except Exception as e:
        logger.warning(f"جدول‌های گیسو ساخته نشد: {e}")

    logger.info(f"✅ دیتابیس SQLite آماده است: {db_path}")
    return _conn


def _migrate_columns(conn: sqlite3.Connection) -> None:
    """اضافه کردن ستون‌های جدید به جداول قدیمی (migration ایمن)."""
    migrations = [
        ("cash_sale_settings", "display_place", "TEXT DEFAULT 'course'"),
        ("cash_sale_settings", "card_number",   "TEXT DEFAULT ''"),
        ("cash_sale_settings", "card_holder",   "TEXT DEFAULT ''"),
        ("cash_sale_settings", "bank_name",     "TEXT DEFAULT ''"),
        ("users",              "ban_until",     "INTEGER DEFAULT 0"),
        ("users",              "phone",         "TEXT DEFAULT ''"),
        ("platform_links",     "last_active",   "INTEGER DEFAULT 0"),
        ("platform_links",     "interactions",  "INTEGER DEFAULT 0"),
        ("tickets",            "platform",      "TEXT DEFAULT 'bale'"),
        ("tickets",            "chat_id",       "TEXT DEFAULT ''"),
        ("tickets",            "canonical_user_id", "INTEGER DEFAULT 0"),
        ("cash_sale_requests", "platform",      "TEXT DEFAULT 'bale'"),
        ("cash_sale_requests", "chat_id",       "TEXT DEFAULT ''"),
        ("cash_sale_requests", "canonical_user_id", "INTEGER DEFAULT 0"),
    ]
    for table, col, col_def in migrations:
        try:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if col not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
                conn.commit()
                logger.info(f"Migration: ستون {col} به {table} اضافه شد.")
        except Exception as e:
            logger.warning(f"Migration {table}.{col}: {e}")


def _create_tables(conn: sqlite3.Connection) -> None:
    """ساخت همه جدول‌ها و ایندکس‌ها (اگر از قبل وجود نداشتند)."""
    conn.executescript("""
-- ================= هسته اصلی =================

CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY,
    first_name     TEXT    DEFAULT '',
    username       TEXT    DEFAULT '',
    joined         INTEGER DEFAULT 0,
    last_active    INTEGER DEFAULT 0,
    points         INTEGER DEFAULT 0,
    xp             INTEGER DEFAULT 0,
    credits        INTEGER DEFAULT 0,
    referrer       INTEGER,
    level_announced INTEGER DEFAULT 0,
    pending_level_up TEXT,
    is_banned      INTEGER DEFAULT 0,
    is_muted       INTEGER DEFAULT 0,
    mute_until     INTEGER DEFAULT 0,
    phone          TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);

CREATE TABLE IF NOT EXISTS referrals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id INTEGER NOT NULL,
    referred_id INTEGER NOT NULL,
    time        INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON referrals(referrer_id);

CREATE TABLE IF NOT EXISTS completed_missions (
    user_id    INTEGER NOT NULL,
    mission_id TEXT    NOT NULL,
    PRIMARY KEY (user_id, mission_id)
);
CREATE INDEX IF NOT EXISTS idx_completed_missions_user_id ON completed_missions(user_id);

CREATE TABLE IF NOT EXISTS credits_paid (
    user_id   INTEGER NOT NULL,
    scope_key TEXT    NOT NULL,
    PRIMARY KEY (user_id, scope_key)
);
CREATE INDEX IF NOT EXISTS idx_credits_paid_user_id ON credits_paid(user_id);

CREATE TABLE IF NOT EXISTS courses (
    course_id               TEXT    PRIMARY KEY,
    title                   TEXT    DEFAULT '',
    description             TEXT    DEFAULT '',
    required_joins          TEXT    DEFAULT '[]',
    referral_required       INTEGER DEFAULT 0,
    referral_required_set_at INTEGER,
    required_credits        INTEGER DEFAULT 0,
    survey_enabled          INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS lessons (
    lid                     TEXT    PRIMARY KEY,
    course_id               TEXT    NOT NULL,
    position                INTEGER DEFAULT 0,
    title                   TEXT    DEFAULT '',
    type                    TEXT    DEFAULT '',
    content                 TEXT    DEFAULT '',
    file_id                 TEXT    DEFAULT '',
    caption                 TEXT    DEFAULT '',
    source_chat_id          INTEGER,
    source_message_id       INTEGER,
    required_joins          TEXT    DEFAULT '[]',
    referral_required       INTEGER DEFAULT 0,
    referral_required_set_at INTEGER,
    required_credits        INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_lessons_course_id ON lessons(course_id);

CREATE TABLE IF NOT EXISTS progress (
    user_id      INTEGER NOT NULL,
    lid          TEXT    NOT NULL,
    completed_at INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, lid)
);
CREATE INDEX IF NOT EXISTS idx_progress_user_id ON progress(user_id);
CREATE INDEX IF NOT EXISTS idx_progress_lid      ON progress(lid);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);

-- ================= قابلیت‌های فعلی =================

CREATE TABLE IF NOT EXISTS missions (
    mission_id     TEXT    PRIMARY KEY,
    title          TEXT    DEFAULT '',
    description    TEXT    DEFAULT '',
    type           TEXT    DEFAULT '',
    content        TEXT    DEFAULT '',
    file_id        TEXT    DEFAULT '',
    caption        TEXT    DEFAULT '',
    xp_reward      INTEGER DEFAULT 0,
    credits_reward INTEGER DEFAULT 0,
    active         INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS shop_items (
    item_id     TEXT    PRIMARY KEY,
    title       TEXT    DEFAULT '',
    description TEXT    DEFAULT '',
    price       INTEGER DEFAULT 0,
    kind        TEXT    DEFAULT '',
    content     TEXT    DEFAULT '',
    active      INTEGER DEFAULT 1,
    stock       INTEGER,
    repeatable  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS purchases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    item_id      TEXT    NOT NULL,
    purchased_at INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id);

CREATE TABLE IF NOT EXISTS survey_votes (
    user_id   INTEGER NOT NULL,
    course_id TEXT    NOT NULL,
    vote      TEXT    DEFAULT '',
    time      INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, course_id)
);
CREATE INDEX IF NOT EXISTS idx_survey_votes_user_id ON survey_votes(user_id);

CREATE TABLE IF NOT EXISTS tickets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    user_name  TEXT    DEFAULT '',
    username   TEXT    DEFAULT '',
    text       TEXT    DEFAULT '',
    time       INTEGER DEFAULT 0,
    replied    INTEGER DEFAULT 0,
    reply_text TEXT    DEFAULT '',
    platform   TEXT    DEFAULT 'bale',
    chat_id    TEXT    DEFAULT '',
    canonical_user_id INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bot_commands (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger       TEXT    DEFAULT '',
    active        INTEGER DEFAULT 1,
    admin_only    INTEGER DEFAULT 0,
    scope         TEXT    DEFAULT 'both',
    match_type    TEXT    DEFAULT 'exact',
    command_type  TEXT    DEFAULT 'text_reply',
    response_text TEXT    DEFAULT '',
    action_name   TEXT    DEFAULT ''
);

-- ================= قابلیت‌های جدید =================

-- سیستم دسترسی بخش‌ها بر اساس XP/اعتبار/سطح/رتبه
CREATE TABLE IF NOT EXISTS feature_access (
    feature_key TEXT    PRIMARY KEY,
    min_xp      INTEGER DEFAULT 0,
    min_credits INTEGER DEFAULT 0,
    min_level   INTEGER DEFAULT 0,
    min_edu_rank INTEGER DEFAULT 0
);

-- [مشکل 3] محدودیت اختصاصی بخش‌ها برای هر کاربر
CREATE TABLE IF NOT EXISTS user_feature_restrictions (
    user_id     INTEGER NOT NULL,
    feature_key TEXT    NOT NULL,
    is_blocked  INTEGER DEFAULT 1,
    until_ts    INTEGER DEFAULT 0,
    note        TEXT    DEFAULT '',
    PRIMARY KEY (user_id, feature_key)
);
CREATE INDEX IF NOT EXISTS idx_ufr_user_id ON user_feature_restrictions(user_id);

-- [مشکل 5] درخواست‌های فروش نقدی دوره — ستون‌های کامل
CREATE TABLE IF NOT EXISTS cash_sale_requests (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    user_name      TEXT    DEFAULT '',
    username       TEXT    DEFAULT '',
    course_id      TEXT    DEFAULT '',
    course_title   TEXT    DEFAULT '',
    lesson_id      TEXT    DEFAULT '',
    lesson_title   TEXT    DEFAULT '',
    target_type    TEXT    DEFAULT 'course',
    amount         INTEGER DEFAULT 0,
    payment_method TEXT    DEFAULT '',
    fiche_file_id  TEXT    DEFAULT '',
    status         TEXT    DEFAULT 'pending',
    requested_at   INTEGER DEFAULT 0,
    reviewed_at    INTEGER DEFAULT 0,
    admin_note     TEXT    DEFAULT '',
    platform       TEXT    DEFAULT 'bale',
    chat_id        TEXT    DEFAULT '',
    canonical_user_id INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cash_sale_user_id ON cash_sale_requests(user_id);

-- [مشکل 5] تنظیمات فروش نقدی برای دوره/سرفصل
CREATE TABLE IF NOT EXISTS cash_sale_settings (
    target_type    TEXT    NOT NULL,
    target_id      TEXT    NOT NULL,
    enabled        INTEGER DEFAULT 0,
    amount         INTEGER DEFAULT 0,
    payment_method TEXT    DEFAULT '',
    display_note   TEXT    DEFAULT '',
    display_place  TEXT    DEFAULT 'course',
    card_number    TEXT    DEFAULT '',
    card_holder    TEXT    DEFAULT '',
    bank_name      TEXT    DEFAULT '',
    PRIMARY KEY (target_type, target_id)
);

-- ================= چندپلتفرمی (Final Stage) =================

-- نگاشت کاربر اصلی (canonical = شناسه بله) به شناسه‌اش در پلتفرم‌های دیگر
CREATE TABLE IF NOT EXISTS platform_links (
    platform         TEXT    NOT NULL,
    platform_user_id TEXT    NOT NULL,
    user_id          INTEGER NOT NULL,
    connected_at     INTEGER DEFAULT 0,
    via              TEXT    DEFAULT 'link',
    last_active      INTEGER DEFAULT 0,
    interactions     INTEGER DEFAULT 0,
    PRIMARY KEY (platform, platform_user_id)
);
CREATE INDEX IF NOT EXISTS idx_platform_links_user_id ON platform_links(user_id);

-- کدهای یک‌بارمصرف اتصال کاربر به پلتفرم دیگر
CREATE TABLE IF NOT EXISTS link_codes (
    code        TEXT    PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    platform    TEXT    NOT NULL,
    mission_id  TEXT    DEFAULT '',
    created_at  INTEGER DEFAULT 0,
    expires_at  INTEGER DEFAULT 0,
    used        INTEGER DEFAULT 0,
    used_at     INTEGER DEFAULT 0,
    used_by     TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_link_codes_user_id ON link_codes(user_id);

-- لینک‌های یک‌بارمصرف ادمینی برای هر پلتفرم
CREATE TABLE IF NOT EXISTS admin_link_codes (
    code        TEXT    PRIMARY KEY,
    platform    TEXT    NOT NULL,
    created_by  INTEGER DEFAULT 0,
    created_at  INTEGER DEFAULT 0,
    expires_at  INTEGER DEFAULT 0,
    used        INTEGER DEFAULT 0,
    used_at     INTEGER DEFAULT 0,
    used_by     TEXT    DEFAULT ''
);

-- ادمین‌های ثبت‌شده هر پلتفرم
CREATE TABLE IF NOT EXISTS platform_admins (
    platform         TEXT    NOT NULL,
    platform_user_id TEXT    NOT NULL,
    user_id          INTEGER DEFAULT 0,
    added_at         INTEGER DEFAULT 0,
    PRIMARY KEY (platform, platform_user_id)
);
CREATE INDEX IF NOT EXISTS idx_platform_admins_user ON platform_admins(user_id);

-- گروه‌ها/کانال‌هایی که ربات در آن‌ها حضور دارد (برای ارسال گروهی مرکز پیام‌رسانی)
CREATE TABLE IF NOT EXISTS bot_groups (
    platform   TEXT    NOT NULL,
    chat_id    TEXT    NOT NULL,
    title      TEXT    DEFAULT '',
    chat_type  TEXT    DEFAULT 'group',
    added_at   INTEGER DEFAULT 0,
    last_seen  INTEGER DEFAULT 0,
    PRIMARY KEY (platform, chat_id)
);
CREATE INDEX IF NOT EXISTS idx_bot_groups_platform ON bot_groups(platform);

-- گزارش تحویل مرکز پیام‌رسانی (ماندگار بعد از ری‌استارت)
CREATE TABLE IF NOT EXISTS delivery_reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           INTEGER DEFAULT 0,
    route        TEXT    DEFAULT '',
    route_label  TEXT    DEFAULT '',
    dest         TEXT    DEFAULT '',
    dest_label   TEXT    DEFAULT '',
    mtype        TEXT    DEFAULT '',
    mtype_fa     TEXT    DEFAULT '',
    sent         INTEGER DEFAULT 0,
    failed       INTEGER DEFAULT 0,
    total        INTEGER DEFAULT 0,
    per_platform TEXT    DEFAULT '{}',
    errors       TEXT    DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_delivery_reports_ts ON delivery_reports(ts);

-- لاگ حذف کاربران از پنل ادمین سایت/ربات آموزشی (بدون ذخیره هش رمز یا پاسخ امنیتی)
CREATE TABLE IF NOT EXISTS user_deletion_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deleted_user_id INTEGER DEFAULT 0,
    deleted_phone TEXT DEFAULT '',
    deleted_first_name TEXT DEFAULT '',
    deleted_username TEXT DEFAULT '',
    deleted_by_user_id INTEGER DEFAULT 0,
    deleted_by_phone TEXT DEFAULT '',
    mode TEXT DEFAULT 'single_user_id',
    include_admins INTEGER DEFAULT 0,
    affected_counts_json TEXT DEFAULT '{}',
    snapshot_json TEXT DEFAULT '{}',
    created_at INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_user_deletion_logs_user ON user_deletion_logs(deleted_user_id);
CREATE INDEX IF NOT EXISTS idx_user_deletion_logs_created ON user_deletion_logs(created_at);

-- جدول‌های هوش مصنوعی به ai_brain.init_ai_tables() منتقل شدند.
""")

    # مقادیر پیش‌فرض settings
    conn.execute("""
        INSERT INTO settings(key, value) VALUES
        ('global_required_joins', '[]'),
        ('global_required_referrals', '0'),
        ('global_required_credits', '0'),
        ('telegram_token', ''),
        ('telegram_enabled', '0'),
        ('telegram_username', ''),
        ('site_maintenance', 'off'),
        ('giso_maintenance', 'off')
        ON CONFLICT DO NOTHING
        -- منسوخ: کلیدهای rubika_* و eitaa_* در دور هفتم حذف شدند.
        -- ردیف‌های قدیمی در دیتابیس‌های موجود بی‌ضررند و خوانده نمی‌شوند.""")
    conn.commit()
    logger.debug("جدول‌های دیتابیس ایجاد شدند.")


# ========================= هوش مصنوعی — دسترسی دیتابیس ========================
# ⚠️ بازآرایی: پیاده‌سازی این توابع به ai_brain.py منتقل شد تا «مغز هوش
# مصنوعی» در یک فایل متمرکز باشد. نام‌ها عیناً از اینجا دوباره export
# می‌شوند، پس کدهای موجود مثل `from db import get_ai_provider` بدون هیچ
# تغییری کار می‌کنند.
from ai_brain import (           # noqa: E402
    _AI_EDITABLE,
    _ai_now,
    add_ai_provider,
    ai_provider_count,
    delete_ai_provider,
    get_ai_provider,
    init_ai_tables,
    list_ai_providers,
    save_ai_check_result,
    toggle_ai_provider,
    update_ai_provider_field,
)

# فهرست re-exportهای AI — هم مستندسازی، هم اعلام «استفاده‌شده» به pyflakes.
__all_ai__ = (
    init_ai_tables, _ai_now, get_ai_provider, list_ai_providers,
    add_ai_provider, delete_ai_provider, toggle_ai_provider,
    update_ai_provider_field, save_ai_check_result, ai_provider_count,
    _AI_EDITABLE,
)
# Phase 10.4 Bot DB sync verified (giso_admins init at 676fa6b)
