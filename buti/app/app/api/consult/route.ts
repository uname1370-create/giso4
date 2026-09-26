/**
 * app/api/consult/route.ts
 * ---------------------------------------------------------------------------
 * اندپوینت «مشاور کارشناس ARIA» — حلقه اول زنجیره هوش مصنوعی:
 *   عکس + خدمت + استایل اولیه → تحلیل بینایی (JSON) → نسخه ساخت‌یافته
 * زنجیره ترکیبی (ارزان اول): Cloudflare Vision (رایگان) → Pollinations (پولی/اثبات‌شده) → دموی صادقانه.
 * خطا → دموی صادقانه، هرگز ۵۰۲.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';
import { SERVICES_CONTENT } from '@/services-content';
import { SERVICE_TECHNIQUES } from '@/techniques';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 120;

/**
 * زنجیره تحلیل (تأییدشده با مستندات رسمی):
 *  ۱) Cloudflare @cf/meta/llama-3.2-11b-vision-instruct — $0.0485/$0.676 به‌ازای 1M توکن
 *     ≈ ‎۰٫۰۰۱۲$ برای هر تحلیل، رایگان تا ~۹۵ تحلیل در روز برای هر حساب (سهمیه ۱۰هزار نورون).
 *  ۲) Pollinations openai/gpt-5.4-nano — ~۰٫۰۰۱ pollen برای هر تحلیل (پولی از اولین فراخوانی).
 * ترتیب = ارزان اول؛ با CLOUDFLARE_VISION_MODEL/POLLINATIONS_VISION_MODEL قابل تغییر است.
 */
const POLLINATIONS_BASE_URL = 'https://gen.pollinations.ai/v1';
const POLLINATIONS_MODEL =
  (process.env.POLLINATIONS_VISION_MODEL ?? '').trim() || 'openai/gpt-5.4-nano';
const CLOUDFLARE_VISION_MODEL =
  (process.env.CLOUDFLARE_VISION_MODEL ?? '').trim() ||
  '@cf/meta/llama-3.2-11b-vision-instruct';

/** سقف هر تلاش تحلیل: ۱۵ ثانیه (تحلیل سالم زیر ۱۰ ثانیه؛ بیشتر یعنی صف/اختلال) */
const CONSULT_TIMEOUT_MS = (() => {
  const raw = Number(process.env.CONSULT_TIMEOUT_MS);
  return Number.isFinite(raw) && raw > 1000 ? raw : 15_000;
})();

/** کلید سروری Pollinations (sk_...) — طبق مستندات، همه درخواست‌های تولید به کلید نیاز دارند */
function pollinationsKey(): string {
  return (process.env.POLLINATIONS_API_KEY ?? '').trim();
}

/** حساب اول کلادفلر (برای تحلیل بینایی) */
function cloudflareAccount(): { token: string; accountId: string } | null {
  const token = (process.env.CLOUDFLARE_API_TOKEN_1 ?? '').trim();
  const accountId = (process.env.CLOUDFLARE_ACCOUNT_ID_1 ?? '').trim();
  return token && accountId ? { token, accountId } : null;
}

/** الگوی JSON خامی که در حالت بدون-tool از مدل پشتیبان خواسته می‌شود */
const PRESCRIPTION_JSON_SKELETON = `{"analysis_summary_en":"...","analysis_summary_fa":"...","face_shape":"oval|round|square|oblong|heart|diamond|unknown","symmetry_score":0-100,"skin_undertone":"warm|cool|neutral","fitzpatrick":"I|II|III|IV|V|VI","safety_flags":[],"requires_in_person":false,"confidence":0-100,"recommended_option":1-3,"options":[{"id":1,"title_en":"...","client_text_fa":"...","recommended":true,"params":{}},{"id":2,...},{"id":3,...}]}`;

/** سقف طول base64 ورودی (~۶ مگابایت عکس) */
const MAX_BASE64_LENGTH = 8_500_000;

/* ------------------------------------------------------------------ */
/* پرامپت سیستم ARIA (سند زنجیره هوش مصنوعی — نسخه مصوب)                  */
/* ------------------------------------------------------------------ */

