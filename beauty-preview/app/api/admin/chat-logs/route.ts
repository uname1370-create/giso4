import { NextResponse } from 'next/server';
import { isAuthorized, unauthorizedResponse } from '@/admin-auth';
import { getChatLogs } from '@/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  if (!isAuthorized(request)) {
    return unauthorizedResponse();
  }

  try {
    const logs = getChatLogs(50);
    return NextResponse.json({ ok: true, logs });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: 'خطا در بارگذاری تاریخچه چت‌ها' },
      { status: 500 },
    );
  }
}
