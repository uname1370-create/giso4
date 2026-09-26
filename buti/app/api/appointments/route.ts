import { NextResponse } from 'next/server';
import { saveLead } from '@/db';
import { saveLeadImage } from '@/storage';
import { randomUUID } from 'node:crypto';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const {
      fullName,
      phoneNumber,
      instagramId,
      selectedService = 'eyebrows',
      selectedStyle = 'میکروبلیدینگ مویی',
      originalImageData,
      resultImageData,
      notes,
    } = body;

    if (!fullName || !phoneNumber) {
      return NextResponse.json(
        { ok: false, error: 'نام و شماره تماس الزامی است.' },
        { status: 400 },
      );
    }

    const leadId = randomUUID();

    // ذخیره فایل‌های تصویر در دیسک
    let originalImageUrl = '';
    let resultImageUrl = '';

    if (originalImageData) {
      originalImageUrl = (await saveLeadImage(leadId, 'original', originalImageData)) || '';
    }
    if (resultImageData) {
      resultImageUrl = (await saveLeadImage(leadId, 'result', resultImageData)) || '';
    }

    const record = saveLead({
      id: leadId,
      fullName: String(fullName).trim(),
      phoneNumber: String(phoneNumber).trim(),
      instagramId: instagramId ? String(instagramId).trim() : null,
      selectedService: String(selectedService),
      selectedStyle: String(selectedStyle),
      originalImageUrl: originalImageUrl || '/uploads/default-before.png',
      resultImageUrl: resultImageUrl || '/uploads/default-after.png',
      status: 'new',
      notes: notes ? String(notes).trim() : null,
    });

    return NextResponse.json({
      ok: true,
      lead: record,
    });
  } catch (error) {
    console.error('[APPOINTMENTS_POST_ERROR]', error);
    return NextResponse.json(
      { ok: false, error: 'خطا در ثبت نوبت. لطفاً مجدداً تلاش نمایید.' },
      { status: 500 },
    );
  }
}
