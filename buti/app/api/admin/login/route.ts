/**
 * app/api/admin/login/route.ts
 * ---------------------------------------------------------------------------
 * ورود به پنل مدیریت:
 *
 *   POST /api/admin/login   { "password": "..." }
 *     ✅ 200 → { ok: true, token, expiresAt }
 *     ❌ 401 → { ok: false, error: "رمز عبور اشتباه است" }
 *     ❌ 429 → { ok: false, error: "تلاش‌های ناموفق زیاد..." }
 *
 * رمز عبور از متغیر محیطی ADMIN_PASSWORD خوانده می‌شود (پیش‌فرض «1234»).
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { adminPassword, createToken, safeCompare } from '@/admin-auth';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** محدودیت تلاش ناموفق: حداکثر ۱۰ خطا در هر ۱۰ دقیقه برای هر IP */
const MAX_ATTEMPTS = 10;
const ATTEMPT_WINDOW_MS = 10 * 60 * 1000;

const failedAttempts = new Map<string, { count: number; firstAt: number }>();

function clientIp(request: Request): string {
  const forwarded = request.headers.get('x-forwarded-for');
  if (forwarded) return forwarded.split(',')[0].trim();
  return request.headers.get('x-real-ip')?.trim() || 'unknown';
}

function isRateLimited(ip: string): boolean {
  const record = failedAttempts.get(ip);
  if (!record) return false;
  if (Date.now() - record.firstAt > ATTEMPT_WINDOW_MS) {
    failedAttempts.delete(ip);
    return false;
  }
  return record.count >= MAX_ATTEMPTS;
}

function registerFailure(ip: string): void {
  const record = failedAttempts.get(ip);
  if (!record || Date.now() - record.firstAt > ATTEMPT_WINDOW_MS) {
    failedAttempts.set(ip, { count: 1, firstAt: Date.now() });
    return;
  }
  record.count += 1;
}

export async function POST(request: Request): Promise<NextResponse> {
  const ip = clientIp(request);

  if (isRateLimited(ip)) {
    return NextResponse.json(
      { ok: false, error: 'تلاش‌های ناموفق زیاد بوده است. چند دقیقه بعد دوباره امتحان کنید.' },
      { status: 429 },
    );
  }

  let password = '';
  try {
    const body = (await request.json()) as { password?: unknown };
    if (typeof body?.password === 'string') password = body.password;
  } catch {
    return NextResponse.json(
      { ok: false, error: 'درخواست نامعتبر است.' },
      { status: 400 },
    );
  }

  if (!password) {
    return NextResponse.json(
      { ok: false, error: 'رمز عبور را وارد کنید.' },
      { status: 400 },
    );
  }

  if (!safeCompare(password, adminPassword())) {
    registerFailure(ip);
    return NextResponse.json({ ok: false, error: 'رمز عبور اشتباه است' }, { status: 401 });
  }

  // ورود موفق → پاک‌کردن شمارندهٔ خطاها
  failedAttempts.delete(ip);

  const { token, expiresAt } = createToken();
  return NextResponse.json({ ok: true, token, expiresAt });
}
