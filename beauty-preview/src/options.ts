/**
 * src/options.ts
 * ---------------------------------------------------------------------------
 * داده‌های ثابت صفحه: ۴ سبک ابرو، ۶ رنگ، و ساخت لینک واتساپ.
 * ---------------------------------------------------------------------------
 */

import { browPreviewUri, type BrowStyleKey } from './brow-shapes';

export interface EyebrowStyle {
  /** کلید داخلی (به API فرستاده نمی‌شود؛ فقط برای شناسایی در UI) */
  key: BrowStyleKey;
  /** نام فارسی که در پرامپت هوش مصنوعی و پیام واتساپ استفاده می‌شود */
  label: string;
  /** معادل انگلیسی سبک (برای پرامپت مدل تصویری) */
  labelEn: string;
  /** توضیح کوتاه زیر نام */
  hint: string;
  /**
   * مسیر فایل تصویر واقعی این مدل داخل پوشهٔ public.
   * مدیر از پنل (/admin → تصاویر ابرو) همین فایل را آپلود می‌کند:
   *   /eyebrows/natural-hairstroke.jpg
   *   /eyebrows/feather.jpg
   *   /eyebrows/ombre-powder.jpg
   *   /eyebrows/combination.jpg
   */
  imagePath: string;
  /**
   * آدرس تصویر برای مرورگر.
   * چرا مستقیم از public خوانده نمی‌شود؟ چون سرور production نکست فهرست public را
   * فقط یک بار در زمان بالا آمدن می‌خواند و تصویر تازه‌آپلودشده تا ری‌استارت ۴۰۴
   * می‌دهد؛ روت /api/site-image فایل را در هر درخواست از دیسک می‌خواند.
   */
  imageUrl: string;
  /**
   * نام فایل ذخیره‌شده روی دیسک (داخل public/eyebrows).
   */
  imageFileName: string;
  /**
   * تصویر نمونهٔ کارت.
   * اگر روزی خواستید عکس واقعی بگذارید، همین فیلد را به مسیر فایل بدهید
   * (مثلاً '/eyebrows/hairstroke.jpg')؛ در غیر این صورت تصویر SVG تولیدی
   * از src/brow-shapes.ts نمایش داده می‌شود.
   */
  sampleImage?: string;
}

/** پیشوند روت سرو کردن تصاویر آپلودی (پوشهٔ public را در production جایگزین می‌کند) */
export const SITE_IMAGE_ROUTE = '/api/site-image';

/** پوشه‌ای که تصاویر ابروها در آن ذخیره می‌شوند (داخل public) */
export const BROW_IMAGE_FOLDER = '/eyebrows';

/** پوشه‌ای که تصویر هیرو در آن ذخیره می‌شود (داخل public) */
export const HERO_IMAGE_FOLDER = '/hero';

/** نام پایهٔ فایل تصویر هیرو (پسوند بر اساس نوع فایل آپلودی انتخاب می‌شود) */
export const HERO_IMAGE_BASENAME = 'hero';

/** آدرس تصویر هیرو برای مرورگر — بدون پسوند، سرور خودش jpg/png/webp را پیدا می‌کند */
export const HERO_IMAGE_URL = `${SITE_IMAGE_ROUTE}${HERO_IMAGE_FOLDER}/${HERO_IMAGE_BASENAME}`;

export const EYEBROW_STYLES: EyebrowStyle[] = [
  {
    key: 'hairstroke',
    imagePath: `${BROW_IMAGE_FOLDER}/natural-hairstroke.jpg`,
    imageUrl: `${SITE_IMAGE_ROUTE}${BROW_IMAGE_FOLDER}/natural-hairstroke.jpg`,
    imageFileName: 'natural-hairstroke.jpg',
    labelEn: 'Natural Hairstroke',
    label: 'هایر استروک طبیعی',
    hint: 'ضربه‌های مو‌مانند و بسیار طبیعی',
  },
  {
    key: 'feather',
    imagePath: `${BROW_IMAGE_FOLDER}/feather.jpg`,
    imageUrl: `${SITE_IMAGE_ROUTE}${BROW_IMAGE_FOLDER}/feather.jpg`,
    imageFileName: 'feather.jpg',
    labelEn: 'Feather Brow',
    label: 'فدر براو',
    hint: 'ابتدای محو و پرمانند، دم نازک',
  },
  {
    key: 'ombre',
    imagePath: `${BROW_IMAGE_FOLDER}/ombre-powder.jpg`,
    imageUrl: `${SITE_IMAGE_ROUTE}${BROW_IMAGE_FOLDER}/ombre-powder.jpg`,
    imageFileName: 'ombre-powder.jpg',
    labelEn: 'Ombre Powder',
    label: 'اومبره پودری',
    hint: 'پودری و مخملی، بدون خط',
  },
  {
    key: 'combination',
    imagePath: `${BROW_IMAGE_FOLDER}/combination.jpg`,
    imageUrl: `${SITE_IMAGE_ROUTE}${BROW_IMAGE_FOLDER}/combination.jpg`,
    imageFileName: 'combination.jpg',
    labelEn: 'Combination',
    label: 'کامبینیشن',
    hint: 'ترکیب تار مو و سایهٔ پودری',
  },
];

