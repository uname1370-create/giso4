/**
 * app/api/consult/route.ts
 * ---------------------------------------------------------------------------
 * اندپوینت «مشاور کارشناس ARIA» — حلقه اول زنجیره هوش مصنوعی:
 *   عکس + خدمت + استایل اولیه → تحلیل Vision (Llama 3.2 11B) → نسخه ساخت‌یافته
 * خروجی JSON فقط از طریق tool اجباری (pmu_prescription) پذیرفته می‌شود.
 * بدون کلید Cloudflare: نسخه نمایشی (demo) برمی‌گردد تا فلو UX نخوابد.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';
import { SERVICES_CONTENT } from '@/services-content';
import { SERVICE_TECHNIQUES } from '@/techniques';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const VISION_MODEL =
  (process.env.CLOUDFLARE_VISION_MODEL ?? '').trim() ||
  '@cf/meta/llama-3.2-11b-vision-instruct';

/** سقف طول base64 ورودی (~۶ مگابایت عکس) */
const MAX_BASE64_LENGTH = 8_500_000;

type CloudflareAccount = {
  token: string;
  accountId: string;
};

function accounts(): CloudflareAccount[] {
  return [1, 2, 3]
    .map((index) => ({
      token: (process.env[`CLOUDFLARE_API_TOKEN_${index}`] ?? '').trim(),
      accountId: (process.env[`CLOUDFLARE_ACCOUNT_ID_${index}`] ?? '').trim(),
    }))
    .filter((account) => account.token && account.accountId);
}

/* ------------------------------------------------------------------ */
/* پرامپت سیستم ARIA (سند زنجیره هوش مصنوعی — نسخه مصوب)                  */
/* ------------------------------------------------------------------ */

const ARIA_SYSTEM_PROMPT = `You are ARIA, the owner of an ultra-specialized VIP permanent-makeup atelier and a master face designer with 15 years of clinical PMU experience. You speak to the client through structured data only — never in free prose.

INPUTS YOU RECEIVE:
1. CUSTOMER_PHOTO — the client's real, unedited face photo (source of truth).
2. SELECTED_SERVICE — one of: eyebrows | lips | eyeliner | removal.
3. INITIAL_STYLE — the style/technique the client pre-selected.
4. FACE_METRICS — optional pre-computed browser measurements (face ratios, symmetry, distances). Treat these as measured hints, not guesses. If a metric contradicts what you see, trust the PHOTO and flag the metric as unreliable.
5. CLIENT_TASTE — the client's stated taste (daily makeup intensity, brow shape, density). Respect it when shaping option params; morphology and safety always win over taste.

ANALYSIS PROTOCOL (apply in this exact order):
A. FACE MORPHOLOGY — Classify face shape (oval | round | square | oblong | heart | diamond) using proportions + jaw/forehead reading. Apply the classical thirds (hairline-brow-nose-chin) and fifths (five eye widths) proportion check. Score overall symmetry 0-100.
B. SERVICE-ZONE MICRO-ANALYSIS —
- eyebrows: native density, thickness, arch position vs. golden-ratio ideal (arch apex above outer iris edge), tail endpoint vs. ala-outer-canthus line, front softness, gaps/scars, previous PMU traces.
- lips: upper/lower volume ratio vs. 1:1.6 ideal, border crispness, commissure symmetry, melanin darkness level (0-3), dryness/cracks.
- eyeliner: eye spacing vs. one-eye-width ideal, lid hooding level (0-3), lash density, downward/upward tilt, dark circles.
- removal: old pigment hue (red/orange/gray/blue), saturation depth, shape distortion, scarring signs.
C. COLORIMETRY — Determine skin undertone (warm | cool | neutral) and Fitzpatrick type (I-VI) from the photo. Select pigment family + temperature that NEUTRALIZES the undertone (warm skin → neutral-cool pigment; cool skin → warm-balanced pigment). NEVER propose carbon-black on Fitzpatrick I-II brows; NEVER propose cool pigment on warm lips.
D. SAFETY TRIAGE (recommendation only, never a diagnosis) — Flag: active inflammation/acne/wounds in zone, suspicious moles inside zone → set requires_in_person=true and downgrade confidence. Pregnancy/keloid/medication status is unknown to you; always defer to the salon intake form.
E. STYLE FIT — Score INITIAL_STYLE compatibility 0-100 against A-D. If below 60, you MUST still include it as option 3 (respect client wish) but mark it not_recommended with a one-line clinical reason.

OPTION LOGIC — Always produce exactly 3 options: option 1 = your expert recommendation (best fit); option 2 = a bolder variant inside the safe renderable range; option 3 = the client's initial wish (even if weak, with reason).

OUTPUT CONTRACT (strict):
- Respond ONLY by calling the pmu_prescription tool with valid arguments. No prose outside the tool call.
- Every claim must cite its evidence: "photo" | "metric:<name>" | "rule:<name>".
- Numbers must be plausible for a real adult face; never invent anatomy.
- Confidence = your honest 0-100 certainty. Below 70 → requires_in_person=true.
- Persian client-facing copy (client_text_fa) must be warm, feminine, respectful, 2-3 short sentences, zero medical jargon, zero price talk.`;

