/**
 * app/api/generate/route.ts
 * ---------------------------------------------------------------------------
 * تنها روت سرور: دریافت عکس چهره + سبک + رنگ و ساخت پیش‌نمایش با هوش مصنوعی.
 *
 * نکتهٔ امنیتی: همهٔ کلیدهای API فقط در همین لایه (سرور) خوانده می‌شوند و
 * هیچ‌گاه به مرورگر فرستاده نمی‌شوند.
 * ---------------------------------------------------------------------------
 */

import { NextResponse } from 'next/server';

import { EYEBROW_STYLES, buildEnglishPrompt } from '@/options';
import { analyzeBeautyPhoto, type BeautyPhotoAnalysis } from '@/analysis';
import { generateWithFallback, configuredProviders } from '@/providers';
import { parseDataUri } from '@/providers/http';
import type { AttemptLog } from '@/providers/types';
import { recordEvent } from '@/stats';
import { applyVisionQuality } from '@/vision';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

/** حداکثر اندازهٔ مجاز عکس در سمت سرور (۵ مگابایت) */
const MAX_BYTES = 5 * 1024 * 1024;
/** ~۶.۸ مگابایت base64 برای ۵ مگابایت بایت */
const MAX_BASE64_LENGTH = Math.ceil((MAX_BYTES * 4) / 3) + 1024 * 1024;

interface GenerateBody {
  imageBase64?: unknown;
  style?: unknown;
  colorName?: unknown;
  colorHex?: unknown;
  referenceImageBase64?: unknown;
}

/** ثبت رویداد «پیش‌نمایش» برای پنل مدیریت. خطاهای آن نادیده گرفته می‌شوند. */
function trackPreview(styleKey: string): void {
  void recordEvent({
    type: 'preview',
    style: styleKey,
    time: new Date().toISOString(),
  });
}

interface GenerateSuccess {
  ok: true;
  /** 'openrouter' | 'cloudflare' | 'pollinations' | 'demo' */
  provider: string;
  providerLabel: string;
  /** data URI یا آدرس تصویر (در حالت نمایشی خالی است و کلاینت خودش می‌سازد) */
  resultUrl?: string;
  /** true یعنی حالت نمایشی محلی (بدون کلید API) */
  demo: boolean;
  attempts: AttemptLog[];
  ms: number;
  analysis?: BeautyPhotoAnalysis;
}

interface GenerateFailure {
  ok: false;
  error: string;
  attempts: AttemptLog[];
  analysis?: BeautyPhotoAnalysis;
}

function badRequest(error: string): NextResponse<GenerateFailure> {
  return NextResponse.json({ ok: false, error, attempts: [] }, { status: 400 });
}

type DemoMode = 'auto' | 'on' | 'off';

function demoMode(): DemoMode {
  const raw = (process.env.DEMO_MODE ?? 'auto').trim().toLowerCase();
  if (raw === 'on' || raw === '1' || raw === 'true') return 'on';
  if (raw === 'off' || raw === '0' || raw === 'false') return 'off';
  return 'auto';
}

/** آیا حالت نمایشی فعال است؟ (auto = فقط وقتی هیچ کلید API‌ای تنظیم نشده باشد) */
function isDemoActive(): boolean {
  const mode = demoMode();
  if (mode === 'on') return true;
  if (mode === 'off') return false;
  return configuredProviders().length === 0;
}

