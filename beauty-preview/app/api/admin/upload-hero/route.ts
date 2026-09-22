/**
 * app/api/admin/upload-hero/route.ts
 * ---------------------------------------------------------------------------
 * آپلود/حذف تصویر هیرو صفحهٔ اصلی (نیازمند توکن ورود):
 *
 *   POST   /api/admin/upload-hero    form-data: file
 *   DELETE /api/admin/upload-hero    ← حذف تصویر هیرو
 *
 * فایل در public/hero/hero-<timestamp>.<ext> ذخیره و در
 * public/site-images.json ثبت می‌شود.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { isAuthorized, unauthorizedResponse } from '@/admin-auth';
import { deleteUpload, readSiteImages, saveUpload, updateSiteImages } from '@/site-images';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: Request): Promise<NextResponse> {
  if (!isAuthorized(request)) return unauthorizedResponse();

  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return NextResponse.json(
      { ok: false, error: 'درخواست نامعتبر است (form-data خوانده نشد).' },
      { status: 400 },
    );
  }

  const file = form.get('file');
  if (!(file instanceof File)) {
    return NextResponse.json({ ok: false, error: 'فایلی انتخاب نشده است.' }, { status: 400 });
  }

  try {
    const saved = await saveUpload('hero', 'hero', file);
    const previous = (await readSiteImages()).hero;

    if (previous && previous !== saved.url) {
      await deleteUpload(previous);
    }

    const images = await updateSiteImages((current) => ({ ...current, hero: saved.url }));

    return NextResponse.json({ ok: true, ...saved, images });
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : 'ذخیرهٔ تصویر ناموفق بود.',
      },
      { status: 400 },
    );
  }
}

export async function DELETE(request: Request): Promise<NextResponse> {
  if (!isAuthorized(request)) return unauthorizedResponse();

  const current = await readSiteImages();
  if (current.hero) await deleteUpload(current.hero);

  const images = await updateSiteImages((value) => ({ ...value, hero: null }));

  return NextResponse.json({ ok: true, removed: Boolean(current.hero), images });
}