/* ------------------------------------------------------------------ */
/* اسکیمای tool اجباری pmu_prescription                                   */
/* ------------------------------------------------------------------ */

const PRESCRIPTION_TOOL = {
  type: 'function',
  function: {
    name: 'pmu_prescription',
    description:
      'Structured PMU expert prescription: face analysis plus exactly 3 client options with hidden render parameters.',
    parameters: {
      type: 'object',
      properties: {
        analysis_summary_en: {
          type: 'string',
          description: 'Compact expert analysis (2-4 sentences) with evidence citations.',
        },
        face_shape: {
          type: 'string',
          enum: ['oval', 'round', 'square', 'oblong', 'heart', 'diamond', 'unknown'],
        },
        symmetry_score: { type: 'number', description: 'Overall facial symmetry 0-100.' },
        skin_undertone: { type: 'string', enum: ['warm', 'cool', 'neutral'] },
        fitzpatrick: { type: 'string', enum: ['I', 'II', 'III', 'IV', 'V', 'VI'] },
        safety_flags: { type: 'array', items: { type: 'string' } },
        requires_in_person: { type: 'boolean' },
        confidence: { type: 'number', description: 'Honest certainty 0-100.' },
        recommended_option: { type: 'integer', enum: [1, 2, 3] },
        options: {
          type: 'array',
          minItems: 3,
          maxItems: 3,
          items: {
            type: 'object',
            properties: {
              id: { type: 'integer', enum: [1, 2, 3] },
              title_en: { type: 'string' },
              client_text_fa: {
                type: 'string',
                description: 'Warm Persian copy shown to the client (2-3 sentences).',
              },
              recommended: { type: 'boolean' },
              not_recommended_reason: { type: 'string' },
              params: {
                type: 'object',
                description:
                  'Hidden render prescription passed to the image model (arch/thickness/density/pigment per service).',
                additionalProperties: true,
              },
            },
            required: ['id', 'title_en', 'client_text_fa', 'recommended', 'params'],
          },
        },
      },
      required: [
        'analysis_summary_en',
        'face_shape',
        'symmetry_score',
        'skin_undertone',
        'fitzpatrick',
        'safety_flags',
        'requires_in_person',
        'confidence',
        'recommended_option',
        'options',
      ],
    },
  },
} as const;

/* ------------------------------------------------------------------ */
/* تایپ‌ها                                                               */
/* ------------------------------------------------------------------ */

interface ConsultBody {
  imageBase64?: unknown;
  service?: unknown;
  initialStyle?: unknown;
  faceMetrics?: unknown;
  preferences?: unknown;
}

export interface ConsultOption {
  id: number;
  title_en: string;
  client_text_fa: string;
  recommended: boolean;
  not_recommended_reason?: string;
  params: Record<string, unknown>;
}

