/**
 * app/api/admin/stats/route.ts
 * ---------------------------------------------------------------------------
 * آمار پنل مدیریت (نیازمند توکن ورود):
 *
 *   GET /api/admin/stats            → آمار کامل + ۱۰ رویداد آخر
 *   GET /api/admin/stats?limit=50   → تعداد رویدادهای برگشتی
 *
 * پاسخ:
 *   {
 *     ok: true,
 *     visits, previews,               ← کل بازدید و کل پیش‌نمایش
 *     todayVisits, todayPreviews,     ← آمار امروز (به وقت محلی سرور)
 *     history: [ { type, style?, time } ],
 *     statsPath                        ← مسیر فایل آمار (برای نمایش در پنل)
 *   }
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { isAuthorized, unauthorizedResponse } from '@/admin-auth';
import { STATS_PATH, statsSummary } from '@/stats';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: Request): Promise<NextResponse> {
  if (!isAuthorized(request)) return unauthorizedResponse();

  const url = new URL(request.url);
  const limitParam = Number(url.searchParams.get('limit'));
  const limit = Number.isFinite(limitParam) && limitParam > 0 ? Math.min(limitParam, 300) : 10;

  const summary = await statsSummary(limit);

  return NextResponse.json({
    ok: true,
    visits: summary.visits,
    previews: summary.previews,
    todayVisits: summary.todayVisits,
    todayPreviews: summary.todayPreviews,
    today: summary.today,
    history: summary.history,
    statsPath: STATS_PATH,
  });
}
