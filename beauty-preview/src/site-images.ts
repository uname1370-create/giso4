/**
 * src/site-images.ts
 * ---------------------------------------------------------------------------
 * مدیریت تصاویر آپلودشده از پنل مدیریت (/admin):
 *
 *   تصاویر ابروها — فقط PNG، حداکثر ۵ مگابایت، با نام‌های ثابت:
 *       public/eyebrows/natural-hairstroke.png   ← هایر استروک طبیعی
 *       public/eyebrows/feather.png              ← فدر براو
 *       public/eyebrows/ombre-powder.png         ← اومبره پودری
 *       public/eyebrows/combination.png          ← کامبینیشن
 *
 *   تصویر هیرو — JPG/PNG/WEBP، حداکثر ۱۰ مگابایت:
 *       public/hero/hero.jpg  یا  hero.png  یا  hero.webp
 *       (فقط یکی از این سه هم‌زمان وجود دارد؛ آپلود جدید بقیه را پاک می‌کند)
 *
 * نام‌ها ثابت‌اند (نه timestamp‌دار) تا صفحهٔ اصلی بتواند بدون هیچ فهرست
 * جانبی، تصویر مدیر را جای SVG خودکار بگذارد و اگر فایل نبود به SVG برگردد.
 *
 * تصاویر از روت `/api/site-image/...` سرو می‌شوند، نه مستقیم از public/:
 * سرور production نکست فهرست پوشهٔ public را فقط یک بار در زمان بالا آمدن
 * می‌خواند؛ پس فایلی که بعد از استارت آپلود شود تا ری‌استارت سرور ۴۰۴ می‌دهد.
 * روت در هر درخواست فایل را از دیسک می‌خواند.
 *
 * فقط سمت سرور استفاده می‌شود.
 * ---------------------------------------------------------------------------
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';

import { BROW_IMAGE_FOLDER, HERO_IMAGE_BASENAME, HERO_IMAGE_FOLDER, EYEBROW_STYLES } from './options';

/** ریشهٔ پوشهٔ public */
export const PUBLIC_DIR = path.join(process.cwd(), 'public');

/** حداکثر حجم تصویر ابرو (۵ مگابایت) */
export const MAX_BROW_BYTES = 5 * 1024 * 1024;

/** حداکثر حجم تصویر هیرو (۱۰ مگابایت) */
export const MAX_HERO_BYTES = 10 * 1024 * 1024;

/** فرمت‌های مجاز تصویر هیرو */
export const HERO_EXTENSIONS = ['jpg', 'png', 'webp'] as const;

export type HeroExtension = (typeof HERO_EXTENSIONS)[number];

/** نوع محتوا بر اساس پسوند فایل */
export const MIME_BY_EXTENSION: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
};

/** امضای بایتی فایل‌های تصویری (برای اطمینان از اینکه فایل واقعاً تصویر است) */
const SIGNATURES: Array<{ extension: HeroExtension; mime: string; bytes: number[]; offset?: number }> = [
  { extension: 'jpg', mime: 'image/jpeg', bytes: [0xff, 0xd8, 0xff] },
  { extension: 'png', mime: 'image/png', bytes: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a] },
  {
    extension: 'webp',
    mime: 'image/webp',
    bytes: [0x57, 0x45, 0x42, 0x50], // "WEBP" در بایت‌های ۸ تا ۱۱
    offset: 8,
  },
];

/** تشخیص نوع واقعی فایل از روی محتوایش (نه از روی هدر مرورگر) */
export function detectImageExtension(buffer: Buffer): HeroExtension | null {
  for (const signature of SIGNATURES) {
    const offset = signature.offset ?? 0;
    const matches = signature.bytes.every((byte, index) => buffer[offset + index] === byte);
    if (matches) return signature.extension;
  }
  return null;
}

/* -------------------------------------------------------------------------- */
/* ابروها                                                                     */
/* -------------------------------------------------------------------------- */

/** مشخصات آپلود هر مدل ابرو */
export interface BrowTarget {
  /** کلید داخلی مدل */
  key: string;
  /** نام فایل روی دیسک، مثل feather.png */
  fileName: string;
  /** نام فارسی مدل */
  label: string;
  /** مسیر فایل داخل public، مثل /eyebrows/feather.png */
  publicPath: string;
}

