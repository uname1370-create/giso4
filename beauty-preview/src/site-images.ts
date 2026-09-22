/**
 * src/site-images.ts
 * ---------------------------------------------------------------------------
 * مدیریت تصاویر آپلودشده از پنل مدیریت:
 *
 *   - فایل‌ها در `public/` ذخیره می‌شوند:
 *       public/eyebrows/<style>-<timestamp>.<ext>   ← تصاویر مدل‌های ابرو
 *       public/hero/hero-<timestamp>.<ext>          ← تصویر هیرو صفحهٔ اصلی
 *
 *   - تصاویر از طریق روت `/api/site-image/...` سرو می‌شوند، نه مستقیم از public/.
 *     دلیل: در حالت production سرور Next فهرست پوشهٔ public را فقط یک بار در زمان
 *     بالا آمدن می‌خواند؛ فایلی که بعد از استارت آپلود شود تا ری‌استارت ۴۰۴ می‌دهد.
 *     این روت فایل را در هر درخواست از دیسک می‌خواند تا آپلود در dev و production
 *     بلافاصله دیده شود.
 *
 *   - فهرست تصاویر در `public/site-images.json` نگه داشته می‌شود تا صفحهٔ اصلی
 *     بتواند با یک fetch ساده (بدون API) آن را بخواند:
 *
 *       { "brows": { "hairstroke": "/api/site-image/eyebrows/hairstroke-1712.jpg" },
 *         "hero": "/api/site-image/hero/hero-1712.jpg", "updatedAt": "..." }
 *
 * فقط سمت سرور استفاده می‌شود.
 * ---------------------------------------------------------------------------
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';

import type { BrowStyleKey } from './brow-shapes';

export interface SiteImages {
  /** تصویر اختصاصی هر مدل ابرو (اگر نباشد، SVG خودکار نمایش داده می‌شود) */
  brows: Partial<Record<BrowStyleKey, string>>;
  /** تصویر هیرو صفحهٔ اصلی */
  hero: string | null;
  /** زمان آخرین تغییر (ISO) */
  updatedAt: string | null;
}

/** ریشهٔ پوشهٔ public */
export const PUBLIC_DIR = path.join(process.cwd(), 'public');

/** مسیر فایل فهرست تصاویر */
export const MANIFEST_PATH = path.join(PUBLIC_DIR, 'site-images.json');

export const BROW_KEYS: BrowStyleKey[] = ['hairstroke', 'feather', 'ombre', 'combination'];

/** پیشوند روت سرو کردن تصاویر آپلودی */
export const SITE_IMAGE_ROUTE = '/api/site-image';

/** پوشه‌هایی که آپلود در آن‌ها مجاز است */
export const UPLOAD_FOLDERS = ['eyebrows', 'hero'] as const;

export type UploadFolder = (typeof UPLOAD_FOLDERS)[number];

/** نوع محتوا بر اساس پسوند فایل */
export const MIME_BY_EXTENSION: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
};

/** الگوی نام امن فایل‌های آپلودی (نام را خودمان می‌سازیم) */
const SAFE_FILE = /^[a-z0-9][a-z0-9-]*\.(jpg|jpeg|png|webp)$/i;

/** اندازهٔ مجاز آپلود (۵ مگابایت) */
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

export const ALLOWED_MIME: Record<string, string> = {
  'image/jpeg': 'jpg',
  'image/jpg': 'jpg',
  'image/png': 'png',
  'image/webp': 'webp',
};

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
/* فهرست تصاویر                                                               */
/* -------------------------------------------------------------------------- */

function emptySiteImages(): SiteImages {
  return { brows: {}, hero: null, updatedAt: null };
}

function sanitize(raw: unknown): SiteImages {
  if (!raw || typeof raw !== 'object') return emptySiteImages();
  const record = raw as Record<string, unknown>;

  const brows: Partial<Record<BrowStyleKey, string>> = {};
  const rawBrows = record.brows;
  if (rawBrows && typeof rawBrows === 'object') {
    for (const key of BROW_KEYS) {
      const value = (rawBrows as Record<string, unknown>)[key];
      if (typeof value === 'string' && value) brows[key] = value;
    }
  }

  return {
    brows,
    hero: typeof record.hero === 'string' && record.hero ? record.hero : null,
    updatedAt: typeof record.updatedAt === 'string' ? record.updatedAt : null,
  };
}

export async function readSiteImages(): Promise<SiteImages> {
  try {
    const text = await fs.readFile(MANIFEST_PATH, 'utf8');
    return sanitize(JSON.parse(text));
  } catch {
    return emptySiteImages();
  }
}

