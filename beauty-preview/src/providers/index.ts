/**
 * src/providers/index.ts
 * ---------------------------------------------------------------------------
 * زنجیرهٔ جایگزین ۴ پروایدری (4-provider fallback):
 *
 *   ۱) Runware      → RUNWARE_API_KEY      (غیر OpenAI — آرایهٔ JSON)
 *   ۲) SiliconFlow  → SILICONFLOW_API_KEY  (images/edits + SDK)
 *   ۳) AIMLAPI      → AIMLAPI_API_KEY      (image_url)
 *   ۴) Pollinations → POLLINATIONS_API_KEY (images/edits + SDK)
 *
 * هر پروایدری که کلیدش خالی باشد رد می‌شود و در صورت خطا، پروایدر بعدی
 * امتحان می‌شود. همهٔ فراخوانی‌ها فقط سمت سرور انجام می‌شوند.
 * ---------------------------------------------------------------------------
 */

import { aimlapiProvider } from './aimlapi';
import { ProviderError, materializeImage } from './http';
import { pollinationsProvider } from './pollinations';
import { runwareProvider } from './runware';
import { siliconflowProvider } from './siliconflow';
import type { AttemptLog, Provider, ProviderInput } from './types';

export const PROVIDERS: Provider[] = [
  runwareProvider,
  siliconflowProvider,
  aimlapiProvider,
  pollinationsProvider,
];

export type { AttemptLog, Provider, ProviderInput };

export interface FallbackResult {
  provider: Provider;
  /** data URI (برای دانلود بدون مشکل CORS) یا آدرس اینترنتی */
  image: string;
  attempts: AttemptLog[];
  ms: number;
}

export function isProviderConfigured(provider: Provider): boolean {
  return (process.env[provider.envKey] ?? '').trim().length > 0;
}

export function configuredProviders(): Provider[] {
  return PROVIDERS.filter(isProviderConfigured);
}

/**
 * اجرای زنجیرهٔ جایگزین تا اولین موفقیت.
 * اگر همه شکست بخورند، خطایی با خلاصهٔ تلاش‌ها پرتاب می‌شود.
 */
export async function generateWithFallback(input: ProviderInput): Promise<FallbackResult> {
  const startedAt = Date.now();
  const attempts: AttemptLog[] = [];

  for (const provider of PROVIDERS) {
    if (!isProviderConfigured(provider)) {
      attempts.push({
        provider: provider.id,
        label: provider.label,
        ok: false,
        ms: 0,
        error: 'کلید API تنظیم نشده است (skip)',
      });
      continue;
    }

    const attemptStart = Date.now();
    try {
      const image = await provider.generate(input);
      const remote = await materializeImage(image);

      attempts.push({
        provider: provider.id,
        label: provider.label,
        ok: true,
        ms: Date.now() - attemptStart,
      });

      return {
        provider,
        image: remote,
        attempts,
        ms: Date.now() - startedAt,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const detail =
        error instanceof ProviderError && error.detail ? ` — ${error.detail.slice(0, 220)}` : '';

      attempts.push({
        provider: provider.id,
        label: provider.label,
        ok: false,
        ms: Date.now() - attemptStart,
        error: `${message}${detail}`,
      });
      // سراغ پروایدر بعدی می‌رویم
    }
  }

  const summary = attempts
    .filter((attempt) => attempt.error && attempt.error !== 'کلید API تنظیم نشده است (skip)')
    .map((attempt) => `${attempt.label}: ${attempt.error}`)
    .join(' • ');

  throw Object.assign(
    new Error('هیچ‌کدام از سرویس‌های هوش مصنوعی پاسخ ندادند' + (summary ? ` — ${summary}` : '')),
    { attempts },
  );
}
