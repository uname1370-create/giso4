import { NextResponse } from 'next/server';

type QualityInput = {
  service?: unknown;
  styleKey?: unknown;
  targetChangeRatio?: unknown;
  outsideChangeRatio?: unknown;
  faceChangeRatio?: unknown;
  leftChangeRatio?: unknown;
  rightChangeRatio?: unknown;
};

function num(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? Math.max(0, Math.min(1, n)) : 0;
}

function credentials() {
  for (const index of [1, 2, 3]) {
    const token = (process.env[`CLOUDFLARE_API_TOKEN_${index}`] ?? '').trim();
    const accountId = (process.env[`CLOUDFLARE_ACCOUNT_ID_${index}`] ?? '').trim();
    if (token && accountId) return { token, accountId };
  }
  return null;
}

export async function POST(request: Request) {
  let body: QualityInput;
  try {
    body = await request.json() as QualityInput;
  } catch {
    return NextResponse.json({ ok: false, retry: false }, { status: 400 });
  }

  const state = {
    service: typeof body.service === 'string' ? body.service : '',
    style: typeof body.styleKey === 'string' ? body.styleKey : '',
    target_change_ratio: num(body.targetChangeRatio),
    outside_change_ratio: num(body.outsideChangeRatio),
    face_change_ratio: num(body.faceChangeRatio),
    left_change_ratio: num(body.leftChangeRatio),
    right_change_ratio: num(body.rightChangeRatio),
  };

  const localFallback =
    state.target_change_ratio < 0.035 ||
    state.outside_change_ratio > 0.02 ||
    (state.service === 'eyebrows' &&
      Math.min(state.left_change_ratio, state.right_change_ratio) < 0.018);

  const c = credentials();
  if (!c) {
    return NextResponse.json({
      ok: true,
      retry: localFallback,
      confidence: 0,
      source: 'local-fallback',
    });
  }

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3500);
    const response = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${c.accountId}/ai/run`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${c.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'typesafe/jev',
          input: {
            state,
            questions: {
              treatment_present: {
                type: 'noul',
                instructions:
                  'Does the measured target-region change indicate a meaningful treatment rather than a tiny decorative mark?',
                criteria: {
                  true: 'There is meaningful treatment change across the target region.',
                  false: 'The change is too small and likely represents only a line, stroke, or incomplete treatment.',
                },
              },
              zone_safe: {
                type: 'noul',
                instructions:
                  'Is the edit sufficiently confined to the requested service zone?',
                criteria: {
                  true: 'Outside-zone and face-wide changes are negligible.',
                  false: 'The result changes too much outside the requested zone.',
                },
              },
              retry: {
                type: 'noul',
                instructions:
                  'Should this preview be regenerated once with stricter precision instructions?',
                criteria: {
                  true: 'The treatment is incomplete or zone safety is poor enough to justify one retry.',
                  false: 'The result is acceptable to show the customer.',
                },
              },
            },
          },
        }),
        signal: controller.signal,
      },
    );
    clearTimeout(timer);

    if (!response.ok) {
      return NextResponse.json({ ok: true, retry: localFallback, source: 'local-fallback' });
    }

    const payload = await response.json() as any;
    const answers = payload?.result?.answers ?? payload?.answers ?? {};
    const treatment = Number(answers.treatment_present?.noul ?? 1);
    const zoneSafe = Number(answers.zone_safe?.noul ?? 1);
    const retry = Number(answers.retry?.noul ?? 0);

    return NextResponse.json({
      ok: true,
      retry: retry >= 0.60 || treatment < 0.45 || zoneSafe < 0.45 || localFallback,
      confidence: Math.min(
        Number(answers.treatment_present?.confidence ?? 0),
        Number(answers.zone_safe?.confidence ?? 0),
      ) || 0,
      source: 'jev',
    });
  } catch {
    return NextResponse.json({ ok: true, retry: localFallback, source: 'local-fallback' });
  }
}
