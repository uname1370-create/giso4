/**
 * scripts/reminder.mjs
 * ---------------------------------------------------------------------------
 * اسکریپت CRON برای خلاصه کردن لیدها و نوبت‌های ثبت‌شده با better-sqlite3
 * ---------------------------------------------------------------------------
 */

import Database from 'better-sqlite3';
import path from 'node:path';
import fs from 'node:fs';

const DB_PATH = path.join(process.cwd(), 'data', 'app.sqlite');

function runDailyReminder() {
  console.log('⏰ [CRON REMINDER] Starting daily appointment summary check...');

  if (!fs.existsSync(DB_PATH)) {
    console.log('ℹ️ No app.sqlite database found yet.');
    return;
  }

  try {
    const db = new Database(DB_PATH);
    const stmt = db.prepare('SELECT * FROM leads WHERE status IN ("new", "contacted", "booked") ORDER BY createdAt DESC');
    const leads = stmt.all();

    console.log(`📋 Total active leads requiring attention: ${leads.length}`);
    for (const lead of leads) {
      console.log(`👉 [${lead.status.toUpperCase()}] ${lead.fullName} | Phone: ${lead.phoneNumber} | Service: ${lead.selectedService} | Style: ${lead.selectedStyle}`);
    }
  } catch (error) {
    console.error('❌ Error executing reminder script:', error);
  }
}

runDailyReminder();
