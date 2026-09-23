/**
 * app/api/consult/route.ts
 * ---------------------------------------------------------------------------
 * اندپوینت «مشاور کارشناس ARIA» — حلقه اول زنجیره هوش مصنوعی:
 *   عکس → توصیف چهره با LLaVA از مسیر REST (۲۰ث) → نسخه JSON با gpt-oss-20b (۲۰ث) → نسخه ساخت‌یافته
 * معماری دومرحله‌ای بدون tool (JSON خام + Regex) با سقف کل ۴۵ ثانیه؛ خطا → دموی صادقانه، هرگز ۵۰۲.
 * بدون کلید Cloudflare: نسخه نمایشی (demo) برمی‌گردد تا فلو UX نخوابد.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';
import { SERVICES_CONTENT } from '@/services-content';
import { SERVICE_TECHNIQUES } from '@/techniques';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

/**
 * معماری دومرحله‌ای (تأییدشده با مستندات Cloudflare):
 *  مرحله ۱ (بینایی): LLaVA فقط یک توصیف متنی کوتاه از چهره می‌دهد (~۲ ثانیه).
 *  مرحله ۲ (استدلال JSON): gpt-oss-20b از روی توصیف، نسخه ۳ گزینه‌ای ARIA را می‌سازد.
 * هر دو مدل آزاد و بدون لایسنس Meta هستند. شناسه llama-3.1-8b-instruct اصلاً
 * در کاتالوگ Cloudflare وجود ندارد، پس مرحله متنی با gpt-oss-20b بسته شد.
 */
const VISION_MODEL = '@cf/llava-hf/llava-1.5-7b-hf';
const TEXT_MODEL = '@cf/openai/gpt-oss-20b';

/** پرامپت ساده مرحله بینایی: توصیف کوتاه چهره، متن ساده، بدون JSON */
const VISION_DESCRIBE_PROMPT =
  'Describe only what you see in this face photo for a PMU beauty analysis: 1) Face shape, 2) Skin undertone and Fitzpatrick tone, 3) Eyebrow density, arch and symmetry, 4) Any eye/lip features. Keep it short (under 120 words), plain text, no JSON. Never invent features you cannot see.';

/** الگوی JSON خامی که در حالت بدون-tool از مدل پشتیبان خواسته می‌شود */
const PRESCRIPTION_JSON_SKELETON = `{"analysis_summary_en":"...","analysis_summary_fa":"...","face_shape":"oval|round|square|oblong|heart|diamond|unknown","symmetry_score":0-100,"skin_undertone":"warm|cool|neutral","fitzpatrick":"I|II|III|IV|V|VI","safety_flags":[],"requires_in_person":false,"confidence":0-100,"recommended_option":1-3,"options":[{"id":1,"title_en":"...","client_text_fa":"...","recommended":true,"params":{}},{"id":2,...},{"id":3,...}]}`;

