import { NextResponse } from 'next/server';
import { analyzeBeautyPhoto } from '@/analysis';
import { parseDataUri } from '@/providers/http';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const imageBase64 = typeof body.image === 'string' ? body.image : '';

    if (!imageBase64) {
      return NextResponse.json({ ok: false, error: 'عکس ارسال نشده است' }, { status: 400 });
    }

    const parsed = parseDataUri(imageBase64);
    if (!parsed) {
      return NextResponse.json({ ok: false, error: 'قالب تصویر نامعتبر است' }, { status: 400 });
    }

    const analysis = await analyzeBeautyPhoto(parsed.dataUri);
    return NextResponse.json({
      ok: true,
      analysis,
    });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : 'خطای تحلیل' },
      { status: 500 },
    );
  }
}
