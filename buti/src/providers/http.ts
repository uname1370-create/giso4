/**
 * src/providers/http.ts
 * ---------------------------------------------------------------------------
 * ابزارهای مشترک همهٔ پروایدرها: تجزیهٔ data URI، مهلت (timeout) و
 * یکسان‌سازی شکل پاسخ‌ها.
 * ---------------------------------------------------------------------------
 */

export interface ParsedImage {
  /** مثال: image/jpeg */
  mime: string;
  /** base64 بدون پیشوند data URI */
  base64: string;
  /** data URI کامل (همان چیزی که از مرورگر آمده) */
  dataUri: string;
  /** بایت‌های تصویر (برای آپلود چندبخشی) */
  bytes: Buffer;
  extension: string;
}

const EXTENSION_BY_MIME: Record<string, string> = {
  'image/jpeg': 'jpg',
  'image/jpg': 'jpg',
  'image/png': 'png',
  'image/webp': 'webp',
};

/** تجزیهٔ data URI به اجزای مورد نیاز پروایدرها */
export function parseDataUri(dataUri: string): ParsedImage | null {
  const match = /^data:([\w.+-]+\/[\w.+-]+);base64,(.+)$/s.exec(dataUri.trim());
  if (!match) return null;

  const [, mime, base64] = match;
  const bytes = Buffer.from(base64, 'base64');
  if (bytes.length === 0) return null;

  return {
    mime,
    base64,
    dataUri: `data:${mime};base64,${base64}`,
    bytes,
    extension: EXTENSION_BY_MIME[mime.toLowerCase()] ?? 'png',
  };
}

/** خطای پروایدر با پیام خوانا */
export class ProviderError extends Error {
  constructor(
    message: string,
    readonly detail?: string,
  ) {
    super(message);
    this.name = 'ProviderError';
  }
}

/** ساخت یک AbortSignal با مهلت مشخص */
export function timeoutSignal(ms: number): { signal: AbortSignal; done: () => void } {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  return { signal: controller.signal, done: () => clearTimeout(timer) };
}

/**
 * مهلت مؤثر برای یک پروایدر: `timeoutMs` مستقیمِ درخواست (تست سلامت)
 * بر `PROVIDER_TIMEOUT_MS` مقدم است وگرنه پیش‌فرض ۹۰ ثانیه‌ای.
 */
export function timeoutFor(input?: { timeoutMs?: number }): number {
  const custom = Number(input?.timeoutMs);
  if (Number.isFinite(custom) && custom > 1000) return custom;

  const raw = Number(process.env.PROVIDER_TIMEOUT_MS);
  if (Number.isFinite(raw) && raw > 1000) return raw;

  return 90_000;
}

/**
 * استخراج تصویر از پاسخِ فرمت‌شدهٔ OpenAI (Images API):
 *   { data: [ { url } ] }  یا  { data: [ { b64_json } ] }
 *
 * همچنین پاسخ خامِ پروایدرهای سازگار با OpenAI SDK را می‌پذیرد (شیء کامل
 * response که داده‌ها زیر response.data قرار دارند).
 * در صورت نبود تصویر، `null` برمی‌گرداند.
 */
export function readOpenAiImage(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null;

  const record = payload as Record<string, unknown>;

  // پاسخ خام JSON: { data: [{ url | b64_json }] }
  // پاسخ کامل SDK: { data: { data: [...] } }
  let images: unknown = record.data;

  if (images && typeof images === 'object' && !Array.isArray(images)) {
    const inner = images as Record<string, unknown>;
    if (Array.isArray(inner.data)) {
      images = inner.data;
    }
  }

  if (!Array.isArray(images) || images.length === 0) return null;

  const first = images[0] as Record<string, unknown> | null;
  if (!first) return null;

  if (typeof first.url === 'string') return first.url;

  if (typeof first.b64_json === 'string') {
    return first.b64_json.startsWith('data:')
      ? first.b64_json
      : `data:image/png;base64,${first.b64_json}`;
  }

  return null;
}

/** استخراج پیام خطا از بدنهٔ JSON پروایدرها */
export function extractApiError(payload: unknown): string {
  if (!payload || typeof payload !== 'object') return '';
  const record = payload as Record<string, unknown>;

  const errors = record.errors;
  if (Array.isArray(errors) && errors.length > 0) {
    const first = errors[0] as Record<string, unknown>;
    return String(first?.message ?? first?.code ?? JSON.stringify(first)).slice(0, 300);
  }
  if (record.error) {
    const err = record.error;
    if (typeof err === 'string') return err.slice(0, 300);
    if (typeof err === 'object') {
      const msg = (err as Record<string, unknown>).message;
      if (msg) return String(msg).slice(0, 300);
    }
  }
  if (typeof record.message === 'string') return record.message.slice(0, 300);
  if (typeof record.detail === 'string') return record.detail.slice(0, 300);
  return '';
}

/**
 * نتیجه را به data URI تبدیل می‌کند تا دانلود در مرورگر بدون مشکل CORS
 * انجام شود. اگر دانلود ناموفق بود، همان آدرس اصلی برگردانده می‌شود.
 */
export async function materializeImage(image: string): Promise<string> {
  if (image.startsWith('data:')) return image;

  const { signal, done } = timeoutSignal(30_000);
  try {
    const res = await fetch(image, { signal, cache: 'no-store' });
    if (!res.ok) return image;
    const buffer = Buffer.from(await res.arrayBuffer());
    if (buffer.length === 0 || buffer.length > 12 * 1024 * 1024) return image;
    const mime = res.headers.get('content-type')?.split(';')[0] ?? 'image/jpeg';
    return `data:${mime};base64,${buffer.toString('base64')}`;
  } catch {
    return image;
  } finally {
    done();
  }
}
