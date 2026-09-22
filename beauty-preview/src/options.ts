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
   * تصویر نمونهٔ کارت.
   * اگر روزی خواستید عکس واقعی بگذارید، همین فیلد را به مسیر فایل بدهید
   * (مثلاً '/eyebrows/hairstroke.jpg')؛ در غیر این صورت تصویر SVG تولیدی
   * از src/brow-shapes.ts نمایش داده می‌شود.
   */
  sampleImage?: string;
}

export const EYEBROW_STYLES: EyebrowStyle[] = [
  {
    key: 'hairstroke',
    labelEn: 'Natural Hairstroke',
    label: 'هایر استروک طبیعی',
    hint: 'ضربه‌های مو‌مانند و بسیار طبیعی',
  },
  {
    key: 'feather',
    labelEn: 'Feather Brow',
    label: 'فدر براو',
    hint: 'ابتدای محو و پرمانند، دم نازک',
  },
  {
    key: 'ombre',
    labelEn: 'Ombre Powder',
    label: 'اومبره پودری',
    hint: 'پودری و مخملی، بدون خط',
  },
  {
    key: 'combination',
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

export const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // ۵ مگابایت
export const ACCEPTED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const;
export const ACCEPT_ATTRIBUTE = ACCEPTED_MIME_TYPES.join(',');

export const WHATSAPP_NUMBER = '989058674412';

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