const ARIA_VISION_SYSTEM_PROMPT = `You are ARIA, the owner of an ultra-specialized VIP permanent-makeup atelier and a master face designer with 15 years of clinical PMU experience. You speak to the client through structured data only — never in free prose.

INPUTS YOU RECEIVE:
1. CUSTOMER_PHOTO — the client's real, unedited face photo (source of truth).
2. SELECTED_SERVICE — one of: eyebrows | lips | eyeliner | removal.
3. INITIAL_STYLE — the style/technique the client pre-selected.
4. FACE_METRICS — optional pre-computed browser measurements. Treat as measured hints; if a metric contradicts what you see, trust the PHOTO and ignore the metric.
5. CLIENT_TASTE — the client's stated taste. Respect it in option params; morphology and safety always win over taste.

ANALYSIS PROTOCOL (apply in this exact order):
A. FACE MORPHOLOGY — From the photo: face shape (oval | round | square | oblong | heart | diamond), thirds/fifths proportion check, symmetry 0-100.
B. SERVICE-ZONE MICRO-ANALYSIS — eyebrows: density, thickness, arch vs. golden-ratio ideal, tail endpoint, gaps/scars; lips: volume ratio vs. 1:1.6, border, commissure symmetry, melanin 0-3; eyeliner: spacing, hooding 0-3, lash density, tilt; removal: old pigment hue/depth, distortion, scarring.
C. COLORIMETRY — Undertone (warm | cool | neutral) + Fitzpatrick (I-VI) from the photo. Pigment must NEUTRALIZE the undertone. NEVER carbon-black on Fitzpatrick I-II brows; NEVER cool pigment on warm lips.
D. SAFETY TRIAGE (recommendation only, never a diagnosis) — inflammation/moles in zone → requires_in_person=true, lower confidence. Pregnancy/keloid/meds unknown → defer to salon intake form.
E. STYLE FIT — Score INITIAL_STYLE 0-100. Below 60 → still include as option 3 but not_recommended with one-line clinical reason.

OPTION LOGIC — Exactly 3 options: 1 = expert recommendation; 2 = bolder variant in safe range; 3 = client's initial wish.

OUTPUT CONTRACT (strict):
- Respond with ONLY a single JSON object, no prose. Every claim cites evidence: "photo" | "metric:<name>" | "rule:<name>".
- Numbers plausible for a real adult face; never invent anatomy. Confidence 0-100 honest; below 70 → requires_in_person=true.
- client_text_fa: warm, feminine, respectful, 2-3 short sentences, zero jargon, zero price talk.
- analysis_summary_fa: SAME analysis in SIMPLE Persian (2-3 short sentences, zero jargon, zero invented numbers). If uncertain, say the in-person visit will finalize it — NEVER fabricate.`;

/* ------------------------------------------------------------------ */
/* توجه: فراخوانی بینایی عمداً بدون tool است.                              */
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

interface ConsultAttempt {
  provider: string;
  ok: boolean;
  ms: number;
  error?: string;
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

/**
 * استخراج مشترک نسخه از متن خام هر دو پروایدر (Regex + اعتبارسنجی).
 */
function extractPrescription(content: string, who: string): ConsultPrescription {
  const jsonMatch = content.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error(`${who}: no JSON object in response`);
  }

  let parsed: unknown = null;
  try {
    parsed = JSON.parse(jsonMatch[0]);
  } catch {
    throw new Error(`${who}: response is not valid JSON`);
  }

  if (!isValidPrescription(parsed)) {
    throw new Error(`${who}: prescription failed validation (need analysis + 3 options)`);
  }

