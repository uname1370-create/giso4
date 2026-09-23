/**
 * app/api/consult/route.ts
 * ---------------------------------------------------------------------------
 * اندپوینت «مشاور کارشناس ARIA» — حلقه اول زنجیره هوش مصنوعی:
 *   عکس + خدمت + استایل اولیه → تحلیل Vision (زنجیره آزاد: LLaVA اصلی، Qwen پشتیبان) → نسخه ساخت‌یافته
 * فراخوانی بینایی بدون tool (JSON خام + Regex) با سقف ۸ ثانیه؛ خطا → دموی صادقانه، هرگز ۵۰۲.
 * بدون کلید Cloudflare: نسخه نمایشی (demo) برمی‌گردد تا فلو UX نخوابد.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';
import { SERVICES_CONTENT } from '@/services-content';
import { SERVICE_TECHNIQUES } from '@/techniques';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

const ENV_VISION_MODEL = (process.env.CLOUDFLARE_VISION_MODEL ?? '').trim();
/**
 * مدل بینایی ثابت و آزاد: اگر env خالی باشد یا هنوز روی llama/meta قفل شده
 * باشد (باقی‌مانده از تنظیم قدیمی)، نادیده گرفته می‌شود تا ۵۰۱۶ برنگردد.
 */
const VISION_MODEL =
  !ENV_VISION_MODEL || /llama|meta/i.test(ENV_VISION_MODEL)
    ? '@cf/llava-hf/llava-1.5-7b-hf'
    : ENV_VISION_MODEL;

/** مدل بینایی پشتیبان — کل زنجیره آزاد است و به لایسنس Meta نیاز ندارد */
const FALLBACK_VISION_MODELS: string[] = ['@cf/qwen/qwen3.8-27b'];

/** الگوی JSON خامی که در حالت بدون-tool از مدل پشتیبان خواسته می‌شود */
const PRESCRIPTION_JSON_SKELETON = `{"analysis_summary_en":"...","analysis_summary_fa":"...","face_shape":"oval|round|square|oblong|heart|diamond|unknown","symmetry_score":0-100,"skin_undertone":"warm|cool|neutral","fitzpatrick":"I|II|III|IV|V|VI","safety_flags":[],"requires_in_person":false,"confidence":0-100,"recommended_option":1-3,"options":[{"id":1,"title_en":"...","client_text_fa":"...","recommended":true,"params":{}},{"id":2,...},{"id":3,...}]}`;