export interface ConsultPrescription {
  analysis_summary_en: string;
  face_shape: string;
  symmetry_score: number;
  skin_undertone: string;
  fitzpatrick: string;
  safety_flags: string[];
  requires_in_person: boolean;
  confidence: number;
  recommended_option: number;
  options: ConsultOption[];
}

function isValidPrescription(value: unknown): value is ConsultPrescription {
  if (!value || typeof value !== 'object') return false;
  const p = value as Record<string, unknown>;
  return (
    typeof p.analysis_summary_en === 'string' &&
    Array.isArray(p.options) &&
    p.options.length === 3 &&
    typeof p.recommended_option === 'number'
  );
}

/* ------------------------------------------------------------------ */
/* نسخه نمایشی (بدون کلید) — فلو UX نمی‌خوابد                              */
/* ------------------------------------------------------------------ */

function buildDemoPrescription(service: string, styleKey: string): ConsultPrescription {
  const serviceTitle = SERVICES_CONTENT[service]?.title ?? 'خدمت زیبایی';
  const techniques =
    service === 'eyebrows' || service === 'lips' || service === 'eyeliner'
      ? SERVICE_TECHNIQUES[service]
      : [];
  const picked = techniques.find((t) => t.key === styleKey) ?? techniques[0];
  const pickedLabel = picked?.label ?? 'مدل طبیعی';

  const baseParams: Record<string, Record<string, unknown>> = {
    eyebrows: {
      technique: styleKey || 'hairstroke',
      arch_height: 'medium',
      thickness_mm: { front: 'soft', body: 'medium', tail: 'tapered' },
      stroke_density: 0.6,
      front_softness: 0.8,
      pigment_family: 'warm organic brown',
      pigment_temperature: 'neutral-warm',
      pigment_depth: 'natural',
    },
    lips: {
      lip_look: styleKey || 'natural_blush',
      border_definition: 0.4,
      volume_illusion: 'soft',
      neutralization_passes: 0,
      pigment_family: 'rose-nude organic',
      pigment_temperature: 'warm',
      pigment_depth: 'sheer',
    },
    eyeliner: {
      liner_look: styleKey || 'lash_line_enhancement',
      line_thickness_mm: 0.6,
      wing_length_mm: 0,
      smoke_gradient: 0,
      pigment_carbon: true,
    },
    removal: {
      sessions_estimate: 2,
      method: 'enzymatic',
      healing_interval_weeks: 6,
    },
  };

  const params = baseParams[service] ?? baseParams.eyebrows;

  return {
    analysis_summary_en: `Demo analysis for ${serviceTitle}: balanced facial thirds, good symmetry, neutral-warm undertone (rule:golden-ratio, photo). Client wish "${pickedLabel}" is compatible.`,
    face_shape: 'oval',
    symmetry_score: 86,
    skin_undertone: 'neutral',
    fitzpatrick: 'III',
    safety_flags: [],
    requires_in_person: false,
    confidence: 62,
    recommended_option: 1,
    options: [
      {
        id: 1,
        title_en: `Expert recommendation: ${pickedLabel}`,
        client_text_fa: `عزیزم، فرم صورتت بیضی و متقارنه و مدل «${pickedLabel}» دقیقاً همون چیزیه که چهره‌ت رو متعادل و شیک نشون میده. پیشنهاد من همینه؛ هم طبیعیه هم موندگاری عالی داره. ✨`,
        recommended: true,
        params,
      },
      {
        id: 2,
        title_en: 'Bolder variant inside safe range',
        client_text_fa:
          'اگه دنبال جلوه پررنگ‌تری هستی، می‌تونیم همون مدل رو با تراکم و عمق بیشتر اجرا کنیم؛ جسورانه ولی هنوز کاملاً امن و متناسب با صورتت.',
        recommended: false,
        params: { ...params, bold_variant: true },
      },
      {
        id: 3,
        title_en: 'Client initial wish',
        client_text_fa: `مدل اولیه‌ای که خودت انتخاب کردی («${pickedLabel}») هم قابل اجراست و ما دقیقاً همون رو برات پیش‌نمایش می‌کنیم تا با خیال راحت مقایسه کنی.`,
        recommended: false,
        params,
      },
    ],
  };
}

