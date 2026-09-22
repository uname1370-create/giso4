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
const MAX_OUTPUT_SIDE = 1536;
const MIN_OUTPUT_SIDE = 256;

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

/**
 * Keep the provider output in the same aspect ratio as the uploaded photo.
 * Cloudflare supports independent width/height values; the previous hard-coded
 * 1024x1024 forced portrait photos into a square output before Python saw them.
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
    // JPEG: find a SOF marker containing the frame dimensions.
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
      const { signal, done } = timeoutSignal(timeoutFor(input));

      try {
        const size = outputSize(new Uint8Array(input.image.bytes));
        const form = new FormData();
        form.append('prompt', input.prompt);
        form.append('width', String(size.width));
        form.append('height', String(size.height));
        form.append(
          'input_image_0',
          new Blob([new Uint8Array(input.image.bytes)], { type: input.image.mime }),
          `face.${input.image.extension}`,
        );

        // The customer photo is always image 0. When a style reference exists,
        // send it as image 1 so the image model can use it as a technique/style
        // reference without replacing the customer's identity or anatomy.
        if (input.referenceImage) {
          form.append(
            'input_image_1',
            new Blob(
              [new Uint8Array(input.referenceImage.bytes)],
              { type: input.referenceImage.mime },
            ),
            `brow-reference.${input.referenceImage.extension}`,
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