export async function POST(request: Request): Promise<NextResponse<GenerateSuccess | GenerateFailure>> {
  const requestStartedAt = Date.now();
  console.error('[AI-GENERATE] START');

  let body: GenerateBody;
  try {
    body = (await request.json()) as GenerateBody;
  } catch {
    console.error('[AI-GENERATE] BAD_REQUEST | invalid JSON');
    return badRequest('بدنهٔ درخواست نامعتبر است (JSON خوانده نشد).');
  }

  const imageBase64 = typeof body.imageBase64 === 'string' ? body.imageBase64 : '';
  const style = typeof body.style === 'string' ? body.style.trim() : '';
  const colorName = typeof body.colorName === 'string' ? body.colorName.trim() : '';
  const colorHex = typeof body.colorHex === 'string' ? body.colorHex.trim() : '';
  const referenceImageBase64 = typeof body.referenceImageBase64 === 'string' ? body.referenceImageBase64.trim() : '';

  /* ------------------------------ اعتبارسنجی ------------------------------ */
  if (!style) return badRequest('لطفاً ابتدا مدل ابرو را انتخاب کنید.');
  // رنگ دیگر از کاربر دریافت نمی‌شود؛ برای سازگاری با کلاینت قدیمی فیلدها پذیرفته می‌شوند،
  // اما رنگ واقعی باید از تحلیل عکس تعیین شود.
  if (!imageBase64) return badRequest('لطفاً عکس چهره خود را آپلود کنید.');
  if (imageBase64.length > MAX_BASE64_LENGTH) {
    return badRequest('حجم تصویر بیش از حد مجاز است. حداکثر حجم آپلود ۵ مگابایت است.');
  }

  const image = parseDataUri(imageBase64);
  const referenceImage = referenceImageBase64 ? parseDataUri(referenceImageBase64) : null;
  if (!image) {
    return badRequest('قالب تصویر پشتیبانی نمی‌شود. لطفاً عکس JPG، PNG یا WEBP آپلود کنید.');
  }
  if (image.bytes.length > MAX_BYTES) {
    return badRequest('حجم تصویر بیش از ۵ مگابایت است.');
  }
  if (referenceImage && referenceImage.bytes.length > 2 * 1024 * 1024) {
    return badRequest('تصویر مرجع مدل ابرو بیش از حد بزرگ است.');
  }

  /* ----------------------------- حالت نمایشی ------------------------------ */
  // حالت نمایشی نباید به Vision یا API خارجی وابسته باشد.
  if (isDemoActive()) {
    trackPreview(knownStyle.key);
    console.error(`[AI-GENERATE] DEMO_SUCCESS | duration=${Date.now() - requestStartedAt}ms`);
    return NextResponse.json({
      ok: true,
      provider: 'demo',
      providerLabel: 'حالت نمایشی',
      demo: true,
      attempts: [],
      ms: 0,
    });
  }

  /* -------------------------------- پرامپت -------------------------------- */
  const knownStyle = EYEBROW_STYLES.find((item) => item.label === style);
  if (!knownStyle) return badRequest('مدل ابروی انتخاب‌شده معتبر نیست.');

  let analysis: BeautyPhotoAnalysis | null = null;
  try {
    analysis = await analyzeBeautyPhoto(image.dataUri);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'تحلیل عکس در دسترس نیست';
    const detail = error instanceof Error && 'detail' in error
      ? String((error as { detail?: unknown }).detail ?? '')
      : '';
    console.error(`[AI-ANALYSIS] FAILED | ${message}${detail ? ` | ${detail}` : ''}`);
    return NextResponse.json(
      { ok: false, error: 'تحلیل هوشمند عکس انجام نشد. لطفاً دوباره تلاش کنید.', attempts: [] },
      { status: 502 },
    );
  }

  if (!analysis.acceptable || !analysis.faceVisible || !analysis.eyebrowsVisible) {
    return NextResponse.json(
      {
        ok: false,
        error: analysis.message || 'عکس برای پیش‌نمایش مناسب نیست. لطفاً عکس واضح و روبه‌رو ارسال کنید.',
        attempts: [],
        analysis,
      },
      { status: 422 },
    );
  }

  const designBrief = JSON.stringify({
    photo_quality: analysis.imageQuality,
    face_shape: analysis.faceShape,
    current_brow: {
      density: analysis.browDensity,
      thickness: analysis.browThickness,
      arch: analysis.browArch,
      symmetry: analysis.browSymmetry,
    },
    natural_color: {
      hair_tone: analysis.hairTone,
      brow_tone: analysis.browTone,
      skin_undertone: analysis.skinUndertone,
      pigment_family: analysis.pigmentFamily,
      pigment_temperature: analysis.pigmentTemperature,
      pigment_depth: analysis.pigmentDepth,
      avoid: analysis.avoidPigments,
    },
  });

  const prompt = buildEnglishPrompt(
    style,
    analysis.pigmentFamily,
    '',
    knownStyle.labelEn,
    knownStyle.key,
    designBrief,
  );

  /* --------------------------- زنجیرهٔ پروایدرها --------------------------- */
  try {
    const result = await generateWithFallback({ prompt, image, referenceImage: referenceImage ?? undefined, designBrief });
    const vision = await applyVisionQuality(image.dataUri, result.image, 'eyebrows');
    const finalImage = vision?.result ?? result.image;
    trackPreview(knownStyle?.key ?? style);
    console.error(
      `[AI-GENERATE] SUCCESS | provider=${result.provider.id} | duration=${Date.now() - requestStartedAt}ms`,
    );
    return NextResponse.json({
      ok: true,
      provider: result.provider.id,
      providerLabel: result.provider.label,
      resultUrl: finalImage,
      demo: false,
      attempts: result.attempts,
      ms: result.ms,
      analysis,
    });
  } catch (error) {
    const attempts = (error as { attempts?: AttemptLog[] })?.attempts ?? [];
    const message = error instanceof Error ? error.message : 'خطای ناشناخته در ساخت تصویر';
    const failedSummary = attempts
      .filter((attempt) => !attempt.ok && attempt.error)
      .map((attempt) => `${attempt.provider}=${attempt.error}`)
      .join(' | ');

    console.error(
      `[AI-GENERATE] FAILED | status=502 | duration=${Date.now() - requestStartedAt}ms | ${failedSummary || message}`,
    );

    return NextResponse.json({ ok: false, error: message, attempts }, { status: 502 });
  }
}

/** بررسی سریع وضعیت سرویس (چه پروایدرهایی فعال‌اند) — بدون افشای کلیدها */
export async function GET(): Promise<NextResponse> {
  const active = configuredProviders().map((provider) => provider.id);
  return NextResponse.json({
    ok: true,
    providersConfigured: active,
    demo: isDemoActive(),
  });
}
