/**
 * src/stats.ts
 * ---------------------------------------------------------------------------
 * ذخیره‌سازی آمار بازدید و پیش‌نمایش‌ها در فایل `data/stats.json`.
 *
 * ساختار فایل:
 *   {
 *     "visits": 42,
 *     "previews": 18,
 *     "history": [
 *       { "type": "visit",   "time": "2025-01-15T10:30:00.000Z" },
 *       { "type": "preview", "style": "feather", "time": "2025-01-15T10:32:00.000Z" }
 *     ]
 *   }
 *
 * نکات:
 *  - فقط سمت سرور (Node) استفاده می‌شود.
 *  - نوشتن‌ها با یک قفل ساده (صف) سریال می‌شوند تا فایل خراب نشود.
 *  - تاریخچه حداکثر MAX_HISTORY رویداد نگه می‌دارد (قدیمی‌ترها حذف می‌شوند).
 *  - اگر فایل نبود یا خراب بود، مقدار پیش‌فرض برگردانده می‌شود (بدون کرش).
 * ---------------------------------------------------------------------------
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';

export type StatEventType = 'visit' | 'preview';

export interface StatEvent {
  type: StatEventType;
  /** زمان ISO (UTC) */
  time: string;
  /** کلید سبک ابرو (فقط برای رویداد preview) — مثل "feather" */
  style?: string;
}

export interface StatsData {
  visits: number;
  previews: number;
  history: StatEvent[];
}

/** حداکثر تعداد رویدادهای نگه‌داری‌شده در تاریخچه */
const MAX_HISTORY = 300;

/**
 * مسیر فایل آمار.
 * پیش‌فرض: <ریشهٔ اپ>/data/stats.json
 * با متغیر محیطی STATS_PATH قابل تغییر است (اسکریپت‌های تست از این راه
 * آمار واقعی را دست‌نخورده می‌گذارند).
 */
export const STATS_PATH = process.env.STATS_PATH
  ? path.resolve(process.env.STATS_PATH)
  : path.join(process.cwd(), 'data', 'stats.json');

/* -------------------------------------------------------------------------- */
/* قفل نوشتن                                                                  */
/* -------------------------------------------------------------------------- */

let queue: Promise<unknown> = Promise.resolve();

function withLock<T>(task: () => Promise<T>): Promise<T> {
  const run = queue.then(task, task);
  queue = run.catch(() => undefined);
  return run;
}

/* -------------------------------------------------------------------------- */
/* خواندن / نوشتن                                                             */
/* -------------------------------------------------------------------------- */

function emptyStats(): StatsData {
  return { visits: 0, previews: 0, history: [] };
}

/** پاک‌سازی دادهٔ خوانده‌شده تا ورودی نامعتبر باعث خطا نشود */
function sanitize(raw: unknown): StatsData {
  if (!raw || typeof raw !== 'object') return emptyStats();
  const record = raw as Record<string, unknown>;

  const visits = Number.isFinite(Number(record.visits)) ? Math.max(0, Math.trunc(Number(record.visits))) : 0;
  const previews = Number.isFinite(Number(record.previews))
    ? Math.max(0, Math.trunc(Number(record.previews)))
    : 0;

  const history: StatEvent[] = Array.isArray(record.history)
    ? record.history
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
        .map((item) => {
          const type: StatEventType = item.type === 'preview' ? 'preview' : 'visit';
          const event: StatEvent = {
            type,
            time: typeof item.time === 'string' ? item.time : new Date(0).toISOString(),
          };
          if (typeof item.style === 'string' && item.style) event.style = item.style;
          return event;
        })
        .slice(0, MAX_HISTORY)
    : [];

  return { visits, previews, history };
}

/** خواندن آمار فعلی */
export async function readStats(): Promise<StatsData> {
  try {
    const text = await fs.readFile(STATS_PATH, 'utf8');
    return sanitize(JSON.parse(text));
  } catch {
    // فایل موجود نیست یا خواندنش ممکن نبود → مقدار پیش‌فرض
    return emptyStats();
  }
}

async function writeStats(data: StatsData): Promise<void> {
  await fs.mkdir(path.dirname(STATS_PATH), { recursive: true });
  await fs.writeFile(STATS_PATH, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
}

/**
 * ثبت یک رویداد (بازدید یا پیش‌نمایش) و برگرداندن آمار به‌روزشده.
 * این تابع خطا پرتاب نمی‌کند؛ در بدترین حالت آمار قبلی را برمی‌گرداند.
 */
export async function recordEvent(event: StatEvent): Promise<StatsData> {
  try {
    return await withLock(async () => {
      const current = await readStats();
      const next: StatsData = {
        visits: current.visits + (event.type === 'visit' ? 1 : 0),
        previews: current.previews + (event.type === 'preview' ? 1 : 0),
        history: [event, ...current.history].slice(0, MAX_HISTORY),
      };
      await writeStats(next);
      return next;
    });
  } catch {
    return readStats();
  }
}

/* -------------------------------------------------------------------------- */
/* خلاصهٔ آمار برای پنل مدیریت                                                */
/* -------------------------------------------------------------------------- */

/** کلید روز محلی (YYYY-MM-DD) از یک زمان ISO */
export function localDayKey(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

export interface StatsSummary extends StatsData {
  /** بازدیدهای امروز (به وقت محلی سرور) */
  todayVisits: number;
  /** پیش‌نمایش‌های امروز */
  todayPreviews: number;
  /** کلید امروز — برای نمایش در پنل */
  today: string;
}

/**
 * خلاصهٔ آماری برای داشبورد: کل‌ها + آمار امروز + آخرین رویدادها.
 * `historyLimit` تعداد رویدادهای برگشتی در history است.
 */
export async function statsSummary(historyLimit = 10): Promise<StatsSummary> {
  const data = await readStats();
  const today = localDayKey(new Date().toISOString());

  let todayVisits = 0;
  let todayPreviews = 0;
  for (const event of data.history) {
    if (localDayKey(event.time) !== today) continue;
    if (event.type === 'visit') todayVisits += 1;
    else todayPreviews += 1;
  }

  return {
    ...data,
    history: data.history.slice(0, Math.max(1, Math.min(historyLimit, MAX_HISTORY))),
    todayVisits,
    todayPreviews,
    today,
  };
}
