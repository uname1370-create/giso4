/**
 * app/api/track/route.ts
 * ---------------------------------------------------------------------------
 * ثبت «بازدید» صفحهٔ اصلی (رویداد preview هنگام ساخت پیش‌نمایش، سمت سرور و
 * در app/api/generate ثبت می‌شود).
 *
 *   POST /api/track   { "type": "visit" }
 *
 * محافظت‌ها:
 *   - فقط نوع «visit» پذیرفته می‌شود.
 *   - هر IP حداکثر یک بازدید در هر ۶ ساعت ثبت می‌کند (ضد اسپم ساده).
 *   - خطاها هرگز به کاربر نمایش داده نمی‌شوند (این روت نباید تجربهٔ کاربر را
 *     خراب کند).
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { recordEvent } from '@/stats';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** فاصلهٔ مجاز بین دو بازدید از یک IP */
const VISIT_WINDOW_MS = 6 * 60 * 60 * 1000;

/** آخرین زمان ثبت بازدید به تفکیک IP (فقط در حافظهٔ پروسه) */
const lastVisitByIp = new Map<string, number>();

function clientIp(request: Request): string {
  const forwarded = request.headers.get('x-forwarded-for');
  if (forwarded) return forwarded.split(',')[0].trim();
  return request.headers.get('x-real-ip')?.trim() || 'unknown';
}

function prune(now: number): void {
  if (lastVisitByIp.size < 500) return;
  for (const [ip, time] of lastVisitByIp) {
    if (now - time > VISIT_WINDOW_MS) lastVisitByIp.delete(ip);
  }
}

export async function POST(request: Request): Promise<NextResponse> {
  let type = 'visit';
  try {
    const body = (await request.json()) as { type?: unknown };
    if (typeof body?.type === 'string') type = body.type;
  } catch {
    // بدنهٔ خالی هم قبول است → پیش‌فرض visit
  }

  if (type !== 'visit') {
    return NextResponse.json({ ok: false, ignored: true }, { status: 200 });
  }

  const now = Date.now();
  const ip = clientIp(request);
  const previous = lastVisitByIp.get(ip);
  if (previous && now - previous < VISIT_WINDOW_MS) {
    // بازدید تکراری — دوباره شمرده نمی‌شود
    return NextResponse.json({ ok: true, counted: false });
  }

  lastVisitByIp.set(ip, now);
  prune(now);

  const stats = await recordEvent({ type: 'visit', time: new Date().toISOString() });
  return NextResponse.json({ ok: true, counted: true, visits: stats.visits });
}
