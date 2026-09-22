/**
 * app/api/site-image/[...path]/route.ts
 * ---------------------------------------------------------------------------
 * سرو کردن تصاویر آپولودی پنل مدیریت:
 *
 *     GET /api/site-image/hero/hero-1712.jpg
 *     GET /api/site-image/eyebrows/hairstroke-1712.jpg
 *
 * چرا از public/ مستقیم سرو نمی‌شوند؟
 *   سرور production نکست، فهرست پوشهٔ public را فقط یک بار در زمان بالا آمدن
 *   می‌خواند؛ بنابراین فایلی که مدیر بعد از استارت آپلود کند تا ری‌استارت سرور
 *   ۴۰۴ می‌دهد. این روت فایل را در هر درخواست از دیسک می‌خواند؛ نتیجه اینکه
 *   آپلود در حالت dev و production بلافاصله روی صفحهٔ اصلی دیده می‌شود.
 *
 * امنیت: فقط دو پوشهٔ eyebrows و hero و نام‌های امن فایل پذیرفته می‌شوند
 * (src/site-images.ts → resolveUploadPath) و مسیر نهایی باید داخل public بماند.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { readUpload } from '@/site-images';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(
  _request: Request,
  context: { params: { path?: string[] } },
): Promise<NextResponse | Response> {
  const segments = context.params?.path ?? [];
  // مسیر ذخیره‌شده در فهرست تصاویر همیشه شکل «/<folder>/<file>» دارد.
  const url = `/${segments.join('/')}`;

  const file = await readUpload(url);
  if (!file) {
    return NextResponse.json({ ok: false, error: 'تصویر پیدا نشد' }, { status: 404 });
  }

  return new Response(new Uint8Array(file.buffer), {
    status: 200,
    headers: {
      'Content-Type': file.mime,
      'Content-Length': String(file.buffer.length),
      // نام فایل شامل timestamp است، پس محتوایش تغییر نمی‌کند؛ اما چون ممکن است
      // مدیر تصویر را حذف کند، کش طولانی نمی‌گذاریم.
      'Cache-Control': 'public, max-age=60',
    },
  });
}
