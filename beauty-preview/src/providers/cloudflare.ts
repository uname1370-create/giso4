/**
 * Provider — Cloudflare Workers AI
 * Model: @cf/black-forest-labs/flux-2-klein-4b (پیش‌فرض سریع و کم‌مصرف؛ مدل dev با CLOUDFLARE_MODEL)
 * Uses up to 3 independent Cloudflare accounts in order.
 */

import {
  ProviderError,
  extractApiError,
  timeoutSignal,
} from './http';
import type { Provider, ProviderInput } from './types';

const DEFAULT_MODEL = '@cf/black-forest-labs/flux-2-klein-4b';
/** مهلت هر حساب کلادفلر: ۱۵ ثانیه — رندر سالم klein سریع است؛ بیشتر یعنی صف/اختلال. */
const DEFAULT_TIMEOUT_MS = 15_000;
const MAX_OUTPUT_SIDE = 1536;
const MIN_OUTPUT_SIDE = 256;

type CloudflareAccount = {
  token: string;
  accountId: string;
};

function model(): string {
  return (process.env.CLOUDFLARE_MODEL ?? '').trim() || DEFAULT_MODEL;
}

/**
 * مهلت مؤثر کلادفلر: ورودی timeoutMs (تست سلامت) بر همه مقدم است،
 * بعد CLOUDFLARE_TIMEOUT_MS، وگرنه ۱۵ ثانیه (fail-fast به‌جای معطلی چنددقیقه‌ای).
 */
function cloudflareTimeoutMs(input?: { timeoutMs?: number }): number {
  const custom = Number(input?.timeoutMs);
  if (Number.isFinite(custom) && custom > 1000) return custom;
  const raw = Number(process.env.CLOUDFLARE_TIMEOUT_MS);
  return Number.isFinite(raw) && raw > 1000 ? raw : DEFAULT_TIMEOUT_MS;
}

function accounts(): CloudflareAccount[] {
  return [1, 2, 3]
    .map((index) => ({
      token: (process.env[`CLOUDFLARE_API_TOKEN_${index}`] ?? '').trim(),
      accountId: (process.env[`CLOUDFLARE_ACCOUNT_ID_${index}`] ?? '').trim(),
    }))
    .filter((account) => account.token && account.accountId);
}

/** سقف رسمی ورودی مدل klein: همهٔ تصاویر ورودی باید کوچک‌تر از ۵۱۲×۵۱۲ باشند. */
const MAX_INPUT_SIDE = 512;

/**
 * تبعیت از پرامپت (پیش‌فرض ۵؛ با CLOUDFLARE_GUIDANCE قابل تنظیم).
 * طبق مستندات کلادفلر، guidance بالاتر یعنی تبعیت بیشتر از پرامپت —
 * دقیقاً همان چیزی که تمایز مدل‌ها به آن نیاز دارد.
 */
function guidance(): string {
  const raw = Number(process.env.CLOUDFLARE_GUIDANCE);
  if (Number.isFinite(raw) && raw > 0 && raw <= 20) return String(raw);
  return '5';
}

type SharpChain = {
  metadata: () => Promise<{ width?: number; height?: number }>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  resize: (width: number, height: number, opts: Record<string, unknown>) => any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  extract: (region: { left: number; top: number; width: number; height: number }) => any;
  jpeg: (opts: Record<string, unknown>) => { toBuffer: () => Promise<Buffer> };
};

type SharpFn = (input: Buffer) => SharpChain;

/** لود واقعاً اختیاری sharp (همان الگوی fail-open در src/image-compress.ts) */
function loadSharp(): SharpFn | null {
  try {
    // eslint-disable-next-line no-eval
    const nodeRequire = eval('require') as (id: string) => unknown;
    return nodeRequire('sharp') as SharpFn;
  } catch {
    return null;
  }
}

interface FittedInput {
  bytes: Buffer;
  mime: string;
  extension: string;
}

/**
 * آماده‌سازی ورودی طبق سقف رسمی klein (کوچک‌تر از ۵۱۲×۵۱۲):
 * - عکس مشتری (photo): کوچک‌سازی ضلع بزرگ به ۵۱۲ با حفظ نسبت تصویر.
 * - رفرنس تکنیک (macro): کراپ مربع مرکزی + خروجی ۵۱۲×۵۱۲ — ماکروی واقعی
 *   ناحیهٔ تکنیک تا مدل به‌جای کل صحنه، بافت تار/پیگمنت را ببیند.
 * بدون sharp یا در هر خطایی → همان بایت اصلی برگردانده می‌شود (fail-open).
 */
