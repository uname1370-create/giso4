/**
 * src/providers/index.ts
 * ---------------------------------------------------------------------------
 * زنجیرهٔ رندر (تک‌پروایدر: Cloudflare سریع و کم‌مصرف):
 *
 *   Cloudflare → ۳ حساب مستقل → FLUX.2 Klein 4B (سریع؛ ~۱۴۰ رندر رایگان در روز)
 * شکست کامل سهمیه‌ای → پاسخ demo:true (به‌جای ۵۰۲) — مهلت هر تلاش ۱۵ ثانیه
 *
 * لاگ‌های تشخیصی فقط metadata و پیام خطا را ثبت می‌کنند؛ کلید API، تصویر و
 * محتوای base64 هرگز لاگ نمی‌شوند.
 * ---------------------------------------------------------------------------
 */

import { ProviderError, materializeImage } from './http';
import { cloudflareProvider } from './cloudflare';
import type { AttemptLog, Provider, ProviderInput } from './types';

const PROVIDERS_ALL: Provider[] = [cloudflareProvider];

/**
 * ترتیب مؤثر زنجیره از روی PROVIDER_ORDER (شناسه‌های ناشناخته نادیده گرفته می‌شوند).
 * شناسه‌های ناشناخته نادیده گرفته می‌شوند و جاافتاده‌ها به انتها اضافه می‌شوند.
 */
function providerOrder(): Provider[] {
  const raw = (process.env.PROVIDER_ORDER ?? '').trim().toLowerCase();
  if (!raw) return [...PROVIDERS_ALL];
  const byId = new Map(PROVIDERS_ALL.map((p) => [p.id, p]));
  const ordered: Provider[] = [];
  for (const id of raw.split(',')) {
    const provider = byId.get(id.trim());
    if (provider && !ordered.includes(provider)) ordered.push(provider);
  }
  for (const provider of PROVIDERS_ALL) {
    if (!ordered.includes(provider)) ordered.push(provider);
  }
  return ordered;
}

export const PROVIDERS: Provider[] = providerOrder();

export type { AttemptLog, Provider, ProviderInput };

export interface FallbackResult {
  provider: Provider;
  /** data URI (برای دانلود بدون مشکل CORS) یا آدرس اینترنتی */
  image: string;
  attempts: AttemptLog[];
  ms: number;
}

export function isProviderConfigured(provider: Provider): boolean {
  return provider.isConfigured ? provider.isConfigured() : (process.env[provider.envKey] ?? '').trim().length > 0;
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