  return ensureFaSummary(parsed);
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
/* فراخوانی Cloudflare Vision (مسیر اول — رایگان)                           */
/* ------------------------------------------------------------------ */

/** متن کاربر مشترک هر دو پروایدر (همان ورودی ARIA) */
function buildUserText(
  service: string,
  initialStyle: string,
  faceMetrics: unknown,
  clientTaste: string,
): string {
  return [
    `SELECTED_SERVICE: ${service}`,
    `INITIAL_STYLE: ${initialStyle || 'client_has_no_preference'}`,
    `CLIENT_TASTE: ${clientTaste}`,
    `FACE_METRICS: ${faceMetrics ? JSON.stringify(faceMetrics).slice(0, 2000) : 'none'}`,
    `Analyze CUSTOMER_PHOTO per the ARIA protocol and respond with ONLY a single JSON object (no prose, exactly 3 options with prescription params) matching exactly: ${PRESCRIPTION_JSON_SKELETON}`,
  ].join('\n');
}

function toImageDataUri(imageBase64: string): string {
  return imageBase64.startsWith('data:')
    ? imageBase64
    : `data:image/jpeg;base64,${imageBase64}`;
}

/** تحلیل بینایی کلادفلر: messages با عکس (طبق مستندات، image جدا deprecated است) */
async function callCloudflareVision(
  imageBase64: string,
  service: string,
  initialStyle: string,
  faceMetrics: unknown,
  clientTaste: string,
): Promise<ConsultPrescription> {
  const account = cloudflareAccount();
  if (!account) {
    throw new Error('Cloudflare: CLOUDFLARE_API_TOKEN_1/ACCOUNT_ID_1 تنظیم نشده است');
  }
  const t0 = Date.now();

  let res: Response;
  try {
    res = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${account.accountId}/ai/run/${CLOUDFLARE_VISION_MODEL}`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${account.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: [
            { role: 'system', content: ARIA_VISION_SYSTEM_PROMPT },
            {
              role: 'user',
              content: [
                {
                  type: 'text',
                  text: buildUserText(service, initialStyle, faceMetrics, clientTaste),
                },
                { type: 'image_url', image_url: { url: toImageDataUri(imageBase64) } },
              ],
            },
          ],
          max_tokens: 1500,
          temperature: 0.2,
          top_p: 0.9,
        }),
        signal: AbortSignal.timeout(CONSULT_TIMEOUT_MS),
        cache: 'no-store',
      },
    );
  } catch (networkError) {
    const msg = networkError instanceof Error ? networkError.message : String(networkError);
    throw new Error(`Cloudflare vision failed after ${Date.now() - t0}ms: ${msg}`);
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
    throw new Error(`Cloudflare vision HTTP ${res.status}: ${msg}`);
  }

  const result =
    payload && typeof payload === 'object'
      ? (payload as Record<string, unknown>).result
      : null;
  const content =
    typeof result === 'string'
      ? result
      : result && typeof result === 'object'
        ? (result as Record<string, unknown>).response
        : null;
  if (typeof content !== 'string' || !content.trim()) {
    throw new Error('Cloudflare vision: empty response');
  }

  console.error(
    `[AI-CONSULT] cloudflare vision ok in ${Date.now() - t0}ms (${content.length} chars)`,
  );
  return extractPrescription(content, 'Cloudflare vision');
}

/* ------------------------------------------------------------------ */
/* فراخوانی Pollinations Vision (مسیر دوم — پولی/اثبات‌شده)                  */
/* ------------------------------------------------------------------ */

/** تحلیل بینایی Pollinations (عکس + ARIA → JSON نسخه) */
async function callPollinationsVision(
  imageBase64: string,
  service: string,
  initialStyle: string,
  faceMetrics: unknown,
  clientTaste: string,
): Promise<ConsultPrescription> {
  const t0 = Date.now();
  const userText = buildUserText(service, initialStyle, faceMetrics, clientTaste);
  const imageUrl = toImageDataUri(imageBase64);

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const key = pollinationsKey();
  if (key) headers.Authorization = `Bearer ${key}`;

  let res: Response;
  try {
    res = await fetch(`${POLLINATIONS_BASE_URL}/chat/completions`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        model: POLLINATIONS_MODEL,
        temperature: 0.2,
        top_p: 0.9,
        max_tokens: 1500,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: ARIA_VISION_SYSTEM_PROMPT },
          {
            role: 'user',
            content: [
              { type: 'text', text: userText },
              { type: 'image_url', image_url: { url: imageUrl } },
            ],
          },
        ],
      }),
      signal: AbortSignal.timeout(CONSULT_TIMEOUT_MS),
      cache: 'no-store',
    });
  } catch (networkError) {
    const msg = networkError instanceof Error ? networkError.message : String(networkError);
    throw new Error(`Pollinations failed after ${Date.now() - t0}ms: ${msg}`);
  }

  const raw = await res.text();
  let payload: unknown = null;
  try {
    payload = raw ? JSON.parse(raw) : null;
  } catch {
    payload = null;
  }

  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      throw new Error(
        'Pollinations: missing or invalid POLLINATIONS_API_KEY — get one at enter.pollinations.ai/keys',
      );
    }
    const msg =
      payload && typeof payload === 'object'
        ? JSON.stringify(payload).slice(0, 300)
        : raw.slice(0, 300);
    throw new Error(`Pollinations HTTP ${res.status}: ${msg}`);
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
    throw new Error('Pollinations: empty response');
  }

  console.error(
    `[AI-CONSULT] pollinations vision ok in ${Date.now() - t0}ms (${content.length} chars)`,
  );
  return extractPrescription(content, 'Pollinations');
}

/* ------------------------------------------------------------------ */

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

  /* -------------------- زنجیره ترکیبی: ارزان اول -------------------- */
  const attempts: ConsultAttempt[] = [];
  let prescription: ConsultPrescription | null = null;
  let providerLabel = '';

  // مسیر ۱: Cloudflare Vision (رایگان تا ~۹۵ تحلیل/روز/حساب)
  if (cloudflareAccount()) {
    const t0 = Date.now();
    try {
      prescription = await callCloudflareVision(
        imageBase64,
        service,
        initialStyle,
        body.faceMetrics,
        clientTasteLine,
      );
      providerLabel = `cloudflare:${CLOUDFLARE_VISION_MODEL}`;
      attempts.push({ provider: 'cloudflare', ok: true, ms: Date.now() - t0 });
      console.error(`[AI-CONSULT] cloudflare ok in ${Date.now() - startedAt}ms`);
    } catch (cfError) {
      const msg = cfError instanceof Error ? cfError.message : String(cfError);
      attempts.push({
        provider: 'cloudflare',
        ok: false,
        ms: Date.now() - t0,
        error: msg.slice(0, 200),
      });
      console.error(`[AI-CONSULT] cloudflare failed: ${msg.slice(0, 300)}`);
    }
  } else {
    console.error('[AI-CONSULT] cloudflare skipped (no CLOUDFLARE_API_TOKEN_1)');
  }

  // مسیر ۲: Pollinations Vision (پولی/اثبات‌شده)
  if (!prescription && pollinationsKey()) {
    const t0 = Date.now();
    try {
      prescription = await callPollinationsVision(
        imageBase64,
        service,
        initialStyle,
        body.faceMetrics,
        clientTasteLine,
      );
      providerLabel = `pollinations:${POLLINATIONS_MODEL}`;
      attempts.push({ provider: 'pollinations', ok: true, ms: Date.now() - t0 });
      console.error(
        `[AI-CONSULT] pollinations ok in ${Date.now() - startedAt}ms (${POLLINATIONS_MODEL})`,
      );
    } catch (aiError) {
      const msg = aiError instanceof Error ? aiError.message : String(aiError);
      attempts.push({
        provider: 'pollinations',
        ok: false,
        ms: Date.now() - t0,
        error: msg.slice(0, 200),
      });
      console.error(`[AI-CONSULT] pollinations failed: ${msg.slice(0, 300)}`);
    }
  } else if (!prescription) {
    console.error('[AI-CONSULT] pollinations skipped (no POLLINATIONS_API_KEY)');
  }

  // مسیر ۳: دموی صادقانه با بازتاب سلیقه (بنر 🎭 در UI نشان داده می‌شود)
  if (!prescription) {
    const demo = buildDemoPrescription(service, initialStyle);
    for (const opt of demo.options) {
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
      provider: 'demo-fallback',
      prescription: demo,
      ms: Date.now() - startedAt,
      attempts,
    });
  }

  return NextResponse.json({
    ok: true,
    demo: false,
    provider: providerLabel,
    prescription,
    ms: Date.now() - startedAt,
    attempts,
  });
}

export async function GET(): Promise<NextResponse> {
  const pollKeyConfigured = pollinationsKey().length > 0;
  const cfConfigured = cloudflareAccount() !== null;
  return NextResponse.json({
    ok: true,
    provider: 'cloudflare,pollinations',
    chain: ['cloudflare', 'pollinations', 'demo-fallback'],
    cloudflare: {
      endpoint: '/ai/run',
      model: CLOUDFLARE_VISION_MODEL,
      keyConfigured: cfConfigured,
    },
    pollinations: {
      endpoint: `${POLLINATIONS_BASE_URL}/chat/completions`,
      model: POLLINATIONS_MODEL,
      // عیب‌یابی امن: فقط «هست/نیست» — مقدار کلید هرگز فاش نمی‌شود
      keyConfigured: pollKeyConfigured,
    },
    timeoutMs: CONSULT_TIMEOUT_MS,
    demo: !cfConfigured && !pollKeyConfigured,
    note:
      cfConfigured || pollKeyConfigured
        ? 'AI analysis via Cloudflare (free tier first) + Pollinations fallback.'
        : 'Set CLOUDFLARE_API_TOKEN_1/ACCOUNT_ID_1 or POLLINATIONS_API_KEY to enable real AI analysis.',
  });
}
