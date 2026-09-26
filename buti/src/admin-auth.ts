/**
 * src/admin-auth.ts
 * ---------------------------------------------------------------------------
 * احراز هویت سادهٔ پنل مدیریت — بدون هیچ کتابخانهٔ بیرونی:
 *
 *   رمز عبور از متغیر محیطی ADMIN_PASSWORD خوانده می‌شود
 *   (اگر تنظیم نشده باشد، پیش‌فرض «1234»).
 *
 *   پس از ورود موفق، یک توکن امضاشده با انقضا ساخته می‌شود:
 *       <expiresAt>.<sha256("beauty-admin:<password>:<expiresAt>")>
 *
 *   توکن در sessionStorage مرورگر ذخیره می‌شود و در هر درخواست به‌شکل
 *   `Authorization: Bearer <token>` فرستاده می‌شود. اعتبار توکن بدون نگه‌داشتن
 *   وضعیت در سرور (stateless) و تنها با محاسبهٔ مجدد امضا بررسی می‌شود.
 *
 *   برای ابزارهای ساده (curl، اسکریپت) هدر `x-admin-password: <ADMIN_PASSWORD>`
 *   هم پذیرفته می‌شود — همان روش سادهٔ پیشنهادی در سند طراحی.
 *
 * ⚠️ این یک لایهٔ محافظتی ساده برای پنل داخلی است، نه سیستم احراز هویت کامل.
 *    رمز پیش‌فرض را با ADMIN_PASSWORD در .env عوض کنید.
 * ---------------------------------------------------------------------------
 */

import { createHash, timingSafeEqual } from 'node:crypto';
import { NextResponse } from 'next/server';

/** مدت اعتبار هر نشست (ساعت) */
const SESSION_HOURS = 12;

/** رمز عبور پنل (پیش‌فرض: 1234) */
export function adminPassword(): string {
  return (process.env.ADMIN_PASSWORD ?? '').trim() || '1234';
}

function digest(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

/** مقایسهٔ امن دو رشته (مقاوم به حملهٔ زمان‌سنجی) */
export function safeCompare(a: string, b: string): boolean {
  const bufferA = Buffer.from(digest(a), 'hex');
  const bufferB = Buffer.from(digest(b), 'hex');
  return timingSafeEqual(bufferA, bufferB);
}

function signature(expiresAt: number): string {
  return digest(`beauty-admin:${adminPassword()}:${expiresAt}`);
}

/** ساخت توکن نشست پس از ورود موفق */
export function createToken(): { token: string; expiresAt: number } {
  const expiresAt = Date.now() + SESSION_HOURS * 60 * 60 * 1000;
  return { token: `${expiresAt}.${signature(expiresAt)}`, expiresAt };
}

/** بررسی اعتبار توکن (امضا + انقضا) */
export function verifyToken(token: string | null | undefined): boolean {
  if (!token || typeof token !== 'string') return false;
  const [rawExpires, rawSignature] = token.split('.');
  if (!rawExpires || !rawSignature) return false;

  const expiresAt = Number(rawExpires);
  if (!Number.isFinite(expiresAt) || expiresAt < Date.now()) return false;

  return safeCompare(rawSignature, signature(expiresAt));
}

/** خواندن توکن از هدر Authorization */
export function bearerToken(request: Request): string | null {
  const header = request.headers.get('authorization') ?? '';
  const match = /^Bearer\s+(.+)$/i.exec(header.trim());
  return match ? match[1].trim() : null;
}

/**
 * بررسی رمز عبور در هدر `x-admin-password` (روش سادهٔ جایگزین توکن).
 * برای درخواست‌های curl/اسکریپتی کاربرد دارد.
 */
export function hasValidPasswordHeader(request: Request): boolean {
  const header = request.headers.get('x-admin-password');
  if (!header) return false;
  return safeCompare(header, adminPassword());
}

/** آیا این درخواست مدیرِ وارد‌شده است؟ (توکن Bearer یا هدر رمز عبور) */
export function isAuthorized(request: Request): boolean {
  if (verifyToken(bearerToken(request))) return true;
  return hasValidPasswordHeader(request);
}

/** پاسخ استاندارد ۴۰۱ */
export function unauthorizedResponse(): NextResponse {
  return NextResponse.json(
    { ok: false, error: 'دسترسی غیرمجاز — لطفاً دوباره وارد شوید.' },
    { status: 401 },
  );
}