export interface BrowColor {
  /** نام فارسی رنگ (در پرامپت، پیام واتساپ و tooltip) */
  name: string;
  /** کد رنگ */
  hex: string;
}

export const BROW_COLORS: BrowColor[] = [
  { name: 'قهوه‌ای طبیعی', hex: '#8B6914' },
  { name: 'قهوه‌ای تیره', hex: '#5C3D11' },
  { name: 'بلوند', hex: '#C4A265' },
  { name: 'خاکستری تیره', hex: '#4A4A4A' },
  { name: 'مشکی نرم', hex: '#2C2C2C' },
  { name: 'قهوه‌ای قرمز', hex: '#7B3F00' },
];

export const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // ۵ مگابایت — عکس چهرهٔ کاربر
/** حداکثر حجم تصویر ابروی پنل مدیریت (فقط PNG) */
export const MAX_BROW_IMAGE_BYTES = 5 * 1024 * 1024;
/** حداکثر حجم تصویر هیرو در پنل مدیریت */
export const MAX_HERO_IMAGE_BYTES = 10 * 1024 * 1024;
export const ACCEPTED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const;
export const ACCEPT_ATTRIBUTE = ACCEPTED_MIME_TYPES.join(',');

export const WHATSAPP_NUMBER = '989058674412';

/**
 * ⚠️ آدرس پیج اینستاگرام — این مقدار را با آدرس واقعی پیج خودتان عوض کنید.
 * (دکمهٔ اینستاگرام در هیروی صفحهٔ اصلی از همین مقدار ساخته می‌شود.)
 */
export const INSTAGRAM_URL = 'https://www.instagram.com/asal.rajabi';

/** متن روی هیروی صفحهٔ اصلی */
export const HERO_TITLE = 'عسل رجبی';
export const HERO_SUBTITLE = 'تو زیبایی؛ من فقط کشفش می‌کنم';

/** پیام دکمهٔ واتساپ روی هیرو */
export const HERO_WHATSAPP_MESSAGE =
  'سلام خانم رجبی، برای میکروبلیدینگ ابرو می‌خواهم مشاوره و نوبت بگیرم.';

export function buildHeroWhatsAppLink(): string {
  return `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(HERO_WHATSAPP_MESSAGE)}`;
}

/** تصویر نمونهٔ هر سبک (SVG تولیدی با رنگ طلایی-قهوه‌ای) */
export function styleSampleImage(style: EyebrowStyle): string {
  return style.sampleImage ?? browPreviewUri(style.key, '#C7A76A');
}

/** پیام آمادهٔ واتساپ: خدمت و مدل انتخابی کاربر */
export function buildWhatsAppMessage(serviceTitle: string, modelLabel: string): string {
  return `سلام خانم رجبی، برای ${serviceTitle} با مدل ${modelLabel} می‌خواهم مشاوره و نوبت بگیرم.`;
}

export function buildWhatsAppLink(serviceTitle: string, modelLabel: string): string {
  return `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(
    buildWhatsAppMessage(serviceTitle, modelLabel),
  )}`;
}

/**
 * قرارداد فنی هر تکنیک — مهم‌ترین جملهٔ تمایز مدل‌ها.
 * قانون: هر قرارداد باید (۱) تکنیک دقیق، (۲) ناحیهٔ مجاز، (۳) فرقش با
 * مدل‌های هم‌خانواده (NOT ...) و (۴) یک دم کوتاه حفاظتی داشته باشد.
 * نام مدل به‌تنهایی برای FLUX کافی نیست.
 */
