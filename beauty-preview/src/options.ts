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
   *   /eyebrows/natural-hairstroke.png
   *   /eyebrows/feather.png
   *   /eyebrows/ombre-powder.png
   *   /eyebrows/combination.png
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
    imagePath: `${BROW_IMAGE_FOLDER}/natural-hairstroke.png`,
    imageUrl: `${SITE_IMAGE_ROUTE}${BROW_IMAGE_FOLDER}/natural-hairstroke.png`,
    imageFileName: 'natural-hairstroke.png',
    labelEn: 'Natural Hairstroke',
    label: 'هایر استروک طبیعی',
    hint: 'ضربه‌های مو‌مانند و بسیار طبیعی',
  },
  {
    key: 'feather',
    imagePath: `${BROW_IMAGE_FOLDER}/feather.png`,
    imageUrl: `${SITE_IMAGE_ROUTE}${BROW_IMAGE_FOLDER}/feather.png`,
    imageFileName: 'feather.png',
    labelEn: 'Feather Brow',
    label: 'فدر براو',
    hint: 'ابتدای محو و پرمانند، دم نازک',
  },
  {
    key: 'ombre',
    imagePath: `${BROW_IMAGE_FOLDER}/ombre-powder.png`,
    imageUrl: `${SITE_IMAGE_ROUTE}${BROW_IMAGE_FOLDER}/ombre-powder.png`,
    imageFileName: 'ombre-powder.png',
    labelEn: 'Ombre Powder',
    label: 'اومبره پودری',
    hint: 'پودری و مخملی، بدون خط',
  },
  {
    key: 'combination',
    imagePath: `${BROW_IMAGE_FOLDER}/combination.png`,
    imageUrl: `${SITE_IMAGE_ROUTE}${BROW_IMAGE_FOLDER}/combination.png`,
    imageFileName: 'combination.png',
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

/** پیام آمادهٔ واتساپ: مدل و رنگ انتخابی کاربر */
export function buildWhatsAppMessage(styleLabel: string, colorName: string): string {
  return `سلام خانم رجبی، مدل ${styleLabel} با رنگ ${colorName} برای میکروبلیدینگ انتخاب کردم و می‌خواهم نوبت بگیرم.`;
}

export function buildWhatsAppLink(styleLabel: string, colorName: string): string {
  return `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(
    buildWhatsAppMessage(styleLabel, colorName),
  )}`;
}

/** مشخصات فنی هر تکنیک؛ نام مدل به‌تنهایی برای FLUX کافی نیست. */
export function styleDesignSpec(styleKey: BrowStyleKey): string {
  switch (styleKey) {
    case 'hairstroke':
      return 'Natural Hairstroke: ultra-fine individual hair strokes only, follow the customer’s existing brow growth direction and natural brow boundary, sparse soft front, medium-low natural density, soft arch, tapered tail, preserve natural gaps and asymmetry, NO powder fill, NO skin tint, NO shadow, NO halo.';
    case 'feather':
      return 'Feather Brow: airy separated feather strokes only, follow the customer’s existing growth direction, soft light front, visible individual hair texture, natural irregularity, softly tapered tail, preserve natural gaps, NO solid pigment area, NO skin tint, NO shadow, NO halo.';
    case 'ombre':
      return 'Ombre Powder: soft translucent powder shading ONLY INSIDE THE CUSTOMER’S EXISTING EYEBROW REGION, lightest at the front and gradually deeper through the brow body and tail, velvety diffused brow texture, soft brow edges, NO pigment on skin below or above the brow, NO eyelid shadow, NO makeup halo, NO facial retouching.';
    case 'combination':
      return 'Combination: fine natural hairstrokes at the front plus soft translucent powder shading ONLY INSIDE THE EXISTING EYEBROW REGION, blended transition, medium natural density, preserve natural gaps and asymmetry, NO pigment outside the brow, NO under-brow shadow, NO eyelid makeup, NEVER blocky.';
  }
}

/** پیام انگلیسی ارسالی به مدل ویرایش تصویر */
export function buildEnglishPrompt(
  styleLabel: string,
  colorName: string,
  colorHex: string,
  styleLabelEn?: string,
  styleKey?: BrowStyleKey,
  designBrief?: string,
): string {
  const styleText = styleLabelEn ? `${styleLabel} (${styleLabelEn})` : styleLabel;
  const spec = styleKey ? styleDesignSpec(styleKey) : '';
  const brief = designBrief ? ` Customer-specific Design Brief: ${designBrief}` : '';
  return (
    `IMAGE 0 IS THE ORIGINAL CUSTOMER PHOTO. IMAGE 1 IS ONLY THE SELECTED EYEBROW DESIGN REFERENCE. ` +
    `Edit ONLY the existing eyebrow regions of image 0. Transfer the eyebrow technique, stroke pattern, density, arch character and finish from image 1 onto the customer's existing brows. ` +
    `Do not copy any face, skin, eyes, lighting or identity from image 1. ` +
    `Selected technique: ${styleText}. ${spec} ${brief} ` +
    `Pigment must be inferred from the customer's visible natural eyebrow and hair tone and harmonized with skin undertone. Use a realistic pigment family, temperature and depth; never use a fixed HEX color, pure black, or an arbitrary red/orange/brown tint. ` +
    `Apply pigment only within the existing natural eyebrow hair region. Do not tint surrounding skin. ` +
    `The selected reference image defines technique and finish only; never copy its brow placement, face, skin, color cast, lighting or anatomy. ` +
    `Preserve the person's identity and original facial geometry exactly. ` +
    `Do not change eyes, eyelids, eyelashes, nose, lips, cheeks, forehead, skin texture, skin tone, hair, ears, face shape, lighting, camera angle, background, clothing, or image composition. ` +
    `Do not add makeup outside the eyebrow regions. No under-brow shadow, no brown/gray halo, no pigment on eyelids or forehead, no beauty filter, no skin smoothing. Do not reshape the face. Do not regenerate the portrait. ` +
    `Keep both brows anchored to the customer's original brow position, bone structure, growth direction and natural asymmetry. Change only the eyebrow design. ` +
    `The result must look like the same real photograph after professional microblading, with only the eyebrow technique changed.`
  );
}
