'use client';

/**
 * app/admin/page.tsx — صفحهٔ ورود پنل مدیریت
 * ---------------------------------------------------------------------------
 * - کارت وسط‌چین با حاشیهٔ طلایی
 * - یک ورودی رمز عبور (type=password، RTL)
 * - درخواست سادهٔ POST به /api/admin/login (بدون کتابخانهٔ احراز هویت)
 * - در صورت موفقیت: توکن در sessionStorage ذخیره و به /admin/dashboard می‌رود
 * ---------------------------------------------------------------------------
 */

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import { ADMIN_TOKEN_KEY } from '@/admin-client';

export default function AdminLoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  /** اگر از قبل وارد شده است، مستقیم به داشبورد برود */
  useEffect(() => {
    if (window.sessionStorage.getItem(ADMIN_TOKEN_KEY)) {
      router.replace('/admin/dashboard');
    }
  }, [router]);

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      if (loading) return;

      if (!password) {
        setError('رمز عبور را وارد کنید.');
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const res = await fetch('/api/admin/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password }),
        });
        const data = (await res.json()) as { ok?: boolean; token?: string; error?: string };

        if (!res.ok || !data.ok || !data.token) {
          setError(data?.error || 'رمز عبور اشتباه است');
          return;
        }

        window.sessionStorage.setItem(ADMIN_TOKEN_KEY, data.token);
        router.replace('/admin/dashboard');
      } catch {
        setError('ارتباط با سرور برقرار نشد. دوباره تلاش کنید.');
      } finally {
        setLoading(false);
      }
    },
    [loading, password, router],
  );

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm animate-fadeUp">
        {/* لوگو */}
        <div className="mb-8 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-gold/50 bg-gold/10 text-2xl font-black text-gold">
            ع
          </div>
          <h1 className="mt-5 text-lg font-extrabold tracking-tight">
            عسل رجبی <span className="text-gold">|</span> پنل مدیریت
          </h1>
          <p className="mt-2 text-xs text-mist">برای ورود، رمز عبور را وارد کنید</p>
        </div>

        {/* کارت ورود */}
        <form
          onSubmit={handleSubmit}
          className="rounded-3xl border-2 border-gold/40 bg-card p-7 shadow-[0_30px_80px_-50px_rgba(212,175,55,0.6)]"
        >
          <label htmlFor="admin-password" className="mb-2 block text-xs font-bold text-mist">
            رمز عبور
          </label>
          <input
            id="admin-password"
            type="password"
            dir="rtl"
            autoComplete="current-password"
            autoFocus
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              setError(null);
            }}
            placeholder="••••"
            className="w-full rounded-xl border border-white/10 bg-[#0F0F0F] px-4 py-3 text-center text-lg tracking-[0.3em] text-white outline-none transition focus:border-gold/60 focus:ring-2 focus:ring-gold/25"
          />

          {error ? (
            <p
              role="alert"
              className="mt-4 rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-center text-xs font-bold text-red-200"
            >
              {error}
            </p>
          ) : null}

          <button type="submit" disabled={loading} className="btn-gold mt-5 w-full !py-3.5">
            {loading ? (
              <>
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-ink/30 border-t-ink" />
                در حال ورود…
              </>
            ) : (
              'ورود'
            )}
          </button>
        </form>

        <p className="mt-6 text-center text-[11px] leading-6 text-mist/60">
          رمز عبور در متغیر محیطی <code className="text-gold/80">ADMIN_PASSWORD</code> تنظیم می‌شود.
        </p>
      </div>
    </main>
  );
}
