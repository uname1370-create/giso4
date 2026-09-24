/**
 * app/api/site-image/[...path]/route.ts
 * ---------------------------------------------------------------------------
 * سرو کردن تصاویر آپلودشده از پنل مدیریت:
 *
 *     GET /api/site-image/eyebrows/feather.jpg       ← تصویر مدل ابرو
 *     GET /api/site-image/eyebrows/ombre-powder.jpg
 *     GET /api/site-image/hero/hero                  ← تصویر هیرو (هر فرمتی که آپلود شده)
 *     GET /api/site-image/hero/hero.jpg
 *
 * چرا از public/ مستقیم سرو نمی‌شوند؟
 *   سرور production نکست، فهرست پوشهٔ public را فقط یک بار در زمان بالا آمدن
 *   می‌خواند؛ بنابراین فایلی که مدیر بعد از استارت آپلود کند تا ری‌استارت سرور
 *   ۴۰۴ می‌دهد. این روت در هر درخواست فایل را از دیسک می‌خواند؛ نتیجه اینکه
 *   آپلود در حالت dev و production بلافاصله روی صفحهٔ اصلی دیده می‌شود.
 *
 * امنیت: فقط نام‌های ثابت از پیش تعیین‌شده (src/site-images.ts → resolveSiteImage)
 * پذیرفته می‌شوند و مسیر نهایی باید داخل public بماند (بدون path traversal).
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { readSiteImage } from '@/site-images';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(
  _request: Request,
  context: { params: { path?: string[] } },
): Promise<NextResponse | Response> {
  const segments = context.params?.path ?? [];
  const file = await readSiteImage(segments.join('/'));

  if (!file) {
    return NextResponse.json({ ok: false, error: 'تصویر پیدا نشد' }, { status: 404 });
  }

  return new Response(new Uint8Array(file.buffer), {
    status: 200,
    headers: {
      'Content-Type': file.mime,
      'Content-Length': String(file.buffer.length),
      // تصویر ممکن است هر لحظه از پنل عوض یا حذف شود؛ پس هیچ کش طولانی‌مدتی نمی‌گذاریم
      'Cache-Control': 'no-cache, no-store, must-revalidate',
    },
  });
}
