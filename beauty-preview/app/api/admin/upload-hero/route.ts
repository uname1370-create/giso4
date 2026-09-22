/**
 * app/api/admin/upload-hero/route.ts
 * ---------------------------------------------------------------------------
 * آپلود تصویر هیروی صفحهٔ اصلی از پنل مدیریت.
 *
 *   POST   multipart/form-data:  file
 *          JPG / PNG / WEBP، حداکثر ۱۰ مگابایت.
 *          فایل با نام hero.<ext> در public/hero ذخیره می‌شود و بقیهٔ
 *          پسوندها پاک می‌شوند تا همیشه فقط یک تصویر هیرو وجود داشته باشد.
 *
 *   DELETE  ← حذف تصویر هیرو (صفحهٔ اصلی به پس‌زمینهٔ گرادیانی برمی‌گردد)
 *
 * احراز هویت: هدر Authorization: Bearer <token> (خروجی /api/admin/login)
 * یا هدر x-admin-password با مقدار ADMIN_PASSWORD.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { isAuthorized, unauthorizedResponse } from '@/admin-auth';
import { HERO_IMAGE_URL } from '@/options';
import { deleteHeroImage, saveHeroImage } from '@/site-images';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: Request): Promise<NextResponse> {
  if (!isAuthorized(request)) return unauthorizedResponse();

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return NextResponse.json({ ok: false, error: 'درخواست نامعتبر است.' }, { status: 400 });
  }

  const file = form.get('file');
  if (!(file instanceof File)) {
    return NextResponse.json({ ok: false, error: 'فایلی انتخاب نشده است.' }, { status: 400 });
  }

  try {
    const saved = await saveHeroImage(file);
    return NextResponse.json({
      ok: true,
      // آدرس پایدار (بدون پسوند) که همیشه به تصویر فعلی اشاره می‌کند
      url: HERO_IMAGE_URL,
      publicPath: saved.publicPath,
      fileName: saved.fileName,
      bytes: saved.bytes,
      mime: saved.mime,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'ذخیرهٔ تصویر ناموفق بود.';
    return NextResponse.json({ ok: false, error: message }, { status: 400 });
  }
}

export async function DELETE(request: Request): Promise<NextResponse> {
  if (!isAuthorized(request)) return unauthorizedResponse();

  const removed = await deleteHeroImage();
  return NextResponse.json({ ok: true, removed });
}
