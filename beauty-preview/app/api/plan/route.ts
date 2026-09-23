import { NextResponse } from 'next/server';
import { getTenantSettings } from '@/db';
import { getPlanConfig } from '@/plan-config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const tenant = getTenantSettings();
  const config = getPlanConfig(tenant.planTier);
  return NextResponse.json({
    ok: true,
    tenant: {
      name: tenant.name,
      planTier: tenant.planTier,
      customAssistantName: tenant.customAssistantName,
    },
    plan: config,
  });
}
