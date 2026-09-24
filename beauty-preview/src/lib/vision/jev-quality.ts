/**
 * Jev structured quality gate for Beauty Preview.
 *
 * Jev does not receive raw images here. It evaluates the structured geometry
 * extracted from the customer's photo and returns a small render policy that
 * is injected into the image-generation prompt.
 */

type Point = { x: number; y: number };
type FeatureLandmarks = {
  leftEyebrow?: Point[];
  rightEyebrow?: Point[];
};

export type JevBeautyDecision = {
  ok: boolean;
  message?: string;
  renderPolicy: 'standard' | 'precision' | 'conservative';
  confidence?: number;
};

function account(): { token: string; accountId: string } | null {
  for (const index of [1, 2, 3]) {
    const token = (process.env[`CLOUDFLARE_API_TOKEN_${index}`] ?? '').trim();
    const accountId = (process.env[`CLOUDFLARE_ACCOUNT_ID_${index}`] ?? '').trim();
    if (token && accountId) return { token, accountId };
  }
  return null;
}

function finitePoints(points: unknown): Point[] {
  if (!Array.isArray(points)) return [];
  return points.filter((p): p is Point =>
    !!p &&
    typeof p === 'object' &&
    Number.isFinite((p as Point).x) &&
    Number.isFinite((p as Point).y),
  );
}

function bbox(points: Point[]) {
  if (!points.length) return null;
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
    width: Math.max(0, Math.max(...xs) - Math.min(...xs)),
    height: Math.max(0, Math.max(...ys) - Math.min(...ys)),
  };
}

function geometryState(input: {
  service: string;
  styleKey: string;
  landmarks: unknown;
  qualityRetry: boolean;
}) {
  const f = (input.landmarks ?? {}) as FeatureLandmarks;
  const left = finitePoints(f.leftEyebrow);
  const right = finitePoints(f.rightEyebrow);
  const lb = bbox(left);
  const rb = bbox(right);

  const leftAspect = lb && lb.height > 0 ? lb.width / lb.height : 0;
  const rightAspect = rb && rb.height > 0 ? rb.width / rb.height : 0;
  const widthRatio = lb && rb && Math.max(lb.width, rb.width) > 0
    ? Math.min(lb.width, rb.width) / Math.max(lb.width, rb.width)
    : 0;

  return {
    service: input.service,
    style: input.styleKey,
    target: input.service === 'eyebrows' ? 'both_eyebrows' : input.service,
    left_points: left.length,
    right_points: right.length,
    left_bbox: lb,
    right_bbox: rb,
    left_aspect_ratio: Number(leftAspect.toFixed(3)),
    right_aspect_ratio: Number(rightAspect.toFixed(3)),
    left_right_width_similarity: Number(widthRatio.toFixed(3)),
    retry_after_quality_gate: input.qualityRetry,
  };
}

function getNoul(answer: any, fallback = 1): number {
  const value = Number(answer?.noul);
  return Number.isFinite(value) ? value : fallback;
}

export async function evaluateBeautyPreviewInput(input: {
  service: string;
  styleKey: string;
  landmarks: unknown;
  qualityRetry: boolean;
}): Promise<JevBeautyDecision> {
  const state = geometryState(input);
  const left = state.left_points;
  const right = state.right_points;

  // Never make Jev a hard dependency. If the account is not configured, the
  // existing MediaPipe validation remains the source of truth.
  const credentials = account();
  if (!credentials) {
    return { ok: left >= 3 && right >= 3, renderPolicy: 'standard' };
  }

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3500);

    const response = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${credentials.accountId}/ai/run`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${credentials.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'typesafe/jev',
          input: {
            state,
            questions: {
              target_reliable: {
                type: 'noul',
                instructions:
                  'Are both target regions sufficiently represented by the structured facial geometry for a controlled PMU edit?',
                criteria: {
                  true: 'Both target regions have enough points, usable geometry, and broadly comparable scale.',
                  false: 'A target region is missing, degenerate, or unreliable.',
                },
              },
              render_policy: {
                type: 'choice',
                instructions:
                  'Choose the safest rendering policy for this image edit. Precision must be used when the customer geometry is trustworthy but the treatment must stay tightly localized. Conservative is for uncertain geometry.',
                criteria: {
                  standard: 'Normal controlled PMU edit with the selected style reference.',
                  precision: 'Prioritize exact customer geometry, target-region crop, and strict zone preservation.',
                  conservative: 'Minimize transformation strength and avoid expanding beyond the measured target zone.',
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
      return { ok: left >= 3 && right >= 3, renderPolicy: 'standard' };
    }

    const payload = await response.json() as any;
    const answers = payload?.result?.answers ?? payload?.answers ?? {};
    const reliable = getNoul(answers.target_reliable, 1);
    const policy = answers.render_policy?.choice;
    const renderPolicy =
      policy === 'precision' || policy === 'conservative' || policy === 'standard'
        ? policy
        : input.qualityRetry
          ? 'precision'
          : 'standard';

    // A failed geometry check is a real input problem, not something FLUX
    // should be asked to hallucinate its way through.
    if (input.service === 'eyebrows' && (left < 3 || right < 3 || reliable < 0.55)) {
      return {
        ok: false,
        renderPolicy: 'conservative',
        message: 'هندسهٔ هر دو ابرو برای پیش‌نمایش دقیق کافی نیست. لطفاً عکس واضح‌تر و روبه‌روتری بارگذاری کنید.',
        confidence: reliable,
      };
    }

    return { ok: true, renderPolicy, confidence: reliable };
  } catch {
    return { ok: left >= 3 && right >= 3, renderPolicy: input.qualityRetry ? 'precision' : 'standard' };
  }
}
