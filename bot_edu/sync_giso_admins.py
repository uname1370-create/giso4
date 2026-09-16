# P0 bot_db full sync — idempotent, safe, no data loss
# Reads admin/super users from giso.db and inserts into bot_edu/data/bot.db giso_admins if missing
import sqlite3, os, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# giso DB
GISO_DB = os.path.join(BASE, "giso", "data", "giso.db")
BOT_DB = os.path.join(BASE, "bot_edu", "data", "bot.db")

def sync():
    # Do NOT drop; only insert missing
    g_conn = sqlite3.connect(GISO_DB)
    b_conn = sqlite3.connect(BOT_DB)
    try:
        admins = g_conn.execute("SELECT phone, bale_id FROM giso_users WHERE is_admin = 1 OR (bale_id IS NOT NULL AND bale_id != '')").fetchall()
        for phone, bale_id in admins:
            # Normalize if needed; use INSERT OR IGNORE to avoid duplicates
            b_conn.execute("INSERT INTO giso_admins (phone, bale_id, added_by, added_at) VALUES (?, ?, 1, datetime('now')) ON CONFLICT DO NOTHING", (str(phone or ''), str(bale_id or '')) )
        b_conn.commit()
        inserted = b_conn.total_changes  # approximate
        print(f"SYNC DONE — admins checked; insertions approximate: {inserted}")
    finally:
        g_conn.close(); b_conn.close()

if __name__ == "__main__":
    sync()
