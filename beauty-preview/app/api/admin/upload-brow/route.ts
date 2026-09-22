/**
 * app/api/admin/upload-brow/route.ts
 * ---------------------------------------------------------------------------
 * آپلود تصویر اختصاصی برای هر مدل ابرو (نیازمند توکن ورود):
 *
 *   POST   /api/admin/upload-brow          form-data: file, style
 *   DELETE /api/admin/upload-brow?style=…  ← حذف تصویر و بازگشت به SVG خودکار
 *
 * خروجی موفق: { ok: true, style, url, images: {...} }
 * فایل در public/eyebrows/<style>-<timestamp>.<ext> ذخیره و در
 * public/site-images.json ثبت می‌شود؛ صفحهٔ اصلی همان فایل را نمایش می‌دهد.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { isAuthorized, unauthorizedResponse } from '@/admin-auth';
import type { BrowStyleKey } from '@/brow-shapes';
import {
  BROW_KEYS,
  deleteUpload,
  readSiteImages,
  saveUpload,
  updateSiteImages,
} from '@/site-images';

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

  const style = String(form.get('style') ?? '').trim();
  const file = form.get('file');

  if (!BROW_KEYS.includes(style as BrowStyleKey)) {
    return NextResponse.json(
      { ok: false, error: 'مدل ابرو نامعتبر است.' },
      { status: 400 },
    );
  }
  if (!(file instanceof File)) {
    return NextResponse.json({ ok: false, error: 'فایلی انتخاب نشده است.' }, { status: 400 });
  }

  const styleKey = style as BrowStyleKey;

  try {
    const saved = await saveUpload('eyebrows', styleKey, file);
    const previous = (await readSiteImages()).brows[styleKey];

    // فایل قبلی همین مدل (اگر بود) حذف می‌شود تا پوشه شلوغ نشود
    if (previous && previous !== saved.url) {
      await deleteUpload(previous);
    }

    const images = await updateSiteImages((current) => ({
      ...current,
      brows: { ...current.brows, [styleKey]: saved.url },
    }));

    return NextResponse.json({ ok: true, style: styleKey, ...saved, images });
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

  const style = new URL(request.url).searchParams.get('style')?.trim() ?? '';
  if (!BROW_KEYS.includes(style as BrowStyleKey)) {
    return NextResponse.json({ ok: false, error: 'مدل ابرو نامعتبر است.' }, { status: 400 });
  }

  const styleKey = style as BrowStyleKey;
  const current = await readSiteImages();
  const existing = current.brows[styleKey];

  if (existing) await deleteUpload(existing);

  const images = await updateSiteImages((value) => {
    const brows = { ...value.brows };
    delete brows[styleKey];
    return { ...value, brows };
  });

  return NextResponse.json({ ok: true, style: styleKey, removed: Boolean(existing), images });
}