export function styleDesignSpec(styleKey: string): string {
  switch (styleKey) {
    // ---- ابرو ----
    case 'hairstroke':
      return 'STYLE CONTRACT: Natural Hairstroke. Transfer ONLY fine individual hair-stroke technique from reference. Preserve the customer brow boundary, position, arch, tail, growth direction, gaps and asymmetry. Sparse soft front, medium-low natural density, tapered tail. NO powder fill, NO skin tint, NO shadow, NO halo.';
    case 'feather':
      return 'STYLE CONTRACT: Feather Brow. Transfer ONLY airy separated feather-stroke technique from reference. Preserve the customer brow boundary, position, arch, tail, growth direction, gaps and asymmetry. Soft light front, visible individual hair texture, natural irregularity, tapered tail. NO solid pigment area, NO skin tint, NO shadow, NO halo.';
    case 'ombre':
      return 'STYLE CONTRACT: Ombre Powder. Transfer ONLY translucent powder technique from reference. Apply it strictly inside the customer\'s existing brow region, lightest at front and gradually deeper through body/tail. Preserve customer brow position, boundary, arch, tail and asymmetry. NO pigment above/below brow, NO eyelid shadow, NO makeup halo, NO facial retouching.';
    case 'combination':
      return 'STYLE CONTRACT: Combination. Transfer ONLY the combination technique from reference: fine natural hairstrokes at the front plus soft translucent powder shading inside the customer\'s existing brow region. Preserve customer brow position, boundary, arch, tail, growth direction, gaps and asymmetry. NO pigment outside brow, NO under-brow shadow, NO eyelid makeup, NEVER blocky.';
    // ---- لب ----
    case 'natural_blush':
      return 'STYLE CONTRACT: Sheer Watercolor Blush. A translucent watercolor wash inside the vermilion only — native lip texture stays visible, no visible border line, dewy hydrated sheen. The LIGHTEST lip coverage: sheer glow, NOT a defined contour, NOT full color. Preserve customer lip shape, border, commissures, volume ratio and asymmetry. NO overlining, NO opaque lipstick, NO teeth tint, NO skin stain.';
    case 'nude_pink':
      return 'STYLE CONTRACT: Nude Pink Contour. Soft nude-pink blush with a gently DEFINED contour edge (seamless fading, not a hard line) inside the vermilion. More shape definition than a watercolor wash but still translucent daywear: elegant nude-pink melted into the native mucosa. Preserve customer lip shape, commissures, volume ratio and asymmetry. NO hard liner, NO neon or dark shades, NO overlining, NO teeth tint.';
    case 'full_color':
      return 'STYLE CONTRACT: Full Velvet Lip. Rich saturated velvet blush, full even coverage edge-to-edge with a soft velvety edge — the DENSEST lip style: luminous uniform pigment, yet real lip texture and creases stay visible. Preserve customer lip shape, border, commissures, volume ratio and asymmetry. NO smudged borders, NO asymmetric outline, NO outside stain, NO plastic gloss.';
    case 'dark_neutralization':
      return 'STYLE CONTRACT: Dark Lip Neutralization. A corrective warm peach-coral sheer layer that NEUTRALIZES dark and purple melanin patches into one even warm tone — corrective first, beautifying second. Completely even tone, dewy velvet finish, native texture visible. Preserve customer lip shape, border, commissures and asymmetry. NO purple or gray leftovers, NO opaque orange mask, NO patchiness, NO overlined border.';
    // ---- خط چشم ----
    case 'lash_line_enhancement':
      return 'STYLE CONTRACT: Lash Line Enhancement (invisible tightline). Ultra-fine pigment embedded BETWEEN the lash roots only — no visible line above the lashes, just deeper natural eye definition. The most subtle liner: an invisible-makeup look. Preserve eye shape, tilt, lid fold, lash direction and asymmetry; identical on BOTH eyes. NO visible wing, NO eyeshadow halo, NO blue or green bleed, NO wobbly line.';
    case 'classic_liner':
      return 'STYLE CONTRACT: Classic Eyeliner. A crisp clean VISIBLE line hugging the lash roots with a delicate tapered flick at the outer corner — clearly more defined than an invisible tightline: sharp smooth edge, opaque jet-black tapering into a sheer wing. Preserve eye shape, tilt, lid fold and asymmetry; identical on BOTH eyes. NO smudge, NO drooping tail, NO blocky thickness, NO jagged edges.';
    case 'smokey_shade':
      return 'STYLE CONTRACT: Smokey Stardust Liner. A crisp lash-base line PLUS a soft diffused powder gradient fading upward into the lid (a shaded wing, not a hard flick) — the ONLY liner with above-line shading. Pixelated micro-gradient, skin pores visible through it. Preserve eye shape, tilt, lid fold and asymmetry; identical on BOTH eyes. NO raccoon effect, NO under-eye bleed, NO muddy gray patch, NO harsh lines.';
    // ---- ریمو ----
    case 'removal':
      return 'STYLE CONTRACT: PMU Removal Fade. FADE the existing artificial pigment only — reveal the native skin and hair; add NOTHING. Old reddish, orangey, grayish or bluish casts neutralize into the surrounding skin tone. Realistic healed finish with visible pores. Preserve every native feature exactly. NO new pigment, NO bleached patches, NO scar gloss, NO color inversion.';
    default:
      return '';
  }
}

