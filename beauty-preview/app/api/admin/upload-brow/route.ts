/**
 * app/api/admin/upload-brow/route.ts
 * ---------------------------------------------------------------------------
 * آپلود تصویر اختصاصی هر مدل ابرو از پنل مدیریت.
 *
 *   POST   multipart/form-data:  file  +  styleName
 *          styleName می‌تواند کلید مدل (feather)، نام فارسی (فدر براو) یا نام
 *          فایل (feather.png) باشد. فقط PNG، حداکثر ۵ مگابایت.
 *          فایل با نام ثابت ذخیره می‌شود: public/eyebrows/<file>.png
 *
 *   DELETE ?style=feather   ← حذف تصویر و برگشت به SVG خودکار
 *
 * احراز هویت: هدر Authorization: Bearer <token> (خروجی /api/admin/login)
 * یا هدر x-admin-password با مقدار ADMIN_PASSWORD.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { isAuthorized, unauthorizedResponse } from '@/admin-auth';
import { BROW_TARGETS, deleteBrowImage, findBrowTarget, saveBrowImage } from '@/site-images';

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

  const styleValue = form.get('styleName') ?? form.get('style');
  const target = findBrowTarget(typeof styleValue === 'string' ? styleValue : null);
  if (!target) {
    return NextResponse.json(
      {
        ok: false,
        error: 'مدل ابرو نامعتبر است.',
        styles: BROW_TARGETS.map((item) => ({ key: item.key, label: item.label })),
      },
      { status: 400 },
    );
  }

  try {
    const saved = await saveBrowImage(target, file);
    return NextResponse.json({
      ok: true,
      style: target.key,
      label: target.label,
      url: saved.url,
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

  const styleValue = new URL(request.url).searchParams.get('style');
  const target = findBrowTarget(styleValue);
  if (!target) {
    return NextResponse.json({ ok: false, error: 'مدل ابرو نامعتبر است.' }, { status: 400 });
  }

  const removed = await deleteBrowImage(target);
  // پس از حذف، صفحهٔ اصلی خودش به تصویر SVG خودکار برمی‌گردد
  return NextResponse.json({ ok: true, style: target.key, removed });
}
