import { NextResponse } from 'next/server';

import { EYEBROW_STYLES, buildEnglishPrompt } from '@/options';
import { analyzeBeautyPhoto, buildDesignBrief } from '@/analysis';
import { styleDnaText, type UserSubjectivePreferences } from '@/style-dna';
import { generateWithFallback, configuredProviders } from '@/providers';
import { parseDataUri } from '@/providers/http';
import type { AttemptLog } from '@/providers/types';
import { recordEvent } from '@/stats';
import { readSiteImage } from '@/site-images';

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
  preferences?: UserSubjectivePreferences;
}

/** ثبت رویداد «پیش‌نمایش» برای پنل مدیریت. */
function trackPreview(styleKey: string): void {
  void recordEvent({
    type: 'preview',
    style: styleKey,
    time: new Date().toISOString(),
  });
}

interface GenerateSuccess {
  ok: true;
  provider: string;
  providerLabel: string;
  resultUrl?: string;
  demo: boolean;
  attempts: AttemptLog[];
  ms: number;
}

interface GenerateFailure {
  ok: false;
  error: string;
  attempts: AttemptLog[];
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
  const referenceImageBase64 =
    typeof body.referenceImageBase64 === 'string' ? body.referenceImageBase64.trim() : '';
  const preferences = body.preferences && typeof body.preferences === 'object' ? body.preferences : undefined;

  /* ------------------------------ اعتبارسنجی ------------------------------ */
  if (!style) return badRequest('لطفاً ابتدا مدل ابرو را انتخاب کنید.');
  if (!imageBase64) return badRequest('لطفاً عکس چهره خود را آپلود کنید.');
  if (imageBase64.length > MAX_BASE64_LENGTH) {
    return badRequest('حجم تصویر بیش از حد مجاز است. حداکثر حجم آپلود ۵ مگابایت است.');
  }

  const image = parseDataUri(imageBase64);
  let referenceImage = referenceImageBase64 ? parseDataUri(referenceImageBase64) : null;
  if (!image) {
    return badRequest('قالب تصویر پشتیبانی نمی‌شود. لطفاً عکس JPG، PNG یا WEBP آپلود کنید.');
  }
  if (image.bytes.length > MAX_BYTES) {
    return badRequest('حجم تصویر بیش از ۵ مگابایت است.');
  }
  if (referenceImage && referenceImage.bytes.length > 2 * 1024 * 1024) {
    return badRequest('تصویر مرجع مدل ابرو بیش از حد بزرگ است.');
  }

  /* -------------------------------- پرامپت -------------------------------- */
  const knownStyle = EYEBROW_STYLES.find((item) => item.label === style);
  if (!knownStyle) return badRequest('مدل ابروی انتخاب‌شده معتبر نیست.');

  const serverReference = await readSiteImage(knownStyle.imagePath);
  if (serverReference) {
    const dataUri = `data:${serverReference.mime};base64,${serverReference.buffer.toString('base64')}`;
    referenceImage = parseDataUri(dataUri);
  }

  /* ----------------------------- حالت نمایشی ------------------------------ */
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

  /* تحلیل هوشمند پرامپت */
  const analysis = await analyzeBeautyPhoto(image.dataUri);
  const designBrief = buildDesignBrief(analysis, knownStyle.key);
  const styleDna = styleDnaText(knownStyle.key, preferences);

  const prompt = buildEnglishPrompt(
    style,
    'infer_from_customer_photo',
    '',
    knownStyle.labelEn,
    knownStyle.key,
    `${designBrief} STYLE_DNA: ${styleDna}`,
  );

  /* --------------------------- زنجیرهٔ پروایدرها --------------------------- */
  try {
    const result = await generateWithFallback({
      prompt,
      image,
      referenceImage: referenceImage ?? undefined,
      designBrief,
    });

    trackPreview(knownStyle?.key ?? style);
    console.error(
      `[AI-GENERATE] SUCCESS | provider=${result.provider.id} | duration=${Date.now() - requestStartedAt}ms`,
    );

    return NextResponse.json({
      ok: true,
      provider: result.provider.id,
      providerLabel: result.provider.label,
      resultUrl: result.image,
      demo: false,
      attempts: result.attempts,
      ms: result.ms,
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

export async function GET(): Promise<NextResponse> {
  const active = configuredProviders().map((provider) => provider.id);
  return NextResponse.json({
    ok: true,
    providersConfigured: active,
    demo: isDemoActive(),
  });
}