/** نام کوتاه مدل برای لاگ و provider (حذف پیشوند @cf/vendor) */
function shortModel(model: string): string {
  return model.replace(/^@cf\/[^/]+\//, '') || model;
}

/** سقف زمانی واقع‌بینانه: cold-start سمت Cloudflare تا ~۳۰ ثانیه طول می‌کشد؛ هرگز ۵۰۲ */
const VISION_TIMEOUT_MS = 20000;
const TEXT_TIMEOUT_MS = 20000;
const TOTAL_DEADLINE_MS = 45000;

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

const ARIA_TEXT_SYSTEM_PROMPT = `You are ARIA, the owner of an ultra-specialized VIP permanent-makeup atelier and a master face designer with 15 years of clinical PMU experience. You speak to the client through structured data only — never in free prose.

INPUTS YOU RECEIVE:
1. FACE_DESCRIPTION — a factual visual description of the client's real face photo, written by a vision model (your source of truth about the face).
2. SELECTED_SERVICE — one of: eyebrows | lips | eyeliner | removal.
3. INITIAL_STYLE — the style/technique the client pre-selected.
4. FACE_METRICS — optional pre-computed browser measurements. Treat as measured hints; if a metric contradicts the description, trust the DESCRIPTION and ignore the metric.
5. CLIENT_TASTE — the client's stated taste. Respect it in option params; morphology and safety always win over taste.

ANALYSIS PROTOCOL (apply in this exact order):
A. FACE MORPHOLOGY — From FACE_DESCRIPTION: face shape (oval | round | square | oblong | heart | diamond), thirds/fifths proportion check, symmetry 0-100.
B. SERVICE-ZONE MICRO-ANALYSIS — eyebrows: density, thickness, arch vs. golden-ratio ideal, tail endpoint, gaps/scars; lips: volume ratio vs. 1:1.6, border, commissure symmetry, melanin 0-3; eyeliner: spacing, hooding 0-3, lash density, tilt; removal: old pigment hue/depth, distortion, scarring.
C. COLORIMETRY — Undertone (warm | cool | neutral) + Fitzpatrick (I-VI) from the description. Pigment must NEUTRALIZE the undertone. NEVER carbon-black on Fitzpatrick I-II brows; NEVER cool pigment on warm lips.
D. SAFETY TRIAGE (recommendation only, never a diagnosis) — inflammation/moles in zone → requires_in_person=true, lower confidence. Pregnancy/keloid/meds unknown → defer to salon intake form.
E. STYLE FIT — Score INITIAL_STYLE 0-100. Below 60 → still include as option 3 but not_recommended with one-line clinical reason.

OPTION LOGIC — Exactly 3 options: 1 = expert recommendation; 2 = bolder variant in safe range; 3 = client's initial wish.

OUTPUT CONTRACT (strict):
- Respond with ONLY a single JSON code block, no prose. Every claim cites evidence: "vision" | "metric:<name>" | "rule:<name>".
- Numbers plausible for a real adult face; never invent anatomy. Confidence 0-100 honest; below 70 → requires_in_person=true.
- client_text_fa: warm, feminine, respectful, 2-3 short sentences, zero jargon, zero price talk.
- analysis_summary_fa: SAME analysis in SIMPLE Persian (2-3 short sentences, zero jargon, zero invented numbers). If uncertain, say the in-person visit will finalize it — NEVER fabricate.`;

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
/* فراخوانی Cloudflare دومرحله‌ای (OpenAI-Compatible، بدون tool)            */
/* ------------------------------------------------------------------ */

type ChatMessageContent =
  | string
  | Array<{ type: 'text'; text: string } | { type: 'image_url'; image_url: { url: string } }>;

/** فراخوانی مشترک Chat Completions — متن خام پاسخ را برمی‌گرداند */
async function chatCompletion(
  account: CloudflareAccount,
  model: string,
  label: string,
  systemPrompt: string,
  userContent: ChatMessageContent,
  maxTokens: number,
  timeoutMs: number,
): Promise<string> {
  const t0 = Date.now();
  const tag = `${label} ${shortModel(model)}`;
  let res: Response;
  try {
    res = await fetch(
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
        max_tokens: maxTokens,
        seed: 42,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userContent },
        ],
      }),
      signal: AbortSignal.timeout(timeoutMs),
      cache: 'no-store',
      },
    );
  } catch (networkError) {
    const msg = networkError instanceof Error ? networkError.message : String(networkError);
    throw new Error(`Cloudflare ${tag} failed after ${Date.now() - t0}ms: ${msg}`);
  }

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
    throw Object.assign(new Error(`Cloudflare ${tag} HTTP ${res.status}: ${msg}`), {
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
  const content =
    message && typeof message === 'object'
      ? (message as Record<string, unknown>).content
      : null;
  if (typeof content !== 'string' || !content.trim()) {
    throw new Error(`Cloudflare ${tag}: empty response`);
  }
  console.error(`[AI-CONSULT] ${tag} ok in ${Date.now() - t0}ms (${content.length} chars)`);
  return content;
}

/**
 * مرحله ۱ (REST): توصیف کوتاه چهره با LLaVA.
 * ورودی/خروجی دقیقاً مطابق اسکیمای مستندات مدل (آرایه بایت + prompt؛ پاسخ description).
 * (مسیر Chat Completions برای این مدل محتوای خالی برمی‌گرداند، پس استفاده نشد.)
 */
async function callVisionDescribe(
  account: CloudflareAccount,
  imageBase64: string,
  service: string,
  timeoutMs: number,
): Promise<string> {
  const t0 = Date.now();
  const tag = `vision ${shortModel(VISION_MODEL)}`;

  // حذف پیشوند data URI و تبدیل base64 به آرایه بایت (مطابق اسکیمای ورودی مدل)
  const clean = imageBase64.replace(/^data:image\/\w+;base64,/, '').trim();
  const bytes = Array.from(Buffer.from(clean, 'base64'));
  if (bytes.length < 100) {
    throw new Error(`Cloudflare ${tag}: invalid or tiny image (${bytes.length} bytes)`);
  }

  let res: Response;
  try {
    res = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${account.accountId}/ai/run/${VISION_MODEL}`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${account.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image: bytes,
          prompt: `SELECTED_SERVICE: ${service}\n${VISION_DESCRIBE_PROMPT}`,
          max_tokens: 300,
          temperature: 0.2,
        }),
        signal: AbortSignal.timeout(timeoutMs),
        cache: 'no-store',
      },
    );
  } catch (networkError) {
    const msg = networkError instanceof Error ? networkError.message : String(networkError);
    throw new Error(`Cloudflare ${tag} failed after ${Date.now() - t0}ms: ${msg}`);
  }

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
    throw new Error(`Cloudflare ${tag} HTTP ${res.status}: ${msg}`);
  }

  const envelope =
    payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : null;
  if (envelope && envelope.success === false) {
    const msg = Array.isArray(envelope.errors)
      ? JSON.stringify(envelope.errors).slice(0, 300)
      : 'unknown error';
    throw new Error(`Cloudflare ${tag}: ${msg}`);
  }
  const result =
    envelope && typeof envelope.result === 'object' && envelope.result !== null
      ? (envelope.result as Record<string, unknown>)
      : null;
  const description =
    result && typeof result.description === 'string'
      ? result.description
      : result && typeof result.response === 'string'
        ? result.response
        : '';
  if (description.trim().length < 30) {
    throw new Error(`Cloudflare ${tag}: description too short or missing (${raw.slice(0, 200)})`);
  }
  console.error(
    `[AI-CONSULT] ${tag} ok in ${Date.now() - t0}ms (${Math.round(bytes.length / 1024)}KB image, ${description.trim().length} chars)`,
  );
  return description.trim().slice(0, 2000);
}

/** مرحله ۲: ساخت JSON نسخه ARIA با مدل متنی از روی توصیف چهره */
async function callTextPrescription(
  account: CloudflareAccount,
  faceDescription: string,
  service: string,
  initialStyle: string,
  faceMetrics: unknown,
  clientTaste: string,
  timeoutMs: number,
): Promise<ConsultPrescription> {
  const userText = [
    `FACE_DESCRIPTION: ${faceDescription}`,
    `SELECTED_SERVICE: ${service}`,
    `INITIAL_STYLE: ${initialStyle || 'client_has_no_preference'}`,
    `CLIENT_TASTE: ${clientTaste}`,
    `FACE_METRICS: ${faceMetrics ? JSON.stringify(faceMetrics).slice(0, 2000) : 'none'}`,
    `Write the ARIA expert prescription for this face as ONLY a single JSON code block (no prose, exactly 3 options with prescription params) matching exactly: ${PRESCRIPTION_JSON_SKELETON}`,
  ].join('\n');

  const content = await chatCompletion(
    account,
    TEXT_MODEL,
    'reasoning',
    ARIA_TEXT_SYSTEM_PROMPT,
    userText,
    1500,
    timeoutMs,
  );

  const jsonMatch = content.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error(`Cloudflare ${shortModel(TEXT_MODEL)}: no JSON object in response`);
  }

  let parsed: unknown = null;
  try {
    parsed = JSON.parse(jsonMatch[0]);
  } catch {
    throw new Error(`Cloudflare ${shortModel(TEXT_MODEL)}: response is not valid JSON`);
  }

  if (!isValidPrescription(parsed)) {
    throw new Error(
      `Cloudflare ${shortModel(TEXT_MODEL)}: prescription failed validation (need analysis + 3 options)`,
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

  // دومرحله‌ای برای هر اکانت: توصیف بینایی (۶ث) → نسخه متنی (۶ث)؛ خطا → دموی صادقانه، هرگز ۵۰۲
  let lastError = '';
  for (let i = 0; i < configured.length; i += 1) {
    const account = configured[i];
    const remainingBefore = TOTAL_DEADLINE_MS - (Date.now() - startedAt);
    if (remainingBefore < 8000) break;
    try {
      const faceDescription = await callVisionDescribe(
        account,
        imageBase64,
        service,
        Math.min(VISION_TIMEOUT_MS, remainingBefore),
      );
      const remainingAfterVision = TOTAL_DEADLINE_MS - (Date.now() - startedAt);
      if (remainingAfterVision < 5000) {
        throw new Error('vision ok but no time left for reasoning step');
      }
      const prescription = await callTextPrescription(
        account,
        faceDescription,
        service,
        initialStyle,
        body.faceMetrics,
        clientTasteLine,
        Math.min(TEXT_TIMEOUT_MS, remainingAfterVision),
      );
      const okMs = Date.now() - startedAt;
      console.error(`[AI-CONSULT] account ${i + 1} 2-stage ok in ${okMs}ms (vision+reasoning)`);
      return NextResponse.json({
        ok: true,
        demo: false,
        provider: `cloudflare-2stage:${i + 1}:${shortModel(VISION_MODEL)}+${shortModel(TEXT_MODEL)}`,
        prescription,
        ms: okMs,
      });
    } catch (stageError) {
      lastError = stageError instanceof Error ? stageError.message : String(stageError);
      console.error(
        `[AI-CONSULT] account ${i + 1} 2-stage failed: ${lastError.slice(0, 300)}`,
      );
    }
  }

  // فال‌بک ایمن و سریع: دموی صادقانه (بنر 🎭 در UI نشان داده می‌شود)، هرگز ۵۰۲
  console.error(
    `[AI-CONSULT] all 2-stage attempts failed, serving demo: ${lastError.slice(0, 300)}`,
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
    textModel: TEXT_MODEL,
    budgets: { visionMs: VISION_TIMEOUT_MS, textMs: TEXT_TIMEOUT_MS, totalMs: TOTAL_DEADLINE_MS },
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