/** اکسپورت برای تست تشخیصی (همان منطق مصرفی در مسیر تولید) */
export async function fitInputImage(
  bytes: Buffer,
  mime: string,
  extension: string,
  mode: 'photo' | 'macro',
): Promise<FittedInput> {
  const original: FittedInput = { bytes, mime, extension };
  try {
    const sharp = loadSharp();
    if (!sharp) return original;
    const meta = await sharp(bytes).metadata();
    const width = meta.width ?? 0;
    const height = meta.height ?? 0;
    if (!width || !height) return original;

    if (mode === 'macro') {
      const side = Math.min(width, height);
      const out: Buffer = await sharp(bytes)
        .extract({
          left: Math.floor((width - side) / 2),
          top: Math.floor((height - side) / 2),
          width: side,
          height: side,
        })
        .resize(MAX_INPUT_SIDE, MAX_INPUT_SIDE, { fit: 'fill' })
        .jpeg({ quality: 92 })
        .toBuffer();
      return { bytes: out, mime: 'image/jpeg', extension: 'jpg' };
    }

    if (Math.max(width, height) <= MAX_INPUT_SIDE) return original;
    const out: Buffer = await sharp(bytes)
      .resize(MAX_INPUT_SIDE, MAX_INPUT_SIDE, { fit: 'inside', withoutEnlargement: true })
      .jpeg({ quality: 92 })
      .toBuffer();
    return { bytes: out, mime: 'image/jpeg', extension: 'jpg' };
  } catch (error) {
    console.error(
      `[AI-PROVIDER] cloudflare input-fit skipped: ${
        error instanceof Error ? error.message : String(error)
      }`.slice(0, 160),
    );
    return original;
  }
}

/**
 * Keep the provider output in the same aspect ratio as the uploaded photo.
 */
function outputSize(bytes: Uint8Array): { width: number; height: number } {
  const view = bytes;
  let width = 1024;
  let height = 1024;

  // PNG
  if (
    view.length >= 24 &&
    view[0] === 0x89 && view[1] === 0x50 && view[2] === 0x4e &&
    view[3] === 0x47 && view[4] === 0x0d && view[5] === 0x0a &&
    view[6] === 0x1a && view[7] === 0x0a
  ) {
    width = (view[16] << 24) | (view[17] << 16) | (view[18] << 8) | view[19];
    height = (view[20] << 24) | (view[21] << 16) | (view[22] << 8) | view[23];
  } else if (view.length >= 2 && view[0] === 0xff && view[1] === 0xd8) {
    let offset = 2;
    while (offset + 9 < view.length) {
      if (view[offset] !== 0xff) {
        offset += 1;
        continue;
      }
      const marker = view[offset + 1];
      offset += 2;
      if (marker === 0xd8 || marker === 0xd9) continue;
      if (offset + 2 > view.length) break;
      const segmentLength = (view[offset] << 8) | view[offset + 1];
      if (segmentLength < 2 || offset + segmentLength > view.length) break;
      const isSof =
        marker >= 0xc0 && marker <= 0xc3 ||
        marker >= 0xc5 && marker <= 0xc7 ||
        marker >= 0xc9 && marker <= 0xcb ||
        marker >= 0xcd && marker <= 0xcf;
      if (isSof && offset + 7 < view.length) {
        height = (view[offset + 3] << 8) | view[offset + 4];
        width = (view[offset + 5] << 8) | view[offset + 6];
        break;
      }
      offset += segmentLength;
    }
  }

  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return { width: 1024, height: 1024 };
  }

  const scale = MAX_OUTPUT_SIDE / Math.max(width, height);
  let outWidth = Math.round((width * Math.min(1, scale)) / 8) * 8;
  let outHeight = Math.round((height * Math.min(1, scale)) / 8) * 8;

  outWidth = Math.max(MIN_OUTPUT_SIDE, Math.min(MAX_OUTPUT_SIDE, outWidth));
  outHeight = Math.max(MIN_OUTPUT_SIDE, Math.min(MAX_OUTPUT_SIDE, outHeight));

  return { width: outWidth, height: outHeight };
}