/** نام کوتاه مدل برای لاگ و provider (حذف پیشوند @cf/vendor) */
function shortModel(model: string): string {
  return model.replace(/^@cf\/[^/]+\//, '') || model;
}

/** سقف زمانی هر تلاش بینایی (۸ ثانیه) و سقف کل فرآیند (۹٫۵ ثانیه) — هرگز معطلی یا ۵۰۲ */
const VISION_ATTEMPT_TIMEOUT_MS = 8000;
const VISION_TOTAL_DEADLINE_MS = 9500;

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
- Persian client-facing copy (client_text_fa) must be warm, feminine, respectful, 2-3 short sentences, zero medical jargon, zero price talk.
- analysis_summary_fa: retell the SAME analysis for the client in SIMPLE Persian (2-3 short sentences, zero jargon, zero invented numbers): one warm verdict line + how it fits INITIAL_STYLE + one gentle care note. If uncertain about any measurement, say the in-person visit will finalize it — NEVER fabricate.`;

/* ------------------------------------------------------------------ */
/* توجه: فراخوانی بینایی عمداً بدون tool است (LLaVA با tool خطا می‌دهد).   */
/* خروجی JSON خام با Regex استخراج و با isValidPrescription اعتبارسنجی می‌شود. */
/* ------------------------------------------------------------------ */

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
  analysis_summary_fa: string;
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

/**
 * تضمین خلاصه فارسی: اگر مدل نفرستاده باشد، از متن گزینه پیشنهادی
 * (حداکثر ۲ جمله اول) استفاده می‌شود — بدون جعل هیچ عددی.
 */
function ensureFaSummary(p: ConsultPrescription): ConsultPrescription {
  const fa = typeof p.analysis_summary_fa === 'string' ? p.analysis_summary_fa.trim() : '';
  if (fa) return p;
  const rec = p.options.find((o) => o.id === p.recommended_option) ?? p.options[0];
  const text = rec?.client_text_fa ?? '';
  const two = text
    .split(/(?<=[.!?؟])\s+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 2)
    .join(' ');
  return {
    ...p,
    analysis_summary_fa:
      two || 'تحلیل چهره انجام شد؛ لطفاً یکی از گزینه‌های پیشنهادی را انتخاب کنید.',
  };
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
    analysis_summary_fa:
      'حالت نمایشی فعال است و موتور تحلیل هوشمند هنوز متصل نیست؛ پس عدد دقیقی از چهره اندازه‌گیری نشده. گزینه‌های پیشنهادی زیر را ببینید و یکی را انتخاب کنید.',
    face_shape: 'unknown',
    symmetry_score: 0,
    skin_undertone: 'نامشخص',
    fitzpatrick: 'نامشخص',
    safety_flags: [],
    requires_in_person: false,
    confidence: 0,
    recommended_option: 1,
    options: [
      {
        id: 1,
        title_en: `Expert recommendation: ${pickedLabel}`,
        client_text_fa: `عزیزم، مدل «${pickedLabel}» یکی از پرطرفدارترین انتخاب‌هاست؛ هم طبیعی دیده می‌شه هم موندگاری خوبی داره. چون در حالت نمایشی هستیم، با اتصال موتور هوشمند پیشنهاد دقیق مخصوص چهره‌ت رو می‌گیری. ✨`,
        recommended: true,
        params,
      },
      {
        id: 2,
        title_en: 'Bolder variant inside safe range',
        client_text_fa:
          'اگه دنبال جلوه پررنگ‌تری هستی، می‌تونیم همون مدل رو با تراکم و عمق بیشتر اجرا کنیم؛ جسورانه ولی داخل محدوده امن.',
        recommended: false,
        params: { ...params, bold_variant: true },
      },
      {
        id: 3,
        title_en: 'Client initial wish',
        client_text_fa: `مدل اولیه‌ای که خودت انتخاب کردی («${pickedLabel}») رو هم دقیقاً همون‌طور برات پیش‌نمایش می‌کنیم تا با خیال راحت مقایسه کنی.`,
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
  model: string = VISION_MODEL,
  timeoutMs: number = VISION_ATTEMPT_TIMEOUT_MS,
): Promise<ConsultPrescription> {
  const userText = [
    `SELECTED_SERVICE: ${service}`,
    `INITIAL_STYLE: ${initialStyle || 'client_has_no_preference'}`,
    `CLIENT_TASTE: ${clientTaste}`,
    `FACE_METRICS: ${faceMetrics ? JSON.stringify(faceMetrics).slice(0, 2000) : 'none'}`,
    `Analyze CUSTOMER_PHOTO per the ARIA protocol and respond with ONLY a single JSON code block (no prose, exactly 3 options with prescription params) matching exactly: ${PRESCRIPTION_JSON_SKELETON}`,
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
        model,
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
      }),
      signal: AbortSignal.timeout(timeoutMs),
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
    throw Object.assign(new Error(`Cloudflare vision ${shortModel(model)} HTTP ${res.status}: ${msg}`), {
      status: res.status,
    });
  }

  const choices =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>).choices
      : null;
  const message =
    Array.isArray(choices) && choices[0] && typeof choices[0] === 'object'
      ? (choices[0] as Record<string, unknown>).message
      : null;
  const messageObj =
    message && typeof message === 'object' ? (message as Record<string, unknown>) : null;

  const content = messageObj && typeof messageObj.content === 'string' ? messageObj.content : '';
  const jsonMatch = content.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error(`Cloudflare vision ${shortModel(model)}: no JSON object in response`);
  }

  let parsed: unknown = null;
  try {
    parsed = JSON.parse(jsonMatch[0]);
  } catch {
    throw new Error(`Cloudflare vision ${shortModel(model)}: response is not valid JSON`);
  }

  if (!isValidPrescription(parsed)) {
    throw new Error(
      `Cloudflare vision ${shortModel(model)}: prescription failed validation (need analysis + 3 options)`,
    );
  }

  return ensureFaSummary(parsed);
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

  // تلاش سریع روی زنجیره مدل‌های آزاد با سقف زمانی کل؛ هر خطایی → دموی صادقانه، هرگز ۵۰۲
  let lastError = '';
  for (let i = 0; i < configured.length; i += 1) {
    const account = configured[i];
    for (const model of [VISION_MODEL, ...FALLBACK_VISION_MODELS]) {
      const remaining = VISION_TOTAL_DEADLINE_MS - (Date.now() - startedAt);
      if (remaining < 2000) break;
      try {
        const prescription = await callCloudflareVision(
          account,
          imageBase64,
          service,
          initialStyle,
          body.faceMetrics,
          clientTasteLine,
          model,
          Math.min(VISION_ATTEMPT_TIMEOUT_MS, remaining),
        );
        return NextResponse.json({
          ok: true,
          demo: false,
          provider: `cloudflare-vision:${i + 1}:${shortModel(model)}:json`,
          prescription,
          ms: Date.now() - startedAt,
        });
      } catch (modelError) {
        lastError = modelError instanceof Error ? modelError.message : String(modelError);
        console.error(
          `[AI-CONSULT] account ${i + 1} ${shortModel(model)} failed: ${lastError.slice(0, 300)}`,
        );
      }
    }
  }

  // فال‌بک ایمن و سریع: دموی صادقانه (بنر 🎭 در UI نشان داده می‌شود)، هرگز ۵۰۲
  console.error(
    `[AI-CONSULT] all vision attempts failed, serving demo: ${lastError.slice(0, 300)}`,
  );
  return NextResponse.json({
    ok: true,
    demo: true,
    provider: 'demo-fallback',
    prescription: buildDemoPrescription(service, initialStyle),
    ms: Date.now() - startedAt,
  });
}

export async function GET(): Promise<NextResponse> {
  const configured = accounts();
  const presence = (name: string): boolean => (process.env[name] ?? '').trim().length > 0;
  return NextResponse.json({
    ok: true,
    model: VISION_MODEL,
    fallbacks: FALLBACK_VISION_MODELS,
    accountsConfigured: configured.length,
    demo: configured.length === 0,
    // عیب‌یابی امن: فقط «هست/نیست» — هیچ مقداری فاش نمی‌شود
    env: {
      demoMode: (process.env.DEMO_MODE ?? '').trim() || '(unset→auto)',
      account1: {
        token: presence('CLOUDFLARE_API_TOKEN_1'),
        accountId: presence('CLOUDFLARE_ACCOUNT_ID_1'),
      },
      account2: {
        token: presence('CLOUDFLARE_API_TOKEN_2'),
        accountId: presence('CLOUDFLARE_ACCOUNT_ID_2'),
      },
      account3: {
        token: presence('CLOUDFLARE_API_TOKEN_3'),
        accountId: presence('CLOUDFLARE_ACCOUNT_ID_3'),
      },
    },
  });
}
