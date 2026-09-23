import { ProviderError } from './providers/http';

export interface BeautyPhotoAnalysis {
  acceptable: boolean;
  reason: string;
  message: string;
  faceVisible: boolean;
  eyebrowsVisible: boolean;
  imageQuality: 'good' | 'acceptable' | 'poor';
  faceShape: string;
  browDensity: string;
  browThickness: string;
  browArch: string;
  browSymmetry: string;
  hairTone: string;
  browTone: string;
  skinUndertone: string;
  pigmentFamily: string;
  pigmentTemperature: string;
  pigmentDepth: string;
  avoidPigments: string[];
}

const DEFAULT_MODEL = '@cf/moondream/moondream3.1-9B-A2B';

function accounts(): Array<{ token: string; accountId: string }> {
  return [1, 2, 3]
    .map((index) => ({
      token: (process.env[`CLOUDFLARE_API_TOKEN_${index}`] ?? '').trim(),
      accountId: (process.env[`CLOUDFLARE_ACCOUNT_ID_${index}`] ?? '').trim(),
    }))
    .filter((item) => item.token && item.accountId);
}

function model(): string {
  return (process.env.CLOUDFLARE_VISION_MODEL ?? '').trim() || DEFAULT_MODEL;
}

function cleanJson(text: string): string {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fenced?.[1]) return fenced[1].trim();
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  return start >= 0 && end > start ? text.slice(start, end + 1) : text;
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

function boolValue(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function listValue(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string').slice(0, 6) : [];
}

export async function analyzeBeautyPhoto(imageDataUri: string): Promise<BeautyPhotoAnalysis> {
  const account = accounts()[0];
  if (!account) {
    throw new ProviderError('Cloudflare Vision: حساب فعال پیدا نشد');
  }

  const prompt = `Analyze this exact customer face photo for a professional eyebrow microblading preview.

Return ONLY valid JSON. Do not use markdown.

Rules:
- Check whether one clear face is visible.
- Check whether both eyebrows are sufficiently visible.
- Reject photos that are blurry, extremely dark/bright, heavily filtered, strongly angled, obstructed, or have eyebrows hidden by hair/glasses.
- Do NOT invent precise medical or biometric facts.
- Analyze only visible visual characteristics.
- Treat the customer's original eyebrows as the source of truth. Do not invent a new brow shape.
- Carefully assess visible brow density, thickness, arch character, symmetry, natural start and tail character, and the existing hair-growth direction.
- For pigment, match the customer's actual visible brow and hair tone first, then account for visible skin undertone. Estimate family, temperature and depth from the photo; do not choose a fixed website color or HEX value.
- Never recommend pure black by default. Avoid artificial orange/red casts unless clearly present in the customer's natural brow/hair.
- The generated preview must preserve the customer's original brow position, facial proportions, skin appearance and natural asymmetry.
- The goal is a realistic microblading preview, not beautifying, face reshaping, skin retouching, or inventing a new eyebrow anatomy.

JSON shape:
{
  "acceptable": true,
  "reason": "good_photo",
  "message": "short Persian user-facing message",
  "faceVisible": true,
  "eyebrowsVisible": true,
  "imageQuality": "good",
  "faceShape": "oval",
  "browDensity": "medium",
  "browThickness": "medium",
  "browArch": "soft",
  "browSymmetry": "slightly_asymmetric",
  "hairTone": "dark_brown",
  "browTone": "medium_dark_brown",
  "skinUndertone": "warm_neutral",
  "pigmentFamily": "natural_brown",
  "pigmentTemperature": "neutral_warm",
  "pigmentDepth": "medium_dark",
  "avoidPigments": ["pure_black", "strong_red", "orange"]
}`;

  const response = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${account.accountId}/ai/run/${model()}`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${account.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        task: 'query',
        image: imageDataUri,
        question: prompt,
        reasoning: false,
        stream: false,
        temperature: 0.1,
        max_tokens: 1200,
      }),
      cache: 'no-store',
    },
  );

  const raw = await response.text();
  let payload: unknown = null;
  try { payload = raw ? JSON.parse(raw) : null; } catch { payload = null; }

  if (!response.ok) {
    const detail =
      payload && typeof payload === 'object' && typeof (payload as Record<string, unknown>).error === 'string'
        ? String((payload as Record<string, unknown>).error)
        : raw.slice(0, 400);
    throw new ProviderError('Cloudflare Vision: تحلیل عکس ناموفق بود', detail);
  }

  const result = payload && typeof payload === 'object'
    ? (payload as Record<string, unknown>).result
    : null;
  const answer =
    result && typeof result === 'object' && typeof (result as Record<string, unknown>).answer === 'string'
      ? String((result as Record<string, unknown>).answer)
      : '';

  if (!answer) {
    throw new ProviderError('Cloudflare Vision: پاسخ تحلیل عکس خالی بود');
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(cleanJson(answer)) as Record<string, unknown>;
  } catch {
    throw new ProviderError('Cloudflare Vision: پاسخ JSON قابل پردازش نبود', answer.slice(0, 500));
  }

  const acceptable = boolValue(parsed.acceptable);
  const faceVisible = boolValue(parsed.faceVisible);
  const eyebrowsVisible = boolValue(parsed.eyebrowsVisible);

  return {
    acceptable,
    reason: stringValue(parsed.reason, acceptable ? 'good_photo' : 'photo_not_suitable'),
    message: stringValue(
      parsed.message,
      acceptable
        ? 'عکس برای پیش‌نمایش مناسب است.'
        : 'لطفاً عکس واضح‌تر و روبه‌رو، بدون پوشش روی ابروها ارسال کنید.',
    ),
    faceVisible,
    eyebrowsVisible,
    imageQuality: ['good', 'acceptable', 'poor'].includes(String(parsed.imageQuality))
      ? String(parsed.imageQuality) as BeautyPhotoAnalysis['imageQuality']
      : 'acceptable',
    faceShape: stringValue(parsed.faceShape, 'natural'),
    browDensity: stringValue(parsed.browDensity, 'medium'),
    browThickness: stringValue(parsed.browThickness, 'medium'),
    browArch: stringValue(parsed.browArch, 'soft'),
    browSymmetry: stringValue(parsed.browSymmetry, 'natural'),
    hairTone: stringValue(parsed.hairTone, 'natural'),
    browTone: stringValue(parsed.browTone, 'natural'),
    skinUndertone: stringValue(parsed.skinUndertone, 'neutral'),
    pigmentFamily: stringValue(parsed.pigmentFamily, 'natural_brown'),
    pigmentTemperature: stringValue(parsed.pigmentTemperature, 'neutral'),
    pigmentDepth: stringValue(parsed.pigmentDepth, 'medium'),
    avoidPigments: listValue(parsed.avoidPigments),
  };
}
