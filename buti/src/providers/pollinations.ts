/**
 * src/providers/pollinations.ts
 * ---------------------------------------------------------------------------
 * پروایدر ۴ — Pollinations  (https://gen.pollinations.ai/docs)
 *
 * سازگار با فرمت OpenAI:
 *   POST https://gen.pollinations.ai/v1/images/edits
 *   model: openai/gpt-image-1-mini (ویرایش دقیق با دستورپذیری بالا برای لب/خط چشم، ~۰٫۰۰۸ pollen)
 *   کلید API با فرمت sk_XXXXXXXX از enter.pollinations.ai
 *
 * مسیر اصلی با SDK رسمی OpenAI (multipart) و مسیر پشتیبان با fetch و
 * FormData انجام می‌شود.
 * ---------------------------------------------------------------------------
 */

import OpenAI, { toFile } from 'openai';

import {
  ProviderError,
  extractApiError,
  readOpenAiImage,
  timeoutFor,
  timeoutSignal,
} from './http';
import type { Provider, ProviderInput } from './types';

const DEFAULT_BASE_URL = 'https://gen.pollinations.ai/v1';
const DEFAULT_MODEL = 'openai/gpt-image-1-mini';

/** آدرس پایه (قابل تغییر با POLLINATIONS_BASE_URL) */
function baseUrl(): string {
  return (process.env.POLLINATIONS_BASE_URL ?? '').trim() || DEFAULT_BASE_URL;
}

/** مدل (قابل تغییر با POLLINATIONS_MODEL) */
function model(): string {
  return (process.env.POLLINATIONS_MODEL ?? '').trim() || DEFAULT_MODEL;
}

function client(apiKey: string, timeoutMs: number): OpenAI {
  return new OpenAI({
    baseURL: baseUrl(),
    apiKey,
    timeout: timeoutMs,
    maxRetries: 0,
  });
}

/** مسیر پشتیبان: FormData خام روی همان endpoint ویرایش تصویر */
async function editWithFormData(apiKey: string, input: ProviderInput): Promise<string> {
  const { prompt, image } = input;
  const { signal, done } = timeoutSignal(timeoutFor(input));
  try {
    const form = new FormData();
    form.append('model', model());
    form.append('prompt', prompt);
    form.append('size', '1024x1024');
    form.append('response_format', 'b64_json');
    form.append(
      'image',
      new Blob([new Uint8Array(image.bytes)], { type: image.mime }),
      `face.${image.extension}`,
    );

    const res = await fetch(`${baseUrl()}/images/edits`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiKey}` },
      body: form,
      signal,
      cache: 'no-store',
    });

    const raw = await res.text();
    let payload: unknown = null;
    try {
      payload = raw ? JSON.parse(raw) : null;
    } catch {
      payload = null;
    }

    if (!res.ok) {
      throw new ProviderError(
        `Pollinations ناموفق بود (HTTP ${res.status})`,
        extractApiError(payload) || raw.slice(0, 300),
      );
    }

    const url = readOpenAiImage(payload);
    if (!url) throw new ProviderError('Pollinations: هیچ تصویری دریافت نشد');
    return url;
  } catch (error) {
    if (error instanceof ProviderError) throw error;
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ProviderError('Pollinations: زمان انتظار به پایان رسید');
    }
    throw new ProviderError(
      'Pollinations ناموفق بود',
      error instanceof Error ? error.message : String(error),
    );
  } finally {
    done();
  }
}

export const pollinationsProvider: Provider = {
  id: 'pollinations',
  label: 'Pollinations',
  envKey: 'POLLINATIONS_API_KEY',

  async generate(input: ProviderInput): Promise<string> {
    const apiKey = (process.env.POLLINATIONS_API_KEY ?? '').trim();
    if (!apiKey) throw new ProviderError('Pollinations: کلید API تنظیم نشده است');

    const { prompt, image } = input;

    try {
      const file = await toFile(image.bytes, `face.${image.extension}`, { type: image.mime });
      const response = await client(apiKey, timeoutFor(input)).images.edit({
        model: model(),
        image: file,
        prompt,
        size: '1024x1024',
      });

      const url = readOpenAiImage(response);
      if (url) return url;
      throw new ProviderError('Pollinations: پاسخ بدون تصویر بود');
    } catch (primaryError) {
      const status =
        primaryError && typeof primaryError === 'object'
          ? (primaryError as { status?: unknown }).status
          : undefined;
      const statusCode = typeof status === 'number' ? status : undefined;
      // خطای 4xx (به‌جز 429) با تلاش مجدد درست نمی‌شود — فوری شکست بخور تا کاربر معطل نشود.
      // (۴۰۲ یعنی موجودی Pollen کافی نیست؛ پیام API شامل موجودی و لینک شارژ است.)
      if (
        statusCode !== undefined &&
        statusCode >= 400 &&
        statusCode < 500 &&
        statusCode !== 429
      ) {
        const msg = primaryError instanceof Error ? primaryError.message : String(primaryError);
        throw new ProviderError(
          `Pollinations ناموفق بود (HTTP ${statusCode})`,
          msg.slice(0, 400),
        );
      }
      // 429 یعنی محدودیت نرخ لحظه‌ای: همان درخواست را بعد از مکث کوتاه تکرار کن
      // (طبق مستندات، نتیجه کش‌شده همان تولید برمی‌گردد، نه تولید دوباره و هزینه دوباره)
      if (statusCode === 429) {
        let waitMs = 3000;
        try {
          const headers = (primaryError as { headers?: { get?: (n: string) => string | null } })
            ?.headers;
          const ra = Number(headers?.get?.('retry-after'));
          if (Number.isFinite(ra) && ra > 0) waitMs = Math.min(ra * 1000, 10000);
        } catch {
          // همان ۳ ثانیه پیش‌فرض
        }
        console.error(`[AI-PROVIDER] pollinations 429 — retrying same request after ${waitMs}ms`);
        await new Promise((resolve) => setTimeout(resolve, waitMs));
      }
      try {
        return await editWithFormData(apiKey, input);
      } catch (fallbackError) {
        const first = primaryError instanceof Error ? primaryError.message : String(primaryError);
        const second =
          fallbackError instanceof Error ? fallbackError.message : String(fallbackError);
        throw new ProviderError('Pollinations ناموفق بود', `${first} | ${second}`.slice(0, 400));
      }
    }
  },
};