/* ------------------------------------------------------------------ */
/* فراخوانی Cloudflare (OpenAI-Compatible + tool اجباری)                   */
/* ------------------------------------------------------------------ */

async function callCloudflareVision(
  account: CloudflareAccount,
  imageDataUri: string,
  service: string,
  initialStyle: string,
  faceMetrics: unknown,
  clientTaste: string,
): Promise<ConsultPrescription> {
  const userText = [
    `SELECTED_SERVICE: ${service}`,
    `INITIAL_STYLE: ${initialStyle || 'client_has_no_preference'}`,
    `CLIENT_TASTE: ${clientTaste}`,
    `FACE_METRICS: ${faceMetrics ? JSON.stringify(faceMetrics).slice(0, 2000) : 'none'}`,
    'Analyze CUSTOMER_PHOTO per the ARIA protocol and call pmu_prescription exactly once.',
  ].join('\n');

  const res = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${account.accountId}/ai/v1/chat/completions`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${account.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: VISION_MODEL,
        temperature: 0.2,
        top_p: 0.9,
        max_tokens: 1500,
        seed: 42,
        messages: [
          { role: 'system', content: ARIA_SYSTEM_PROMPT },
          {
            role: 'user',
            content: [
              { type: 'text', text: userText },
              { type: 'image_url', image_url: { url: imageDataUri } },
            ],
          },
        ],
        tools: [PRESCRIPTION_TOOL],
        tool_choice: 'required',
      }),
      signal: AbortSignal.timeout(90000),
      cache: 'no-store',
    },
  );

  const raw = await res.text();
  let payload: unknown = null;
  try {
    payload = raw ? JSON.parse(raw) : null;
  } catch {
    payload = null;
  }

  if (!res.ok) {
    const msg =
      payload && typeof payload === 'object'
        ? JSON.stringify(payload).slice(0, 300)
        : raw.slice(0, 300);
    throw new Error(`Cloudflare vision HTTP ${res.status}: ${msg}`);
  }

  const choices =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>).choices
      : null;
  const toolCalls =
    Array.isArray(choices) && choices[0] && typeof choices[0] === 'object'
      ? (choices[0] as Record<string, unknown>).message &&
        typeof (choices[0] as Record<string, unknown>).message === 'object'
        ? (
            (choices[0] as Record<string, unknown>).message as Record<string, unknown>
          ).tool_calls
        : null
      : null;

  const args =
    Array.isArray(toolCalls) && toolCalls[0] && typeof toolCalls[0] === 'object'
      ? (toolCalls[0] as Record<string, unknown>).function &&
        typeof (toolCalls[0] as Record<string, unknown>).function === 'object'
        ? (
            ((toolCalls[0] as Record<string, unknown>).function as Record<string, unknown>)
              .arguments as unknown
          )
        : null
      : null;

  if (typeof args !== 'string' || !args) {
    throw new Error('Cloudflare vision: tool call pmu_prescription missing in response');
  }

  let parsed: unknown = null;
  try {
    parsed = JSON.parse(args);
  } catch {
    throw new Error('Cloudflare vision: tool arguments are not valid JSON');
  }

  if (!isValidPrescription(parsed)) {
    throw new Error('Cloudflare vision: prescription failed validation (need analysis + 3 options)');
  }

  return parsed;
}

/* ------------------------------------------------------------------ */
/* هندلرها                                                               */
/* ------------------------------------------------------------------ */

export async function POST(request: Request): Promise<NextResponse> {
  const startedAt = Date.now();

  let body: ConsultBody;
  try {
    body = (await request.json()) as ConsultBody;
  } catch {
    return NextResponse.json({ ok: false, error: 'بدنه درخواست نامعتبر است.' }, { status: 400 });
  }

  const imageBase64 = typeof body.imageBase64 === 'string' ? body.imageBase64 : '';
  const service = typeof body.service === 'string' ? body.service.trim() : '';
  const initialStyle = typeof body.initialStyle === 'string' ? body.initialStyle.trim() : '';

  // سلیقه کاربر (اختیاری): فقط مقادیر شناخته‌شده پذیرفته می‌شود
  const rawTaste =
    body.preferences && typeof body.preferences === 'object'
      ? (body.preferences as Record<string, unknown>)
      : {};
  const tasteOf = (value: unknown, allowed: string[]): string | null =>
    typeof value === 'string' && allowed.includes(value) ? value : null;
  const taste = {
    dailyMakeup: tasteOf(rawTaste.dailyMakeup, ['natural', 'soft', 'bold']),
    browShape: tasteOf(rawTaste.browShape, ['natural', 'defined']),
    density: tasteOf(rawTaste.density, ['fluffy', 'dense']),
  };
  // سلیقه مرتبط با هر خدمت فرق می‌کند (فرم ابرو برای لب بی‌معناست؛ ریمو سلیقه نمی‌گیرد)
  const tasteBits = [
    taste.dailyMakeup ? `daily makeup ${taste.dailyMakeup}` : '',
    service === 'eyebrows' && taste.browShape ? `brow shape ${taste.browShape}` : '',
    (service === 'eyebrows' || service === 'lips') && taste.density
      ? `density ${taste.density}`
      : '',
  ].filter(Boolean);
  const tasteText = service === 'removal' ? '' : tasteBits.join('; ');
  const clientTasteLine = tasteText
    ? `${tasteText} — respect this taste in option params (density/depth), never override safety or morphology.`
    : 'no taste stated';

  if (!imageBase64) {
    return NextResponse.json({ ok: false, error: 'عکس چهره ارسال نشده است.' }, { status: 400 });
  }
  if (imageBase64.length > MAX_BASE64_LENGTH) {
    return NextResponse.json({ ok: false, error: 'حجم عکس بیش از حد مجاز است.' }, { status: 400 });
  }
  if (!SERVICES_CONTENT[service]) {
    return NextResponse.json({ ok: false, error: 'خدمت انتخاب‌شده معتبر نیست.' }, { status: 400 });
  }

  const configured = accounts();

  // بدون کلید: نسخه نمایشی تا فلو UX نخوابد
  if (configured.length === 0) {
    const prescription = buildDemoPrescription(service, initialStyle);
    // بازتاب سلیقه در نسخه نمایشی، فقط کلیدهای مرتبط با هر خدمت
    // (مسیر واقعی در پرامپت LLM اعمال می‌شود)
    for (const opt of prescription.options) {
      if (service === 'eyebrows' || service === 'lips') {
        if (taste.dailyMakeup === 'bold') opt.params.pigment_depth = 'rich';
        else if (taste.dailyMakeup === 'natural') opt.params.pigment_depth = 'sheer';
      }
      if (service === 'eyebrows') {
        if (taste.density === 'dense') opt.params.stroke_density = 0.8;
        else if (taste.density === 'fluffy') opt.params.stroke_density = 0.45;
      }
    }
    return NextResponse.json({
      ok: true,
      demo: true,
      provider: 'demo',
      prescription,
      ms: Date.now() - startedAt,
    });
  }

  let lastError = '';
  for (let i = 0; i < configured.length; i += 1) {
    try {
      const prescription = await callCloudflareVision(
        configured[i],
        imageBase64,
        service,
        initialStyle,
        body.faceMetrics,
        clientTasteLine,
      );
      return NextResponse.json({
        ok: true,
        demo: false,
        provider: `cloudflare-llama-vision:${i + 1}`,
        prescription,
        ms: Date.now() - startedAt,
      });
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
      console.error(`[AI-CONSULT] account ${i + 1} failed: ${lastError.slice(0, 300)}`);
    }
  }

  return NextResponse.json(
    { ok: false, error: `سرویس تحلیل پاسخ نداد — ${lastError}`.slice(0, 500) },
    { status: 502 },
  );
}

export async function GET(): Promise<NextResponse> {
  const configured = accounts();
  return NextResponse.json({
    ok: true,
    model: VISION_MODEL,
    accountsConfigured: configured.length,
    demo: configured.length === 0,
  });
}
