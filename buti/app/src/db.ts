import fs from 'node:fs';
import path from 'node:path';
import Database from 'better-sqlite3';

export interface LeadRecord {
  id: string;
  fullName: string;
  phoneNumber: string;
  instagramId?: string | null;
  selectedService: string;
  selectedStyle: string;
  originalImageUrl: string;
  resultImageUrl: string;
  status: 'new' | 'contacted' | 'booked' | 'cancelled';
  notes?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ChatLogRecord {
  id: string;
  sessionId: string;
  userMessage: string;
  aiResponse: string;
  createdAt: string;
}

export interface TenantSettings {
  id: string;
  name: string;
  planTier: 'bronze' | 'silver' | 'gold';
  customAssistantName?: string;
  monthlyGenerationsLimit: number;
  currentMonthUsage: number;
  updatedAt: string;
}

const DB_DIR = path.join(process.cwd(), 'data');
const DB_PATH = path.join(DB_DIR, 'app.sqlite');

let dbInstance: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!dbInstance) {
    if (!fs.existsSync(DB_DIR)) {
      fs.mkdirSync(DB_DIR, { recursive: true });
    }
    dbInstance = new Database(DB_PATH);
    dbInstance.pragma('journal_mode = WAL');
    // تحمل رقابت نوشتن همزمان چند کاربر (به‌جای خطای فوری database is locked)
    dbInstance.pragma('busy_timeout = 5000');

    dbInstance.exec(`
      CREATE TABLE IF NOT EXISTS leads (
        id TEXT PRIMARY KEY,
        fullName TEXT NOT NULL,
        phoneNumber TEXT NOT NULL,
        instagramId TEXT,
        selectedService TEXT NOT NULL,
        selectedStyle TEXT NOT NULL,
        originalImageUrl TEXT NOT NULL,
        resultImageUrl TEXT NOT NULL,
        status TEXT DEFAULT 'new',
        notes TEXT,
        createdAt TEXT NOT NULL,
        updatedAt TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(createdAt DESC);
      CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);

      CREATE TABLE IF NOT EXISTS chat_logs (
        id TEXT PRIMARY KEY,
        sessionId TEXT NOT NULL,
        userMessage TEXT NOT NULL,
        aiResponse TEXT NOT NULL,
        createdAt TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_chat_logs_created ON chat_logs(createdAt DESC);

      CREATE TABLE IF NOT EXISTS tenant_settings (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        planTier TEXT NOT NULL DEFAULT 'gold',
        customAssistantName TEXT,
        monthlyGenerationsLimit INTEGER DEFAULT -1,
        currentMonthUsage INTEGER DEFAULT 0,
        updatedAt TEXT NOT NULL
      );
    `);

    // ایجاد رکورد پیش‌فرض سالن در صورت نبودن
    const checkTenant = dbInstance.prepare('SELECT id FROM tenant_settings WHERE id = ?').get('default');
    if (!checkTenant) {
      dbInstance.prepare(`
        INSERT INTO tenant_settings (id, name, planTier, customAssistantName, monthlyGenerationsLimit, currentMonthUsage, updatedAt)
        VALUES ('default', 'استودیو تخصصی عسل رجبی', 'gold', 'غزل - مشاور اختصاصی استودیو عسل رجبی', -1, 14, datetime('now'))
      `).run();
    }
  }
  return dbInstance;
}

/** دریافت تمام لیدها */
export function getLeads(): LeadRecord[] {
  const db = getDb();
  const stmt = db.prepare('SELECT * FROM leads ORDER BY createdAt DESC');
  return stmt.all() as LeadRecord[];
}

/** دریافت یک لید بر اساس شناسه */
export function getLeadById(id: string): LeadRecord | null {
  const db = getDb();
  const stmt = db.prepare('SELECT * FROM leads WHERE id = ?');
  const row = stmt.get(id);
  return (row as LeadRecord) || null;
}

