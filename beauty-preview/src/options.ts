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

/** پیام انگلیسی ارسالی به مدل ویرایش تصویر */
export function buildEnglishPrompt(
  styleLabel: string,
  colorName: string,
  colorHex: string,
  styleLabelEn?: string,
): string {
  const styleText = styleLabelEn ? `${styleLabel} (${styleLabelEn})` : styleLabel;
  return (
    `Apply professional microblading eyebrows in the style of ${styleText} ` +
    `with color ${colorHex} (${colorName}) to this face photo. ` +
    `Keep everything else exactly the same. ` +
    `Realistic, natural, high quality beauty result.`
  );
}