/** فهرست مدل‌های ابرو با مسیر فایل ثابتشان (برگرفته از src/options.ts) */
export const BROW_TARGETS: BrowTarget[] = EYEBROW_STYLES.map((style) => ({
  key: style.key,
  fileName: style.imageFileName,
  label: style.label,
  publicPath: style.imagePath,
}));

export function findBrowTarget(value: string | null | undefined): BrowTarget | null {
  if (!value) return null;
  const needle = value.trim().toLowerCase();
  if (!needle) return null;

  return (
    BROW_TARGETS.find(
      (target) =>
        target.key.toLowerCase() === needle ||
        target.label === value.trim() ||
        target.label.toLowerCase() === needle ||
        target.fileName.toLowerCase() === needle ||
        target.fileName.replace(/\.png$/, '').toLowerCase() === needle,
    ) ?? null
  );
}

/* -------------------------------------------------------------------------- */
/* مسیر‌یابی امن                                                              */
/* -------------------------------------------------------------------------- */

/**
 * تبدیل مسیر درخواستی (بدون پیشوند /api/site-image) به مسیر فایل روی دیسک.
 *
 *   eyebrows/feather.png  → <public>/eyebrows/feather.png
 *   hero/hero             → <public>/hero/hero.jpg|png|webp (اولین فایلی که وجود دارد)
 *   hero/hero.jpg         → <public>/hero/hero.jpg
 *
 * اگر مسیر نامعتبر یا خارج از public باشد، `null` برمی‌گردد (path traversal).
 */