/** ثبت لید جدید */
export function saveLead(data: Omit<LeadRecord, 'createdAt' | 'updatedAt'>): LeadRecord {
  const db = getDb();
  const now = new Date().toISOString();
  const lead: LeadRecord = {
    ...data,
    status: data.status || 'new',
    createdAt: now,
    updatedAt: now,
  };

  const stmt = db.prepare(`
    INSERT INTO leads (
      id, fullName, phoneNumber, instagramId, selectedService,
      selectedStyle, originalImageUrl, resultImageUrl, status,
      notes, createdAt, updatedAt
    ) VALUES (
      @id, @fullName, @phoneNumber, @instagramId, @selectedService,
      @selectedStyle, @originalImageUrl, @resultImageUrl, @status,
      @notes, @createdAt, @updatedAt
    )
  `);

  stmt.run({
    id: lead.id,
    fullName: lead.fullName,
    phoneNumber: lead.phoneNumber,
    instagramId: lead.instagramId ?? null,
    selectedService: lead.selectedService,
    selectedStyle: lead.selectedStyle,
    originalImageUrl: lead.originalImageUrl,
    resultImageUrl: lead.resultImageUrl,
    status: lead.status,
    notes: lead.notes ?? null,
    createdAt: lead.createdAt,
    updatedAt: lead.updatedAt,
  });

  return lead;
}

/** به‌روزرسانی وضعیت و یادداشت لید */
export function updateLeadStatus(
  id: string,
  status: LeadRecord['status'],
  notes?: string | null,
): LeadRecord | null {
  const db = getDb();
  const existing = getLeadById(id);
  if (!existing) return null;

  const newNotes = notes !== undefined ? notes : existing.notes;
  const now = new Date().toISOString();

  const stmt = db.prepare(`
    UPDATE leads
    SET status = ?, notes = ?, updatedAt = ?
    WHERE id = ?
  `);
  stmt.run(status, newNotes ?? null, now, id);

  return getLeadById(id);
}

/** حذف امن لید */
export function deleteLead(id: string): boolean {
  const db = getDb();
  const stmt = db.prepare('DELETE FROM leads WHERE id = ?');
  const info = stmt.run(id);
  return info.changes > 0;
}

/** ذخیره لاگ پیام کاربر و پاسخ هوش مصنوعی */
export function saveChatLog(sessionId: string, userMessage: string, aiResponse: string): ChatLogRecord {
  const db = getDb();
  const id = `chat_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  const now = new Date().toISOString();

  const stmt = db.prepare(`
    INSERT INTO chat_logs (id, sessionId, userMessage, aiResponse, createdAt)
    VALUES (?, ?, ?, ?, ?)
  `);
  stmt.run(id, sessionId, userMessage, aiResponse, now);

  return { id, sessionId, userMessage, aiResponse, createdAt: now };
}

/** دریافت تاریخچه لاگ‌های چت */
export function getChatLogs(limit = 50): ChatLogRecord[] {
  const db = getDb();
  const stmt = db.prepare('SELECT * FROM chat_logs ORDER BY createdAt DESC LIMIT ?');
  return stmt.all(limit) as ChatLogRecord[];
}

/** دریافت تنظیمات سالن و وضعیت پلن */
export function getTenantSettings(id = 'default'): TenantSettings {
  const db = getDb();
  const row = db.prepare('SELECT * FROM tenant_settings WHERE id = ?').get(id) as TenantSettings | undefined;
  if (row) return row;
  return {
    id: 'default',
    name: 'استودیو تخصصی عسل رجبی',
    planTier: 'gold',
    customAssistantName: 'غزل - مشاور اختصاصی استودیو عسل رجبی',
    monthlyGenerationsLimit: -1,
    currentMonthUsage: 14,
    updatedAt: new Date().toISOString(),
  };
}

/** به‌روزرسانی پلن یا تنظیمات سالن */
export function updateTenantSettings(
  id = 'default',
  updates: Partial<Omit<TenantSettings, 'id' | 'updatedAt'>>
): TenantSettings {
  const db = getDb();
  const current = getTenantSettings(id);
  const updated: TenantSettings = {
    ...current,
    ...updates,
    updatedAt: new Date().toISOString(),
  };

  const stmt = db.prepare(`
    UPDATE tenant_settings
    SET name = @name, planTier = @planTier, customAssistantName = @customAssistantName,
        monthlyGenerationsLimit = @monthlyGenerationsLimit, currentMonthUsage = @currentMonthUsage,
        updatedAt = @updatedAt
    WHERE id = @id
  `);

  stmt.run(updated);
  return updated;
}

/** افزایش شمارنده مصرف پیش‌نمایش در ماه */
export function incrementGenerationUsage(id = 'default'): void {
  const db = getDb();
  db.prepare('UPDATE tenant_settings SET currentMonthUsage = currentMonthUsage + 1, updatedAt = datetime(\'now\') WHERE id = ?').run(id);
}
