/**
 * app/api/providers/route.ts
 * ---------------------------------------------------------------------------
 * بررسی سلامت پروایدرها (فقط سمت سرور — کلیدها هرگز برنمی‌گردند):
 *
 *   GET /api/providers
 *      → فهرست پروایدرها، اینکه کلیدشان تنظیم شده یا نه، و فعال بودن حالت نمایشی
 *
 *   GET /api/providers?check=1
 *      → برای هر پروایدرِ دارای کلید، یک درخواست واقعی و کوچک (تصویر ۸×۸)
 *        می‌فرستد تا مطمئن شویم کلید کار می‌کند. خروجی: ok / ms / پیام خطا.
 *
 *   GET /api/providers?check=1&timeout=30000
 *      → مهلت هر بررسی (پیش‌فرض ۳۰ ثانیه)
 *
 * توجه: حالت check یک تصویر واقعی تولید می‌کند و ممکن است مقدار بسیار کمی از
 * اعتبار حساب شما مصرف شود؛ پس فقط وقتی لازم است از آن استفاده کنید.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { PROVIDERS } from '@/providers';
import { ProviderError, parseDataUri } from '@/providers/http';
import type { ProviderInput } from '@/providers/types';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

/** تصویر خیلی کوچک (۸×۸ پیکسل) برای تست سلامت کلیدها */
const CHECK_IMAGE_BASE64 =
  '/9j/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAAIAAgDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAABP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKEACY//2Q==';

const CHECK_PROMPT =
  'Apply professional microblading eyebrows in the style of Natural Hairstroke ' +
  'with color #8B6914 (Natural Brown) to this face photo. ' +
  'Keep everything else exactly the same. Realistic, natural, high quality beauty result.';

interface ProviderStatus {
  id: string;
  label: string;
  envKey: string;
  configured: boolean;
  ok?: boolean;
  ms?: number;
  error?: string;
}

function configuredList(): ProviderStatus[] {
  return PROVIDERS.map((provider) => ({
    id: provider.id,
    label: provider.label,
    envKey: provider.envKey,
    configured: (process.env[provider.envKey] ?? '').trim().length > 0,
  }));
}

function demoActive(): boolean {
  const mode = (process.env.DEMO_MODE ?? 'auto').trim().toLowerCase();
  if (mode === 'on' || mode === '1' || mode === 'true') return true;
  if (mode === 'off' || mode === '0' || mode === 'false') return false;
  return configuredList().every((provider) => !provider.configured);
}

export async function GET(request: Request): Promise<NextResponse> {
  const url = new URL(request.url);
  const shouldCheck = url.searchParams.get('check') === '1';
  const timeoutParam = Number(url.searchParams.get('timeout'));
  const timeoutMs = Number.isFinite(timeoutParam) && timeoutParam > 1000 ? timeoutParam : 30_000;

  const providers = configuredList();

  if (!shouldCheck) {
    return NextResponse.json({
      ok: true,
      demo: demoActive(),
      providers,
      hint: 'برای تست واقعی کلیدها: /api/providers?check=1',
    });
  }

  const image = parseDataUri(`data:image/jpeg;base64,${CHECK_IMAGE_BASE64}`);
  if (!image) {
    return NextResponse.json({ ok: false, error: 'تصویر تست نامعتبر است' }, { status: 500 });
  }

  // هر پروایدر جداگانه و به‌ترتیب (بدون زنجیرهٔ جایگزین) تست می‌شود
  for (const status of providers) {
    if (!status.configured) continue;

    const provider = PROVIDERS.find((item) => item.id === status.id);
    if (!provider) continue;

    const input: ProviderInput = { prompt: CHECK_PROMPT, image, timeoutMs };
    const startedAt = Date.now();

    try {
      const result = await provider.generate(input);
      status.ok = Boolean(result);
      status.ms = Date.now() - startedAt;
      if (!status.ok) status.error = 'پاسخ بدون تصویر بود';
    } catch (error) {
      status.ok = false;
      status.ms = Date.now() - startedAt;
      const message = error instanceof Error ? error.message : String(error);
      const detail = error instanceof ProviderError && error.detail ? ` — ${error.detail}` : '';
      status.error = `${message}${detail}`.slice(0, 400);
    }
  }

  const checked = providers.filter((provider) => provider.configured);
  const working = checked.filter((provider) => provider.ok);

  return NextResponse.json({
    ok: working.length > 0,
    demo: demoActive(),
    summary: `${working.length} از ${checked.length} پروایدر سالم است`,
    providers,
  });
}
