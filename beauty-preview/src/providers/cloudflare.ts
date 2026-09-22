/**
 * Provider — Cloudflare Workers AI
 * Model: @cf/black-forest-labs/flux-2-klein-4b
 * Uses up to 3 independent Cloudflare accounts in order.
 */

import {
  ProviderError,
  extractApiError,
  timeoutFor,
  timeoutSignal,
} from './http';
import type { Provider, ProviderInput } from './types';

const DEFAULT_MODEL = '@cf/black-forest-labs/flux-2-klein-4b';

type CloudflareAccount = {
  token: string;
  accountId: string;
};

function model(): string {
  return (process.env.CLOUDFLARE_MODEL ?? '').trim() || DEFAULT_MODEL;
}

function accounts(): CloudflareAccount[] {
  return [1, 2, 3]
    .map((index) => ({
      token: (process.env[`CLOUDFLARE_API_TOKEN_${index}`] ?? '').trim(),
      accountId: (process.env[`CLOUDFLARE_ACCOUNT_ID_${index}`] ?? '').trim(),
    }))
    .filter((account) => account.token && account.accountId);
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
