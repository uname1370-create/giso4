import { NextResponse } from 'next/server';
import { isAuthorized, unauthorizedResponse } from '@/admin-auth';
import { updateLeadStatus, deleteLead, getLeadById } from '@/db';
import fs from 'node:fs/promises';
import path from 'node:path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface RouteContext {
  params: { id: string };
}

export async function PATCH(request: Request, { params }: RouteContext) {
  if (!isAuthorized(request)) {
    return unauthorizedResponse();
  }

  const { id } = params;
  try {
    const body = await request.json();
    const { status, notes } = body;

    const updated = updateLeadStatus(id, status, notes);
    if (!updated) {
      return NextResponse.json({ ok: false, error: 'مراجع یافت نشد' }, { status: 404 });
    }

    return NextResponse.json({ ok: true, lead: updated });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: 'خطا در به‌روزرسانی مراجع' },
      { status: 500 },
    );
  }
}

export async function DELETE(request: Request, { params }: RouteContext) {
  if (!isAuthorized(request)) {
    return unauthorizedResponse();
  }

  const { id } = params;
  try {
    const existing = getLeadById(id);
    if (!existing) {
      return NextResponse.json({ ok: false, error: 'مراجع یافت نشد' }, { status: 404 });
    }

    // حذف رکورد از دیتابیس
    deleteLead(id);

    // حذف پوشه تصاویر از دیسک جهت رعایت حریم خصوصی
    try {
      const uploadDir = path.join(process.cwd(), 'public', 'uploads', 'leads', id);
      await fs.rm(uploadDir, { recursive: true, force: true });
    } catch {
      // نادیده گرفتن خطای عدم وجود فایل
    }

    return NextResponse.json({ ok: true, message: 'پرونده با موفقیت حذف شد' });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: 'خطا در حذف پرونده' },
      { status: 500 },
    );
  }
}
