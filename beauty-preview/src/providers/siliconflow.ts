/**
 * SiliconFlow provider
 *
 * Image editing is performed through SiliconFlow's documented
 * /v1/images/generations endpoint with the FLUX.1-Kontext family.
 *
 * The request intentionally starts with the smallest documented payload:
 *   { model, prompt, image }
 *
 * Do not add OpenAI-style /images/edits fallback here.
 */

import {
  ProviderError,
  extractApiError,
  readAnyImage,
  timeoutFor,
  timeoutSignal,
} from './http';
import type { Provider, ProviderInput } from './types';

const DEFAULT_BASE_URL = 'https://api.siliconflow.com/v1';
const DEFAULT_MODEL = 'black-forest-labs/FLUX.1-Kontext-dev';

function baseUrl(): string {
  return (
    (process.env.SILICONFLOW_BASE_URL ?? '').trim().replace(/\/+$/, '') ||
    DEFAULT_BASE_URL
  );
}

function model(): string {
  return (process.env.SILICONFLOW_MODEL ?? '').trim() || DEFAULT_MODEL;
}

async function readJson(
  res: Response,
): Promise<{ payload: unknown; raw: string }> {
  const raw = await res.text();
  let payload: unknown = null;

  try {
    payload = raw ? JSON.parse(raw) : null;
  } catch {
    // SiliconFlow can return plain-text errors.
  }

  return { payload, raw };
}

function errorDetail(payload: unknown, raw: string): string {
  const fromJson = extractApiError(payload);
  if (fromJson) return fromJson;
  return (raw ?? '').replace(/^"|"$/g, '').trim().slice(0, 500);
}

async function viaGenerations(
  apiKey: string,
  input: ProviderInput,
): Promise<string> {
  const { signal, done } = timeoutSignal(timeoutFor(input));

  try {
    const res = await fetch(`${baseUrl()}/images/generations`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        model: model(),
        prompt: input.prompt,
        image: input.image.dataUri,
      }),
      signal,
      cache: 'no-store',
    });

    const { payload, raw } = await readJson(res);

    if (!res.ok) {
      const detail = errorDetail(payload, raw);

      if (res.status === 401) {
        throw new ProviderError(
          'SiliconFlow: کلید API نامعتبر است (401)',
          detail || 'Invalid token',
        );
      }

      if (res.status === 403) {
        throw new ProviderError(
          'SiliconFlow: دسترسی به مدل/حساب مجاز نیست (403)',
          detail || 'Forbidden',
        );
      }

      throw new ProviderError(
        `SiliconFlow ناموفق بود (HTTP ${res.status})`,
        detail || 'Unknown API error',
      );
    }

    const image = readAnyImage(payload);

    if (!image) {
      throw new ProviderError(
        'SiliconFlow: پاسخ موفق بود اما تصویر خروجی پیدا نشد',
        errorDetail(payload, raw) || 'Missing image in response',
      );
    }

    return image;
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

    if (!apiKey) {
      throw new ProviderError(
        'SiliconFlow: کلید API تنظیم نشده است',
      );
    }

    return viaGenerations(apiKey, input);
  },
};