export const cloudflareProvider: Provider = {
  id: 'cloudflare',
  label: 'Cloudflare — FLUX.2 Klein 4B',
  envKey: 'CLOUDFLARE_API_TOKEN_1',
  isConfigured: () => accounts().length > 0,

  async generate(input: ProviderInput): Promise<string> {
    const configuredAccounts = accounts();
    if (configuredAccounts.length === 0) {
      throw new ProviderError('Cloudflare: هیچ‌کدام از ۳ حساب تنظیم نشده است');
    }

    let lastError: unknown = null;

    for (let index = 0; index < configuredAccounts.length; index += 1) {
      const account = configuredAccounts[index];
      const accountNumber = index + 1;
      const { signal, done } = timeoutSignal(cloudflareTimeoutMs(input));

      try {
        const size = outputSize(new Uint8Array(input.image.bytes));
        const form = new FormData();

        // یادآوری کوتاه نقش تصاویر (جزئیات کامل در خود پرامپت هست — تکرار نمی‌کنیم)
        const enhancedPrompt = `${input.prompt} ROLE: IMAGE 0 is the customer-face authority; IMAGE 1 (if any) is a technique swatch only — never copy its face or skin.`;

        // ورودی‌ها در سقف رسمی ۵۱۲ پیکسل آماده می‌شوند (رقیق‌سازی کمتر + آپلود سریع‌تر)
        const fittedPhoto = await fitInputImage(
          Buffer.from(input.image.bytes),
          input.image.mime,
          input.image.extension,
          'photo',
        );

        form.append('prompt', enhancedPrompt);
        form.append('guidance', guidance());
        form.append('width', String(size.width));
        form.append('height', String(size.height));
        form.append(
          'input_image_0',
          new Blob([new Uint8Array(fittedPhoto.bytes)], { type: fittedPhoto.mime }),
          `customer-face.${fittedPhoto.extension}`,
        );

        if (input.referenceImage) {
          const fittedRef = await fitInputImage(
            Buffer.from(input.referenceImage.bytes),
            input.referenceImage.mime,
            input.referenceImage.extension,
            'macro',
          );
          form.append(
            'input_image_1',
            new Blob([new Uint8Array(fittedRef.bytes)], { type: fittedRef.mime }),
            `technique-macro.${fittedRef.extension}`,
          );
        }

        const res = await fetch(
          `https://api.cloudflare.com/client/v4/accounts/${account.accountId}/ai/run/${model()}`,
          {
            method: 'POST',
            headers: { Authorization: `Bearer ${account.token}` },
            body: form,
            signal,
            cache: 'no-store',
          },
        );

        const raw = await res.text();
        let payload: unknown = null;
        try {
          payload = raw ? JSON.parse(raw) : null;
        } catch {
          payload = null;
        }

        if (!res.ok) {
          throw new ProviderError(
            `Cloudflare حساب ${accountNumber} ناموفق بود (HTTP ${res.status})`,
            extractApiError(payload) || raw.slice(0, 500),
          );
        }

        const result = payload && typeof payload === 'object'
          ? (payload as Record<string, unknown>).result
          : null;
        const base64 =
          typeof result === 'string'
            ? result
            : result && typeof result === 'object' && typeof (result as Record<string, unknown>).image === 'string'
              ? (result as Record<string, unknown>).image as string
              : null;

        if (!base64) {
          throw new ProviderError(
            `Cloudflare حساب ${accountNumber}: پاسخ موفق بود اما تصویر خروجی پیدا نشد`,
            extractApiError(payload) || raw.slice(0, 500),
          );
        }

        return base64.startsWith('data:') ? base64 : `data:image/png;base64,${base64}`;
      } catch (error) {
        lastError = error;
        if (error instanceof Error && error.name === 'AbortError') {
          lastError = new ProviderError(`Cloudflare حساب ${accountNumber}: زمان انتظار به پایان رسید`);
        }
      } finally {
        done();
      }
    }

    if (lastError instanceof ProviderError) {
      throw new ProviderError(
        'Cloudflare: هر ۳ حساب ناموفق بودند',
        lastError.detail || lastError.message,
      );
    }

    throw new ProviderError(
      'Cloudflare: هر ۳ حساب ناموفق بودند',
      lastError instanceof Error ? lastError.message : String(lastError),
    );
  },
};
