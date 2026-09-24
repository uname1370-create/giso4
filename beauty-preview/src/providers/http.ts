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

export function providerTimeoutMs(): number {
  const raw = Number(process.env.PROVIDER_TIMEOUT_MS);
  // پیش‌فرض ۱۵ ثانیه (fail-fast): به‌جای معطلی چنددقیقه‌ای، سریع به پروایدر بعدی یا حالت نمایشی می‌رویم
  return Number.isFinite(raw) && raw > 1000 ? raw : 15_000;
}

/**
 * مهلت مؤثر یک درخواست: اگر ورودی `timeoutMs` داده باشد از آن استفاده می‌شود
 * (مثلاً در تست سلامت کلیدها که باید سریع تمام شود)، وگرنه مقدار پیش‌فرض.
 */
export function timeoutFor(input?: { timeoutMs?: number }): number {
  const custom = Number(input?.timeoutMs);
  if (Number.isFinite(custom) && custom > 1000) return custom;
  return providerTimeoutMs();
}

/** خواندن متن امن از پاسخ (برای پیام خطای دقیق‌تر) */
export async function safeText(res: Response): Promise<string> {
  try {
    return (await res.text()).slice(0, 600);
  } catch {
    return '';
  }
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
 * خواندن امن نتیجهٔ سبک OpenAI:
 * `response.data[0].url` یا `response.data[0].b64_json`
 */
export function readOpenAiImage(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null;
  const data = (payload as Record<string, unknown>).data;
  if (!Array.isArray(data) || data.length === 0) return null;

  const img = data[0] as Record<string, unknown>;
  if (typeof img?.url === 'string' && img.url) return img.url;
  if (typeof img?.b64_json === 'string' && img.b64_json) {
    return `data:image/png;base64,${img.b64_json}`;
  }
  if (typeof img?.image_url === 'string' && img.image_url) return img.image_url;
  return null;
}

/** خواندن نتیجه از شکل‌های رایج پاسخ (`images[0]`, `data[0]`, `output[0]`) */
export function readAnyImage(payload: unknown): string | null {
  const fromOpenAi = readOpenAiImage(payload);
  if (fromOpenAi) return fromOpenAi;
  if (!payload || typeof payload !== 'object') return null;

  const record = payload as Record<string, unknown>;
  const candidates: unknown[] = [
    Array.isArray(record.images) ? record.images[0] : undefined,
    Array.isArray(record.output) ? record.output[0] : undefined,
    record.image,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate) return candidate;
    if (candidate && typeof candidate === 'object') {
      const item = candidate as Record<string, unknown>;
      for (const key of ['url', 'image_url', 'imageURL', 'b64_json', 'base64']) {
        const value = item[key];
        if (typeof value === 'string' && value) {
          return key === 'b64_json' || key === 'base64' ? `data:image/png;base64,${value}` : value;
        }
      }
    }
  }
  return null;
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