async function writeSiteImages(data: SiteImages): Promise<SiteImages> {
  const next: SiteImages = { ...data, updatedAt: new Date().toISOString() };
  await fs.mkdir(path.dirname(MANIFEST_PATH), { recursive: true });
  await fs.writeFile(MANIFEST_PATH, `${JSON.stringify(next, null, 2)}\n`, 'utf8');
  return next;
}

/** به‌روزرسانی فهرست (با قفل، برای جلوگیری از نوشتن هم‌زمان) */
export async function updateSiteImages(
  patch: (current: SiteImages) => SiteImages,
): Promise<SiteImages> {
  return withLock(async () => {
    const current = await readSiteImages();
    return writeSiteImages(patch(current));
  });
}

/* -------------------------------------------------------------------------- */
/* ذخیره و حذف فایل                                                           */
/* -------------------------------------------------------------------------- */

export interface SavedUpload {
  /** آدرسی که به مرورگر داده می‌شود، مثل /api/site-image/eyebrows/hairstroke-1712.jpg */
  url: string;
  /** مسیر فایل داخل public، مثل /eyebrows/hairstroke-1712.jpg */
  publicPath: string;
  /** نام فایل */
  fileName: string;
  bytes: number;
  mime: string;
}

/**
 * ذخیرهٔ فایل آپلودی داخل public/<folder>/ با نام امن.
 * نام فایل ساختهٔ خودمان است (prefix + timestamp) و از ورودی کاربر نمی‌آید.
 */
export async function saveUpload(
  folder: 'eyebrows' | 'hero',
  prefix: string,
  file: File,
): Promise<SavedUpload> {
  const extension = ALLOWED_MIME[file.type.toLowerCase()];
  if (!extension) {
    throw new Error('فقط فایل‌های JPG، PNG و WEBP پذیرفته می‌شوند.');
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error('حجم فایل بیش از ۵ مگابایت است.');
  }
  if (file.size === 0) {
    throw new Error('فایل خالی است.');
  }

  const safePrefix = prefix.replace(/[^a-z0-9-]/gi, '') || 'image';
  const fileName = `${safePrefix}-${Date.now()}.${extension}`;
  const directory = path.join(PUBLIC_DIR, folder);

  await fs.mkdir(directory, { recursive: true });
  const buffer = Buffer.from(await file.arrayBuffer());
  await fs.writeFile(path.join(directory, fileName), buffer);

  return {
    url: `${SITE_IMAGE_ROUTE}/${folder}/${fileName}`,
    publicPath: `/${folder}/${fileName}`,
    fileName,
    bytes: buffer.length,
    mime: file.type,
  };
}

/**
 * تبدیل آدرس ذخیره‌شده در فهرست تصاویر به مسیر فایل داخل public.
 *
 *   /api/site-image/hero/hero-1712.jpg  →  <public>/hero/hero-1712.jpg
 *   /hero/hero-1712.jpg                 →  <public>/hero/hero-1712.jpg  (فرمت قدیمی)
 *
 * اگر مسیر نامعتبر/خارج از public باشد، `null` برمی‌گردد (محافظت از path traversal).
 */
export function resolveUploadPath(url: string | null | undefined): string | null {
  if (!url || typeof url !== 'string' || url.includes('..') || url.includes('\\')) return null;

  const relative = url.startsWith(SITE_IMAGE_ROUTE)
    ? url.slice(SITE_IMAGE_ROUTE.length)
    : url.startsWith('/')
      ? url
      : `/${url}`;

  const parts = relative.split('/').filter(Boolean);
  if (parts.length !== 2) return null;

  const [folder, fileName] = parts;
  if (!(UPLOAD_FOLDERS as readonly string[]).includes(folder)) return null;
  if (!SAFE_FILE.test(fileName)) return null;

  const target = path.resolve(PUBLIC_DIR, folder, fileName);
  const root = path.resolve(PUBLIC_DIR);
  if (!target.startsWith(root + path.sep)) return null;

  return target;
}

/** حذف یک فایل آپلودشده با آدرس ذخیره‌شده در فهرست تصاویر */
export async function deleteUpload(url: string | null | undefined): Promise<void> {
  const target = resolveUploadPath(url);
  if (!target) return;

  try {
    await fs.unlink(target);
  } catch {
    // فایل از قبل نیست — مشکلی نیست
  }
}

/** خواندن فایل آپلودشده برای سرو کردن (روت /api/site-image) */
export async function readUpload(
  url: string | null | undefined,
): Promise<{ buffer: Buffer; mime: string } | null> {
  const target = resolveUploadPath(url);
  if (!target) return null;

  try {
    const buffer = await fs.readFile(target);
    const extension = path.extname(target).slice(1).toLowerCase();
    return { buffer, mime: MIME_BY_EXTENSION[extension] ?? 'application/octet-stream' };
  } catch {
    return null;
  }
}