/** پیام انگلیسی ارسالی به مدل ویرایش تصویر — چندخدمتی (ابرو/لب/خط چشم/ریمو)
 *
 * ترتیب عمدی است و نباید جابه‌جا شود:
 *   ۱) قرارداد سبک (متمایزکنندهٔ مدل‌ها) — اول، چون مدل به ابتدای پرامپت بیشترین وزن را می‌دهد
 *   ۲) شواهد سبک (brief + STYLE_DNA + نسخه ARIA)
 *   ۳) یک بلوک حفاظتی فشرده (به‌جای ۵ تکرار «تغییر نده» که سیگنال سبک را خفه می‌کرد)
 */
export function buildEnglishPrompt(
  styleLabel: string,
  colorName: string,
  colorHex: string,
  styleLabelEn?: string,
  styleKey?: string,
  designBrief?: string,
  service: string = 'eyebrows',
): string {
  const styleText = styleLabelEn ? `${styleLabel} (${styleLabelEn})` : styleLabel;
  const spec = styleKey ? styleDesignSpec(styleKey) : '';
  const brief = designBrief ? `STYLE EVIDENCE: ${designBrief}` : '';

  if (service === 'lips') {
    return (
      `STYLE EDITING TASK — apply «${styleText}» onto IMAGE 0 (the customer photo). IMAGE 1 is the selected style reference ONLY. ` +
      `${spec} ${brief} ` +
      `SCOPE: edit ONLY the lip vermilion of IMAGE 0 within its natural border; no overlining, no paint on teeth, tongue, inner mouth, chin, nose or skin. IMAGE 1 is technique-only: never copy its face, lip shape, skin, lighting or background — transfer only tint behavior, density and finish. Pigment = translucent blush melting into the CUSTOMER'S native mucosal tone (never opaque brown, gray, purple or neon, never a fixed HEX). Cover the FULL vermilion of BOTH lips evenly, edge-to-edge, with matching commissures; never patchy or half-filled. No blur, smoothing, relighting or beauty filtering anywhere. FINAL: the SAME original photograph after lip blush, not a new face.`
    );
  }

  if (service === 'eyeliner') {
    return (
      `STYLE EDITING TASK — apply «${styleText}» onto IMAGE 0 (the customer photo). IMAGE 1 is the selected style reference ONLY. ` +
      `${spec} ${brief} ` +
      `SCOPE: edit ONLY the upper lash-line zone of IMAGE 0 (lash roots + up to 1mm above; an optional short flick within 3mm of the outer canthus following the natural tilt). Never touch the eyeball, iris, sclera, waterline, lower lid or brows. IMAGE 1 is technique-only: never copy its face, eye shape, skin or lighting — transfer only line behavior, density and finish. Carbon soft-black matched to the CUSTOMER'S undertone, matte (never blue, green or migrating, never a fixed HEX). Identical liner on BOTH eyes — same thickness, length and flick; no sclera tint, no under-eye bleed. No blur, smoothing, relighting or beauty filtering. FINAL: the SAME original photograph after lash-line treatment, not a new face.`
    );
  }

  if (service === 'removal') {
    return (
      `STYLE EDITING TASK — apply «${styleText}» onto the customer photo. There is NO reference image; infer everything from the customer photo: gradual fading of old artificial PMU pigment toward clean natural skin. ` +
      `${spec} ${brief} ` +
      `SCOPE: fade ONLY the existing artificial pigment traces (old brow, lip or liner tattoo); reveal the natural skin and native hair; add NO new pigment, strokes, blush or liner anywhere. Neutralize old hue casts (reddish, orangey, grayish, bluish) into the surrounding skin tone; no bleached patches, no scar gloss, no inversion. No blur, smoothing, relighting or beauty filtering anywhere; all native anatomy stays pixel-identical. FINAL: the SAME original photograph after healed removal session(s), not a new face.`
    );
  }

  return (
    `STYLE EDITING TASK — apply «${styleText}» onto IMAGE 0 (the customer photo). IMAGE 1 is the selected style reference ONLY. ` +
    `${spec} ${brief} ` +
    `SCOPE: edit ONLY the two existing eyebrow regions of IMAGE 0; never move, reposition or enlarge them. IMAGE 1 is technique-only: never copy its face, skin, brow placement, lighting, color cast or background — transfer only stroke and shading technique, density and finish. Pigment from the CUSTOMER'S own brow and hair appearance plus local undertone (never a fixed HEX, never pure black, never an arbitrary cast). No pigment, shadow, blur, smoothing, relighting or makeup outside the brows; no white-balance or exposure shift. Keep native position, arch, tail, growth direction, gaps and asymmetry. FINAL: the SAME original photograph after professional brow treatment, not a new face.`
  );
}