export async function resolveSiteImage(
  relative: string,
): Promise<{ filePath: string; mime: string } | null> {
  if (!relative || relative.includes('..') || relative.includes('\\')) return null;

  const clean = relative.replace(/^\/+/, '');
  const parts = clean.split('/').filter(Boolean);
  if (parts.length !== 2) return null;

  const [folder, name] = parts;
  const root = path.resolve(PUBLIC_DIR);

  // ---- تصویر ابرو: فقط نام‌های ثابت و فقط PNG ----
  if (folder === BROW_IMAGE_FOLDER.replace(/^\//, '')) {
    const target = BROW_TARGETS.find((item) => item.fileName === name);
    if (!target) return null;

    const filePath = path.resolve(root, folder, target.fileName);
    if (!filePath.startsWith(root + path.sep)) return null;
    return { filePath, mime: MIME_BY_EXTENSION.png };
  }

  // ---- تصویر هیرو ----
  if (folder === HERO_IMAGE_FOLDER.replace(/^\//, '')) {
    const lower = name.toLowerCase();

    // نام دقیق فایل (با پسوند) — ولی فقط با نام پایهٔ hero
    if (/^hero\.(jpg|jpeg|png|webp)$/.test(lower)) {
      const extension = lower.split('.').pop() as string;
      const fileName = `${HERO_IMAGE_BASENAME}.${extension === 'jpeg' ? 'jpg' : extension}`;
      const filePath = path.resolve(root, folder, fileName);
      if (!filePath.startsWith(root + path.sep)) return null;
      return { filePath, mime: MIME_BY_EXTENSION[extension] ?? 'application/octet-stream' };
    }

    // نام بدون پسوند: اولین فایلی که وجود دارد
    if (lower === HERO_IMAGE_BASENAME) {
      for (const extension of HERO_EXTENSIONS) {
        const filePath = path.resolve(root, folder, `${HERO_IMAGE_BASENAME}.${extension}`);
        try {
          await fs.access(filePath);
          return { filePath, mime: MIME_BY_EXTENSION[extension] };
        } catch {
          /* این پسوند وجود ندارد — بعدی */
        }
      }
      return null;
    }
  }

  return null;
}

/** خواندن فایل تصویر برای سرو کردن (روت /api/site-image) */
export async function readSiteImage(relative: string): Promise<{ buffer: Buffer; mime: string } | null> {
  const resolved = await resolveSiteImage(relative);
  if (!resolved) return null;

  try {
    const buffer = await fs.readFile(resolved.filePath);
    return { buffer, mime: resolved.mime };
  } catch {
    return null;
  }
}

/** آیا این مدل ابرو تصویر اختصاصی دارد؟ */
export async function browImageExists(target: BrowTarget): Promise<boolean> {
  try {
    await fs.access(path.resolve(PUBLIC_DIR, target.publicPath.replace(/^\//, '')));
    return true;
  } catch {
    return false;
  }
}

/* -------------------------------------------------------------------------- */
/* ذخیره و حذف                                                                */
/* -------------------------------------------------------------------------- */

export interface SavedImage {
  /** آدرسی که به مرورگر داده می‌شود (روت /api/site-image) */
  url: string;
  /** مسیر فایل داخل public */
  publicPath: string;
  /** نام فایل */
  fileName: string;
  bytes: number;
  mime: string;
}

/** ذخیرهٔ تصویر ابرو (فقط PNG، حداکثر ۵ مگابایت) */
export async function saveBrowImage(target: BrowTarget, file: File): Promise<SavedImage> {
  const buffer = Buffer.from(await file.arrayBuffer());

  if (buffer.length === 0) throw new Error('فایل خالی است.');
  if (buffer.length > MAX_BROW_BYTES) throw new Error('حجم تصویر بیش از ۵ مگابایت است.');
  if (detectImageExtension(buffer) !== 'png') {
    throw new Error('برای تصویر ابرو فقط فایل PNG پذیرفته می‌شود.');
  }

  const directory = path.join(PUBLIC_DIR, BROW_IMAGE_FOLDER.replace(/^\//, ''));
  await fs.mkdir(directory, { recursive: true });
  await fs.writeFile(path.join(directory, target.fileName), buffer);

  return {
    url: `/api/site-image${target.publicPath}`,
    publicPath: target.publicPath,
    fileName: target.fileName,
    bytes: buffer.length,
    mime: 'image/png',
  };
}

/** حذف تصویر ابرو (اگر وجود داشته باشد) */
export async function deleteBrowImage(target: BrowTarget): Promise<boolean> {
  try {
    await fs.unlink(path.resolve(PUBLIC_DIR, target.publicPath.replace(/^\//, '')));
    return true;
  } catch {
    return false;
  }
}

/**
 * ذخیرهٔ تصویر هیرو.
 * فایل با نام hero.<ext> ذخیره می‌شود و بقیهٔ پسوندهای hero پاک می‌شوند تا
 * همیشه فقط یک تصویر هیرو وجود داشته باشد.
 */
export async function saveHeroImage(file: File): Promise<SavedImage> {
  const buffer = Buffer.from(await file.arrayBuffer());

  if (buffer.length === 0) throw new Error('فایل خالی است.');
  if (buffer.length > MAX_HERO_BYTES) throw new Error('حجم تصویر بیش از ۱۰ مگابایت است.');

  const extension = detectImageExtension(buffer);
  if (!extension) {
    throw new Error('فقط فایل‌های JPG، PNG و WEBP پذیرفته می‌شوند.');
  }

  const directory = path.join(PUBLIC_DIR, HERO_IMAGE_FOLDER.replace(/^\//, ''));
  await fs.mkdir(directory, { recursive: true });

  const fileName = `${HERO_IMAGE_BASENAME}.${extension}`;
  await fs.writeFile(path.join(directory, fileName), buffer);

  // بقیهٔ فرمت‌ها را پاک کن تا فقط یک تصویر هیرو بماند
  for (const other of HERO_EXTENSIONS) {
    if (other === extension) continue;
    await fs.unlink(path.join(directory, `${HERO_IMAGE_BASENAME}.${other}`)).catch(() => undefined);
  }

  return {
    url: `/api/site-image${HERO_IMAGE_FOLDER}/${HERO_IMAGE_BASENAME}`,
    publicPath: `${HERO_IMAGE_FOLDER}/${fileName}`,
    fileName,
    bytes: buffer.length,
    mime: MIME_BY_EXTENSION[extension],
  };
}

/** حذف تصویر هیرو (همهٔ پسوندها) */
export async function deleteHeroImage(): Promise<boolean> {
  const directory = path.join(PUBLIC_DIR, HERO_IMAGE_FOLDER.replace(/^\//, ''));
  let removed = false;

  for (const extension of HERO_EXTENSIONS) {
    try {
      await fs.unlink(path.join(directory, `${HERO_IMAGE_BASENAME}.${extension}`));
      removed = true;
    } catch {
      /* این پسوند وجود نداشت */
    }
  }

  return removed;
}
