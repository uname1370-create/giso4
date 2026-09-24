/**
 * src/image-compress.ts
 * ---------------------------------------------------------------------------
 * فشرده‌سازی عکس نهایی رندر «بدون افت کیفیت محسوس»:
 * PNG چندمگابایتی خروجی مدل‌ها → JPEG باکیفیت بالا (پیش‌فرض q90، mozjpeg) + حذف متادیتا.
 * رندرهای ما عکس چهره مات‌اند (شفافیت ندارند)، پس JPEG انتخاب درست است.
 *
 * - fail-open: اگر sharp نصب نباشد یا خطایی بدهد، همان تصویر اصلی برمی‌گردد.
 * - اگر خروجی بزرگ‌تر از ورودی شد، همان اصلی نگه داشته می‌شود.
 * - IMAGE_COMPRESS=off → بدون فشرده‌سازی. IMAGE_JPEG_QUALITY=1..100 (پیش‌فرض 90).
 * ---------------------------------------------------------------------------
 */

export interface CompressResult {
  dataUri: string;
  savedPct: number;
  beforeKb: number;
  afterKb: number;
}

function jpegQuality(): number {
  const raw = Number(process.env.IMAGE_JPEG_QUALITY);
  if (Number.isFinite(raw) && raw >= 1 && raw <= 100) return Math.floor(raw);
  return 90;
}

export function compressEnabled(): boolean {
  const raw = (process.env.IMAGE_COMPRESS ?? 'on').trim().toLowerCase();
  return !(raw === 'off' || raw === '0' || raw === 'false');
}

/**
 * فشرده‌سازی data URI تصویر. در صورت غیرفعال‌بودن، نامناسب‌بودن ورودی،
 * بزرگ‌ترشدن خروجی یا هر خطایی → null (فراخواننده همان اصلی را نگه می‌دارد).
 */
export async function compressGeneratedImage(dataUri: string): Promise<CompressResult | null> {
  if (!compressEnabled()) return null;
  if (!dataUri.startsWith('data:image/')) return null;
  try {
    const match = /^data:(image\/[a-zA-Z0-9+.-]+);base64,(.+)$/.exec(dataUri);
    if (!match) return null;
    const input = Buffer.from(match[2], 'base64');
    if (input.length === 0) return null;

    // لود تنبلِ واقعاً اختیاری: اسم ماژول داخل eval پنهان شده تا باندلر
    // (webpack/turbopack) در زمان کامپایل دنبال sharp نگردد. نبودن یا خراب‌بودن
    // نصب sharp فقط یعنی «بدون فشرده‌سازی» — هرگز خطای کامپایل/رندر نمی‌دهد.
    // eslint-disable-next-line no-eval
    const nodeRequire = eval('require') as (id: string) => unknown;
    const sharp = nodeRequire('sharp') as (input: Buffer) => {
      jpeg: (opts: Record<string, unknown>) => { toBuffer: () => Promise<Buffer> };
    };
    const out: Buffer = await sharp(input)
      .jpeg({ quality: jpegQuality(), mozjpeg: true })
      .toBuffer();

    if (out.length >= input.length) return null;
    const beforeKb = Math.round(input.length / 1024);
    const afterKb = Math.round(out.length / 1024);
    const savedPct = Math.round((1 - out.length / input.length) * 100);
    return {
      dataUri: `data:image/jpeg;base64,${out.toString('base64')}`,
      savedPct,
      beforeKb,
      afterKb,
    };
  } catch (error) {
    console.error(
      `[AI-GENERATE] COMPRESS skipped: ${
        error instanceof Error ? error.message : String(error)
      }`.slice(0, 200),
    );
    return null;
  }
}
