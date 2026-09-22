/**
 * src/providers/siliconflow.ts
 * ---------------------------------------------------------------------------
 * پروایدر ۲ — SiliconFlow  (http://docs.siliconflow.com/)
 *
 * سازگار با فرمت OpenAI:
 *   ۱) مسیر اصلی: POST /v1/images/edits با SDK رسمی OpenAI و آپلود فایل
 *      (multipart) — مدل Qwen/Qwen-Image-Edit
 *   ۲) مسیر جایگزین (مستند رسمی SiliconFlow): POST /v1/images/generations
 *      با بدنهٔ JSON و فیلد `image` به‌صورت data URI
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

const DEFAULT_BASE_URL = 'https://api.siliconflow.cn/v1';
const DEFAULT_MODEL = 'Qwen/Qwen-Image-Edit';

/** آدرس پایه (قابل تغییر با SILICONFLOW_BASE_URL) */
function baseUrl(): string {
  return (process.env.SILICONFLOW_BASE_URL ?? '').trim() || DEFAULT_BASE_URL;
}

/** مدل (قابل تغییر با SILICONFLOW_MODEL) */
function model(): string {
  return (process.env.SILICONFLOW_MODEL ?? '').trim() || DEFAULT_MODEL;
}

function client(apiKey: string, timeoutMs: number): OpenAI {
  return new OpenAI({
    baseURL: baseUrl(),
    apiKey,
    timeout: timeoutMs,
    maxRetries: 0,
  });
}

/** مسیر جایگزین: generations با فیلد image */
async function generateViaJson(apiKey: string, input: ProviderInput): Promise<string> {
  const { prompt, image } = input;
  const { signal, done } = timeoutSignal(timeoutFor(input));
  try {
    const res = await fetch(`${baseUrl()}/images/generations`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: model(),
        prompt,
        image: image.dataUri,
        batch_size: 1,
        num_inference_steps: 20,
      }),
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
        `SiliconFlow ناموفق بود (HTTP ${res.status})`,
        extractApiError(payload) || raw.slice(0, 300),
      );
    }

    const url = readOpenAiImage(payload);
    if (!url) {
      throw new ProviderError(
        'SiliconFlow: هیچ تصویری دریافت نشد',
        extractApiError(payload) || raw.slice(0, 300),
      );
    }
    return url;
  } catch (error) {
    if (error instanceof ProviderError) throw error;
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ProviderError('SiliconFlow: زمان انتظار به پایان رسید');
    }
    throw new ProviderError(
      'SiliconFlow ناموفق بود',
      error instanceof Error ? error.message : String(error),
    );
  } finally {
    done();
  }
}

export const siliconflowProvider: Provider = {
  id: 'siliconflow',
  label: 'SiliconFlow',
  envKey: 'SILICONFLOW_API_KEY',

  async generate(input: ProviderInput): Promise<string> {
    const apiKey = (process.env.SILICONFLOW_API_KEY ?? '').trim();
    const timeoutMs = timeoutFor(input);
    if (!apiKey) throw new ProviderError('SiliconFlow: کلید API تنظیم نشده است');

    const { prompt, image } = input;

    // مسیر ۱ — ویرایش تصویر با SDK (multipart/form-data)
    try {
      const file = await toFile(image.bytes, `face.${image.extension}`, { type: image.mime });
      const response = await client(apiKey, timeoutMs).images.edit({
        model: model(),
        image: file,
        prompt,
      });

      const url = readOpenAiImage(response);
      if (url) return url;
      throw new ProviderError('SiliconFlow: پاسخ بدون تصویر بود');
    } catch (primaryError) {
      // مسیر ۲ — در صورت شکست مسیر اول، از مستندات جایگزین استفاده می‌کنیم
      try {
        return await generateViaJson(apiKey, input);
      } catch (fallbackError) {
        const first = primaryError instanceof Error ? primaryError.message : String(primaryError);
        const second =
          fallbackError instanceof Error ? fallbackError.message : String(fallbackError);
        throw new ProviderError('SiliconFlow ناموفق بود', `${first} | ${second}`.slice(0, 400));
      }
    }
  },
};
