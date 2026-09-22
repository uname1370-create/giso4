/**
 * src/admin-client.ts
 * ---------------------------------------------------------------------------
 * ابزارهای سمت مرورگر برای پنل مدیریت (قابل استفاده در Client Components):
 *   - نام کلید sessionStorage که توکن ورود در آن نگه داشته می‌شود
 *   - خواندن/حذف توکن
 *   - ساخت هدر Authorization و fetch با توکن (و تشخیص ۴۰۱)
 *   - قالب‌بندی اعداد و تاریخ/ساعت فارسی
 * ---------------------------------------------------------------------------
 */

export const ADMIN_TOKEN_KEY = 'beauty_admin_token';

export function getAdminToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.sessionStorage.getItem(ADMIN_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function clearAdminToken(): void {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  } catch {
    /* نادیده */
  }
}

/** خطای «توکن نامعتبر/منقضی» تا UI بتواند کاربر را به صفحهٔ ورود بفرستد */
export class AdminAuthError extends Error {
  constructor() {
    super('نشست شما منقضی شده است. لطفاً دوباره وارد شوید.');
    this.name = 'AdminAuthError';
  }
}

/** fetch با توکن مدیر؛ در صورت ۴۰۱ خطای AdminAuthError پرتاب می‌شود */
export async function adminFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = getAdminToken();
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(input, { ...init, headers, cache: 'no-store' });
  if (res.status === 401) {
    clearAdminToken();
    throw new AdminAuthError();
  }
  return res;
}

/* -------------------------------------------------------------------------- */
/* قالب‌بندی فارسی                                                            */
/* -------------------------------------------------------------------------- */

/** عدد با ارقام فارسی */
export function faNumber(value: number): string {
  try {
    return value.toLocaleString('fa-IR');
  } catch {
    return String(value);
  }
}

/** تاریخ و ساعت فارسی (تقویم هجری شمسی) */
export function faDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  try {
    return new Intl.DateTimeFormat('fa-IR', {
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(date);
  } catch {
    return date.toString();
  }
}

/** تاریخ و ساعت کوتاه برای فهرست رویدادها */
export function faTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  try {
    return new Intl.DateTimeFormat('fa-IR', {
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  } catch {
    return date.toString();
  }
}
