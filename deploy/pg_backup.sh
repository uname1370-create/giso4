#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# بکاپ خودکار PostgreSQL گیسو (سناریوی مصوب: PG نویسندهٔ یگانه، بکاپ pg_dump)
#
# نصب روی سرور:
#   sudo cp deploy/pg_backup.sh /usr/local/bin/giso_pg_backup.sh
#   sudo chmod +x /usr/local/bin/giso_pg_backup.sh
#   # رمز کاربر بکاپ را در /var/lib/postgresql/.pgpass یا ~/.pgpass کاربر cron بگذارید:
#   #   127.0.0.1:5432:*:giso_backup:رمز      (chmod 600)
#
# cron ساعتی (دقیقهٔ ۱۵ هر ساعت):
#   15 * * * * root /usr/local/bin/giso_pg_backup.sh >> /var/log/giso_pg_backup.log 2>&1
#
# بازیابی یک دیتابیس:
#   pg_restore -U giso_app -d giso_db --clean --if-exists /var/backups/giso/giso_db-....dump
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

BACKUP_DIR="${GISO_BACKUP_DIR:-/var/backups/giso}"
BACKUP_USER="${GISO_BACKUP_USER:-giso_backup}"
KEEP_DAYS="${GISO_BACKUP_KEEP_DAYS:-30}"
STAMP="$(date +%Y%m%d-%H%M)"

mkdir -p "$BACKUP_DIR"

for db in giso_db bot_edu_db; do
    pg_dump -U "$BACKUP_USER" -h 127.0.0.1 -Fc "$db" \
        -f "$BACKUP_DIR/${db}-${STAMP}.dump"
    echo "OK dump: ${db}-${STAMP}.dump"
done

# پاکسازی بکاپ‌های قدیمی‌تر از KEEP_DAYS روز
find "$BACKUP_DIR" -name '*.dump' -mtime +"$KEEP_DAYS" -delete

echo "DONE $STAMP"
