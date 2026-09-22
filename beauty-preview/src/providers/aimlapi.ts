/**
 * src/providers/aimlapi.ts
 * ---------------------------------------------------------------------------
 * پروایدر ۳ — AIMLAPI
 *
 * مدل پیش‌فرض: blackforestlabs/flux-2-edit
 * برای image editing طراحی شده و image_urls را با URL یا Local Base64
 * می‌پذیرد؛ بنابراین برای عکس آپلودشدهٔ کاربر به CDN واسط نیاز نداریم.
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
const DEFAULT_MODEL = 'blackforestlabs/flux-2-edit';

function endpoint(): string {
  return (process.env.AIMLAPI_API_URL ?? '').trim() || DEFAULT_ENDPOINT;
}

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
): Promise<AttemptOutcome> {
  const { prompt, image } = input;
  const { signal, done } = timeoutSignal(timeoutFor(input));

  try {
    const body = {
      model: model(),
      prompt,
      image_urls: [image.dataUri],
      image_size: 'portrait_4_3',
      output_format: 'png',
      num_images: 1,
      enable_prompt_expansion: true,
      enable_safety_checker: true,
    };

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
        errorText:
          extractApiError(payload) ||
          raw.slice(0, 500) ||
          `HTTP ${res.status}`,
      };
    }

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
    if (!apiKey) {
      throw new ProviderError('AIMLAPI: کلید API تنظیم نشده است');
    }

    const result = await attempt(apiKey, input);

    if (result.url) return result.url;

    throw new ProviderError(
      `AIMLAPI ناموفق بود (HTTP ${result.status})`,
      result.errorText,
    );
  },
};
