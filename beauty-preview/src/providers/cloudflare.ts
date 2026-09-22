/**
 * Provider — Cloudflare Workers AI
 * Model: @cf/black-forest-labs/flux-2-klein-4b
 * Official contract: multipart/form-data with input_image_0..3.
 */

import {
  ProviderError,
  extractApiError,
  timeoutFor,
  timeoutSignal,
} from './http';
import type { Provider, ProviderInput } from './types';

const DEFAULT_MODEL = '@cf/black-forest-labs/flux-2-klein-4b';

function model(): string {
  return (process.env.CLOUDFLARE_MODEL ?? '').trim() || DEFAULT_MODEL;
}

export const cloudflareProvider: Provider = {
  id: 'cloudflare',
  label: 'Cloudflare — FLUX.2 Klein 4B',
  envKey: 'CLOUDFLARE_API_TOKEN',

  async generate(input: ProviderInput): Promise<string> {
    const token = (process.env.CLOUDFLARE_API_TOKEN ?? '').trim();
    const accountId = (process.env.CLOUDFLARE_ACCOUNT_ID ?? '').trim();
    if (!token) throw new ProviderError('Cloudflare: API Token تنظیم نشده است');
    if (!accountId) throw new ProviderError('Cloudflare: Account ID تنظیم نشده است');

    const { signal, done } = timeoutSignal(timeoutFor(input));
    try {
      const form = new FormData();
      form.append('prompt', input.prompt);
      form.append('width', '1024');
      form.append('height', '1024');
      form.append(
        'input_image_0',
        new Blob([new Uint8Array(input.image.bytes)], { type: input.image.mime }),
        `face.${input.image.extension}`,
      );

      const res = await fetch(
        `https://api.cloudflare.com/client/v4/accounts/${accountId}/ai/run/${encodeURIComponent(model())}`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
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
          `Cloudflare ناموفق بود (HTTP ${res.status})`,
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
          'Cloudflare: پاسخ موفق بود اما تصویر خروجی پیدا نشد',
          extractApiError(payload) || raw.slice(0, 500),
        );
      }

      return base64.startsWith('data:') ? base64 : `data:image/png;base64,${base64}`;
    } catch (error) {
      if (error instanceof ProviderError) throw error;
      if (error instanceof Error && error.name === 'AbortError') {
        throw new ProviderError('Cloudflare: زمان انتظار به پایان رسید');
      }
      throw new ProviderError(
        'Cloudflare ناموفق بود',
        error instanceof Error ? error.message : String(error),
      );
    } finally {
      done();
    }
  },
};
