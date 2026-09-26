/**
 * src/providers/types.ts — قرارداد مشترک پروایدرهای هوش مصنوعی
 */

import type { ParsedImage } from './http';

export interface ProviderInput {
  /** پرامپت انگلیسی ویرایش تصویر */
  prompt: string;
  /** عکس چهرهٔ کاربر (data URI تجزیه‌شده) */
  image: ParsedImage;
  /** تصویر مرجع سبک انتخاب‌شده؛ باید توسط کلاینت به حداکثر 512px کاهش یافته باشد. */
  referenceImage?: ParsedImage;
  /** مهلت اختیاری این درخواست (میلی‌ثانیه) — برای تست سلامت کلیدها */
  timeoutMs?: number;
}

export interface Provider {
  /** شناسهٔ فنی */
  id: string;
  /** نام نمایشی برای رابط کاربری */
  label: string;
  /** نام متغیر محیطی کلید API */
  envKey: string;
  /** Optional custom configuration check for providers with multiple credentials. */
  isConfigured?: () => boolean;
  /**
   * تولید تصویر و برگرداندن آدرس/بایت آن.
   * در صورت خطا باید throw کند تا زنجیرهٔ جایگزین به پروایدر بعدی برود.
   */
  generate(input: ProviderInput): Promise<string>;
}

export interface AttemptLog {
  provider: string;
  label: string;
  ok: boolean;
  ms: number;
  error?: string;
}
