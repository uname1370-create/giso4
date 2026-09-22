/**
 * src/providers/index.ts
 * ---------------------------------------------------------------------------
 * زنجیرهٔ جایگزین پروایدرها:
 *
 *   ۱) OpenRouter   → OPENROUTER_API_KEY → FLUX.2 Klein 4B
 *   ۲) Cloudflare   → CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID → FLUX.2 Klein 4B
 *   ۳) Pollinations → POLLINATIONS_API_KEY
 *
 * هر پروایدر بدون کلید رد می‌شود و در صورت خطا، پروایدر بعدی امتحان می‌شود.
 * لاگ‌های تشخیصی فقط metadata و پیام خطا را ثبت می‌کنند؛ کلید API، تصویر و
 * محتوای base64 هرگز لاگ نمی‌شوند.
 * ---------------------------------------------------------------------------
 */

import { ProviderError, materializeImage } from './http';
import { cloudflareProvider } from './cloudflare';
import { openrouterProvider } from './openrouter';
import { pollinationsProvider } from './pollinations';
import type { AttemptLog, Provider, ProviderInput } from './types';

export const PROVIDERS: Provider[] = [
  openrouterProvider,
  cloudflareProvider,
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

function logProvider(
  provider: Provider,
  event: 'START' | 'SKIP' | 'SUCCESS' | 'FAILED',
  details?: string,
): void {
  const suffix = details ? ` | ${details.slice(0, 500)}` : '';
  console.error(`[AI-PROVIDER] ${provider.id} ${event}${suffix}`);
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
      logProvider(provider, 'SKIP', 'API key not configured');
      continue;
    }

    const attemptStart = Date.now();
    logProvider(provider, 'START');

    try {
      const image = await provider.generate(input);
      const remote = await materializeImage(image);
      const duration = Date.now() - attemptStart;

      attempts.push({
        provider: provider.id,
        label: provider.label,
        ok: true,
        ms: duration,
      });

      logProvider(provider, 'SUCCESS', `duration=${duration}ms`);

      return {
        provider,
        image: remote,
        attempts,
        ms: Date.now() - startedAt,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const detail =
        error instanceof ProviderError && error.detail ? error.detail.slice(0, 500) : '';
      const duration = Date.now() - attemptStart;
      const attemptError = detail ? `${message} — ${detail}` : message;

      attempts.push({
        provider: provider.id,
        label: provider.label,
        ok: false,
        ms: duration,
        error: attemptError,
      });

      logProvider(
        provider,
        'FAILED',
        `duration=${duration}ms | ${attemptError}`,
      );
      // سراغ پروایدر بعدی می‌رویم
    }
  }

  const summary = attempts
    .filter((attempt) => attempt.error && attempt.error !== 'کلید API تنظیم نشده است (skip)')
    .map((attempt) => `${attempt.label}: ${attempt.error}`)
    .join(' • ');

  const totalMs = Date.now() - startedAt;
  console.error(
    `[AI-PROVIDER] ALL_FAILED | providers=${attempts.length} | duration=${totalMs}ms`,
  );

  throw Object.assign(
    new Error('هیچ‌کدام از سرویس‌های هوش مصنوعی پاسخ ندادند' + (summary ? ` — ${summary}` : '')),
    { attempts },
  );
}
