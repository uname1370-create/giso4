/**
 * src/providers/aimlapi.ts
 * ---------------------------------------------------------------------------
 * پروایدر ۳ — AIMLAPI  (https://docs.aimlapi.com/)
 *
 * سازگار با فرمت OpenAI، اما تصویر ورودی با فیلد `image_url` فرستاده می‌شود
 * (نه آپلود فایل):
 *   POST https://api.aimlapi.com/v1/images/generations
 *   model: flux/kontext-pro/image-to-image
 *
 * اگر مدل با پارامتر `image_size` مخالفت کند، یک‌بار دیگر بدون آن تلاش می‌کنیم.
 * ---------------------------------------------------------------------------
 */

import {
  ProviderError,
  extractApiError,
  readAnyImage,
  readOpenAiImage,
  timeoutFor,
  timeoutSignal,
} from './http';
import type { Provider, ProviderInput } from './types';

const DEFAULT_ENDPOINT = 'https://api.aimlapi.com/v1/images/generations';
const DEFAULT_MODEL = 'flux/kontext-pro/image-to-image';

/** آدرس API (قابل تغییر با AIMLAPI_API_URL) */
function endpoint(): string {
  return (process.env.AIMLAPI_API_URL ?? '').trim() || DEFAULT_ENDPOINT;
}

/** مدل (قابل تغییر با AIMLAPI_MODEL) */
function model(): string {
  return (process.env.AIMLAPI_MODEL ?? '').trim() || DEFAULT_MODEL;
}

interface AttemptOutcome {
  url: string | null;
  status: number;
  errorText: string;
}

async function attempt(
  apiKey: string,
  input: ProviderInput,
  withImageSize: boolean,
): Promise<AttemptOutcome> {
  const { prompt, image } = input;
  const { signal, done } = timeoutSignal(timeoutFor(input));
  try {
    const body: Record<string, unknown> = {
      model: model(),
      prompt,
      image_url: image.dataUri,
    };
    if (withImageSize) body.image_size = '1024x1024';

    const res = await fetch(endpoint(), {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
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
      return {
        url: null,
        status: res.status,
        errorText: extractApiError(payload) || raw.slice(0, 300) || `HTTP ${res.status}`,
      };
    }

    // پاسخ‌های AIMLAPI می‌توانند در `images[0].url` یا `data[0].url` باشند
    return {
      url: readAnyImage(payload) ?? readOpenAiImage(payload),
      status: res.status,
      errorText: extractApiError(payload),
    };
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ProviderError('AIMLAPI: زمان انتظار به پایان رسید');
    }
    throw new ProviderError(
      'AIMLAPI ناموفق بود',
      error instanceof Error ? error.message : String(error),
    );
  } finally {
    done();
  }
}

export const aimlapiProvider: Provider = {
  id: 'aimlapi',
  label: 'AIMLAPI',
  envKey: 'AIMLAPI_API_KEY',

  async generate(input: ProviderInput): Promise<string> {
    const apiKey = (process.env.AIMLAPI_API_KEY ?? '').trim();
    if (!apiKey) throw new ProviderError('AIMLAPI: کلید API تنظیم نشده است');

    const first = await attempt(apiKey, input, true);
    if (first.url) return first.url;

    // اگر خطا مربوط به پارامترهای ورودی بود، بار دوم بدون image_size
    if (first.status === 400 || first.status === 422) {
      const second = await attempt(apiKey, input, false);
      if (second.url) return second.url;
      throw new ProviderError(`AIMLAPI ناموفق بود (HTTP ${second.status})`, second.errorText);
    }

    if (first.status === 0 || first.status >= 500) {
      throw new ProviderError(`AIMLAPI ناموفق بود (HTTP ${first.status})`, first.errorText);
    }

    throw new ProviderError(
      `AIMLAPI: هیچ تصویری دریافت نشد (HTTP ${first.status})`,
      first.errorText,
    );
  },
};
