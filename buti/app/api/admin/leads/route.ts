import { NextResponse } from 'next/server';
import { isAuthorized, unauthorizedResponse } from '@/admin-auth';
import { getLeads } from '@/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  if (!isAuthorized(request)) {
    return unauthorizedResponse();
  }

  try {
    const leads = getLeads();
    return NextResponse.json({ ok: true, leads });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: 'خطا در بارگذاری مراجعین' },
      { status: 500 },
    );
  }
}
