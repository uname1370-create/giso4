import { NextResponse } from 'next/server';
import { getTenantSettings, updateTenantSettings } from '@/db';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const tenant = getTenantSettings();
  return NextResponse.json({ ok: true, tenant });
}

export async function PATCH(request: Request) {
  try {
    const body = await request.json();
    const updated = updateTenantSettings('default', {
      planTier: body.planTier,
      name: body.name,
      customAssistantName: body.customAssistantName,
    });
    return NextResponse.json({ ok: true, tenant: updated });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 400 });
  }
}
