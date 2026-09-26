import { NextResponse } from 'next/server';
import { isAuthorized, unauthorizedResponse } from '@/admin-auth';
import fs from 'node:fs/promises';
import path from 'node:path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const VALID_SERVICES = ['brows', 'lips', 'eyeliner'];
const MAX_BYTES = 5 * 1024 * 1024;

export async function POST(request: Request) {
  if (!isAuthorized(request)) {
    return unauthorizedResponse();
  }

  try {
    const formData = await request.formData();
    const service = String(formData.get('service') || '').toLowerCase().trim();
    const styleKey = String(formData.get('styleKey') || '').trim();
    const file = formData.get('file') as File | null;

    if (!VALID_SERVICES.includes(service)) {
      return NextResponse.json({ ok: false, error: 'نوع خدمت نامعتبر است' }, { status: 400 });
    }
    if (!styleKey) {
      return NextResponse.json({ ok: false, error: 'کلید سبک مشخص نشده است' }, { status: 400 });
    }
    if (!file) {
      return NextResponse.json({ ok: false, error: 'فایل تصویر ارسال نشده است' }, { status: 400 });
    }
    if (file.size > MAX_BYTES) {
      return NextResponse.json({ ok: false, error: 'حجم تصویر نباید بیش از ۵ مگابایت باشد' }, { status: 400 });
    }

    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    // ذخیره در پوشه public متناظر
    const targetDir = path.join(process.cwd(), 'public', service);
    await fs.mkdir(targetDir, { recursive: true });

    const fileName = `${styleKey}.png`;
    const targetPath = path.join(targetDir, fileName);
    await fs.writeFile(targetPath, buffer);

    const publicUrl = `/${service}/${fileName}`;
    return NextResponse.json({
      ok: true,
      url: publicUrl,
      fileName,
    });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : 'خطا در ذخیره رفرنس' },
      { status: 500 },
    );
  }
}
