'use client';

/**
 * app/admin/dashboard/page.tsx — داشبورد پنل مدیریت
 * ---------------------------------------------------------------------------
 * چیدمان: سایدبار سمت راست (RTL) + ناحیهٔ محتوا در سمت چپ
 * سه تب:
 *   ۱) 📊 آمار بازدید  → کارت‌های آماری + ۱۰ رویداد آخر
 *   ۲) 🖼️ تصاویر ابرو  → آپلود/حذف تصویر برای هر ۴ مدل ابرو
 *   ۳) 🌟 تصویر هیرو   → آپلود/حذف تصویر هیرو صفحهٔ اصلی
 *
 * احراز هویت: توکن در sessionStorage؛ اگر نبود یا منقضی شد → /admin
 * ---------------------------------------------------------------------------
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  ADMIN_TOKEN_KEY,
  AdminAuthError,
  adminFetch,
  clearAdminToken,
  faNumber,
  faTime,
  getAdminToken,
} from '@/admin-client';
import {
  EYEBROW_STYLES,
  HERO_IMAGE_URL,
  HERO_TITLE,
  MAX_BROW_IMAGE_BYTES,
  MAX_HERO_IMAGE_BYTES,
} from '@/options';

/* -------------------------------------------------------------------------- */
/* انواع                                                                      */
/* -------------------------------------------------------------------------- */

interface StatEvent {
  type: 'visit' | 'preview';
  time: string;
  style?: string;
}

interface StatsResponse {
  ok: boolean;
  visits: number;
  previews: number;
  todayVisits: number;
  todayPreviews: number;
  history: StatEvent[];
  statsPath?: string;
  error?: string;
}

interface UploadResponse {
  ok: boolean;
  url?: string;
  publicPath?: string;
  fileName?: string;
  bytes?: number;
  removed?: boolean;
  error?: string;
}

type TabKey = 'stats' | 'brows' | 'hero';
type Banner = { kind: 'ok' | 'error'; text: string } | null;

const TABS: { key: TabKey; icon: string; label: string }[] = [
  { key: 'stats', icon: '📊', label: 'آمار بازدید' },
  { key: 'brows', icon: '🖼️', label: 'تصاویر ابرو' },
  { key: 'hero', icon: '🌟', label: 'تصویر هیرو' },
];

/** تصویر ابرو فقط PNG است */
const BROW_ACCEPT = 'image/png';
/** تصویر هیرو JPG/PNG/WEBP */
const HERO_ACCEPT = 'image/jpeg,image/png,image/webp';

/** نمایش حجم فایل به فارسی */
function faSize(bytes: number): string {
  return `${faNumber(Math.round(bytes / (1024 * 1024)))} مگابایت`;
}

/** نام فارسی هر مدل ابرو از روی کلید آن */
function styleLabel(key?: string): string {
  if (!key) return '';
  return EYEBROW_STYLES.find((style) => style.key === key)?.label ?? key;
}

/* -------------------------------------------------------------------------- */
/* صفحه                                                                       */
/* -------------------------------------------------------------------------- */

export default function AdminDashboardPage() {
  const router = useRouter();

  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<TabKey>('stats');
  const [banner, setBanner] = useState<Banner>(null);

  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  /**
   * شمارهٔ نسخه — بعد از هر آپلود/حذف یکی زیاد می‌شود تا مرورگر تصویر تازه را
   * دوباره بخواند (نام فایل‌ها ثابت است، پس بدون این کار ممکن است کش شود).
   */
  const [version, setVersion] = useState(0);
  /** مدل‌هایی که تصویر اختصاصی ندارند (آپلود نشده یا حذف شده است) */
  const [browActive, setBrowActive] = useState<Record<string, boolean>>({});
  const [heroActive, setHeroActive] = useState(false);
  const [uploadingStyle, setUploadingStyle] = useState<string | null>(null);
  const [heroUploading, setHeroUploading] = useState(false);

  const browInputs = useRef<Record<string, HTMLInputElement | null>>({});
  const heroInput = useRef<HTMLInputElement | null>(null);

  /* --------------------------- نگهبان ورود --------------------------- */
  useEffect(() => {
    if (!getAdminToken()) {
      router.replace('/admin');
      return;
    }
    setReady(true);
  }, [router]);

  /** خروج از حساب */
  const handleLogout = useCallback(() => {
    clearAdminToken();
    router.replace('/admin');
  }, [router]);

  /** اگر نشست منقضی شد، به صفحهٔ ورود برگرد */
  const handleAuthError = useCallback(
    (error: unknown): boolean => {
      if (error instanceof AdminAuthError) {
        setBanner({ kind: 'error', text: error.message });
        setTimeout(() => router.replace('/admin'), 1200);
        return true;
      }
      return false;
    },
    [router],
  );

  /* ------------------------------ آمار ------------------------------ */
  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const res = await adminFetch('/api/admin/stats?limit=10');
      const data = (await res.json()) as StatsResponse;
      if (!res.ok || !data.ok) {
        setBanner({ kind: 'error', text: data.error || 'دریافت آمار ناموفق بود.' });
        return;
      }
      setStats(data);
    } catch (error) {
      if (handleAuthError(error)) return;
      setBanner({ kind: 'error', text: 'ارتباط با سرور برقرار نشد.' });
    } finally {
      setStatsLoading(false);
    }
  }, [handleAuthError]);

  useEffect(() => {
    if (!ready) return;
    void loadStats();
  }, [ready, loadStats]);

  /* --------------------------- آپلود ابرو --------------------------- */
  const handleBrowUpload = useCallback(
    async (styleKey: string, file: File | undefined | null) => {
      if (!file) return;
      setUploadingStyle(styleKey);
      setBanner(null);
      try {
        const form = new FormData();
        form.append('styleName', styleKey);
        form.append('file', file);

        const res = await adminFetch('/api/admin/upload-brow', { method: 'POST', body: form });
        const data = (await res.json()) as UploadResponse;

        if (!res.ok || !data.ok) {
          setBanner({ kind: 'error', text: data.error || 'آپلود تصویر ناموفق بود.' });
          return;
        }
        setBrowActive((prev) => ({ ...prev, [styleKey]: true }));
        setVersion((value) => value + 1);
        setBanner({ kind: 'ok', text: 'تصویر با موفقیت ذخیره شد ✓' });
      } catch (error) {
        if (handleAuthError(error)) return;
        setBanner({ kind: 'error', text: 'ارتباط با سرور برقرار نشد.' });
      } finally {
        setUploadingStyle(null);
        const input = browInputs.current[styleKey];
        if (input) input.value = '';
      }
    },
    [handleAuthError],
  );

  const handleBrowReset = useCallback(
    async (styleKey: string) => {
      setUploadingStyle(styleKey);
      setBanner(null);
      try {
        const res = await adminFetch(
          `/api/admin/upload-brow?style=${encodeURIComponent(styleKey)}`,
          { method: 'DELETE' },
        );
        const data = (await res.json()) as UploadResponse;
        if (!res.ok || !data.ok) {
          setBanner({ kind: 'error', text: data.error || 'حذف تصویر ناموفق بود.' });
          return;
        }
        setBrowActive((prev) => ({ ...prev, [styleKey]: false }));
        setVersion((value) => value + 1);
        setBanner({ kind: 'ok', text: 'تصویر حذف شد؛ تصویر SVG خودکار برگشت.' });
      } catch (error) {
        if (handleAuthError(error)) return;
        setBanner({ kind: 'error', text: 'ارتباط با سرور برقرار نشد.' });
      } finally {
        setUploadingStyle(null);
      }
    },
    [handleAuthError],
  );

  /* ---------------------------- آپلود هیرو ---------------------------- */
  const handleHeroUpload = useCallback(
    async (file: File | undefined | null) => {
      if (!file) return;
      setHeroUploading(true);
      setBanner(null);
      try {
        const form = new FormData();
        form.append('file', file);

        const res = await adminFetch('/api/admin/upload-hero', { method: 'POST', body: form });
        const data = (await res.json()) as UploadResponse;

        if (!res.ok || !data.ok) {
          setBanner({ kind: 'error', text: data.error || 'آپلود تصویر هیرو ناموفق بود.' });
          return;
        }
        setHeroActive(true);
        setVersion((value) => value + 1);
        setBanner({ kind: 'ok', text: 'تصویر هیرو با موفقیت ذخیره شد ✓' });
      } catch (error) {
        if (handleAuthError(error)) return;
        setBanner({ kind: 'error', text: 'ارتباط با سرور برقرار نشد.' });
      } finally {
        setHeroUploading(false);
        if (heroInput.current) heroInput.current.value = '';
      }
    },
    [handleAuthError],
  );

  const handleHeroReset = useCallback(async () => {
    setHeroUploading(true);
    setBanner(null);
    try {
      const res = await adminFetch('/api/admin/upload-hero', { method: 'DELETE' });
      const data = (await res.json()) as UploadResponse;
      if (!res.ok || !data.ok) {
        setBanner({ kind: 'error', text: data.error || 'حذف تصویر ناموفق بود.' });
        return;
      }
      setHeroActive(false);
      setVersion((value) => value + 1);
      setBanner({ kind: 'ok', text: 'تصویر هیرو حذف شد؛ پس‌زمینهٔ گرادیانی برگشت.' });
    } catch (error) {
      if (handleAuthError(error)) return;
      setBanner({ kind: 'error', text: 'ارتباط با سرور برقرار نشد.' });
    } finally {
      setHeroUploading(false);
    }
  }, [handleAuthError]);

  if (!ready) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-gold/30 border-t-gold" />
      </main>
    );
  }

  /* ------------------------------ نمایش ------------------------------ */
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      {/* ----------------------------- سایدبار ----------------------------- */}
      <aside className="flex w-full shrink-0 flex-col border-e border-white/[0.06] bg-[#111111] p-5 md:min-h-screen md:w-64">
        <div className="mb-6">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-gold/50 bg-gold/10 text-lg font-black text-gold">
              ع
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-extrabold">عسل رجبی</p>
              <p className="text-[11px] text-gold/80">پنل مدیریت</p>
            </div>
          </div>
          <div className="mt-5 h-px w-full bg-gradient-to-l from-transparent via-gold/50 to-transparent" />
        </div>

        <nav className="flex flex-row gap-2 md:flex-col">
          {TABS.map((item) => {
            const active = tab === item.key;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setTab(item.key)}
                aria-current={active ? 'page' : undefined}
                className={`flex flex-1 items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-xs font-bold transition md:justify-start md:px-4 md:py-3 md:text-sm ${
                  active
                    ? 'border-gold/50 bg-gold/10 text-gold'
                    : 'border-transparent text-mist hover:border-white/10 hover:bg-white/[0.03] hover:text-white'
                }`}
              >
                <span aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="mt-5 md:mt-auto">
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 px-4 py-3 text-xs font-bold text-mist transition hover:border-red-400/40 hover:bg-red-500/10 hover:text-red-200"
          >
            <span aria-hidden="true">↩</span>
            خروج از حساب
          </button>
        </div>
      </aside>

      {/* ------------------------------ محتوا ------------------------------ */}
      <main className="flex-1 p-5 md:p-8">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-extrabold sm:text-xl">
              {TABS.find((item) => item.key === tab)?.label}
            </h1>
            <p className="mt-1 text-[11px] text-mist">
              سالن زیبایی عسل رجبی — مدیریت محتوای صفحهٔ میکروبلیدینگ
            </p>
          </div>

          <div className="flex items-center gap-2">
            {tab === 'stats' ? (
              <button
                type="button"
                onClick={() => void loadStats()}
                disabled={statsLoading}
                className="btn-outline !px-4 !py-2 text-xs disabled:opacity-50"
              >
                {statsLoading ? 'در حال بروزرسانی…' : 'بروزرسانی آمار'}
              </button>
            ) : null}
            <a href="/" target="_blank" rel="noreferrer" className="btn-outline !px-4 !py-2 text-xs">
              مشاهدهٔ صفحهٔ اصلی ↗
            </a>
          </div>
        </header>

        {banner ? (
          <p
            role="status"
            className={`mb-5 rounded-2xl border px-4 py-3 text-xs font-bold ${
              banner.kind === 'ok'
                ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-200'
                : 'border-red-400/30 bg-red-500/10 text-red-200'
            }`}
          >
            {banner.text}
          </p>
        ) : null}

        {/* ============================ تب ۱: آمار ============================ */}
        {tab === 'stats' ? (
          <section className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard
                title="بازدید امروز"
                value={stats ? stats.todayVisits : null}
                icon="📅"
                hint={
                  stats && stats.todayPreviews > 0
                    ? `${faNumber(stats.todayPreviews)} پیش‌نمایش امروز`
                    : 'بازدیدکنندگان امروز'
                }
              />
              <StatCard
                title="پیش‌نمایش‌های ساخته‌شده"
                value={stats ? stats.previews : null}
                icon="✨"
                hint="مجموع کل"
              />
              <StatCard
                title="بازدید کل"
                value={stats ? stats.visits : null}
                icon="👁️"
                hint="مجموع کل"
              />
            </div>

            <div className="card !p-0">
              <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
                <h2 className="text-sm font-extrabold">آخرین رویدادها</h2>
                <span className="text-[11px] text-mist">۱۰ رویداد آخر</span>
              </div>

              {statsLoading && !stats ? (
                <p className="px-6 py-8 text-center text-xs text-mist">در حال دریافت…</p>
              ) : stats && stats.history.length > 0 ? (
                <ul className="divide-y divide-white/[0.05]">
                  {stats.history.map((event, index) => (
                    <li
                      key={`${event.time}-${index}`}
                      className="flex flex-wrap items-center gap-3 px-6 py-3.5"
                    >
                      <span
                        className={`rounded-full border px-3 py-1 text-[11px] font-bold ${
                          event.type === 'preview'
                            ? 'border-gold/40 bg-gold/10 text-gold'
                            : 'border-white/10 bg-white/[0.03] text-mist'
                        }`}
                      >
                        {event.type === 'preview' ? 'پیش‌نمایش' : 'بازدید'}
                      </span>

                      {event.type === 'preview' && event.style ? (
                        <span className="text-[11px] text-mist">{styleLabel(event.style)}</span>
                      ) : null}

                      <span className="ms-auto font-mono text-[11px] text-mist/80">
                        {faTime(event.time)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-6 py-8 text-center text-xs text-mist">
                  هنوز رویدادی ثبت نشده است. با بازدید صفحهٔ اصلی، آمار اینجا نمایش داده می‌شود.
                </p>
              )}
            </div>
          </section>
        ) : null}

        {/* ======================== تب ۲: تصاویر ابرو ======================== */}
        {tab === 'brows' ? (
          <section className="space-y-4">
            <p className="rounded-2xl border border-white/[0.08] bg-card px-5 py-4 text-[11px] leading-6 text-mist">
              برای هر مدل ابرو یک تصویر نمونهٔ اختصاصی آپلود کنید — فقط PNG، حداکثر{' '}
              {faSize(MAX_BROW_IMAGE_BYTES)}. تصویر با نام ثابت ذخیره می‌شود و بلافاصله روی صفحهٔ
              اصلی جای تصویر SVG خودکار می‌نشیند. تا وقتی تصویری آپلود نشده باشد، همان SVG نمایش
              داده می‌شود.
            </p>

            {EYEBROW_STYLES.map((style) => {
              // تصویر هر مدل یک آدرس ثابت دارد؛ اگر آپلود نشده باشد بارگذاری‌اش خطا می‌دهد
              const imageSrc = `${style.imageUrl}?v=${version}`;
              const uploaded = browActive[style.key] === true;
              const busy = uploadingStyle === style.key;
              return (
                <div
                  key={style.key}
                  className="card flex flex-col gap-4 !py-5 sm:flex-row sm:items-center"
                >
                  <div className="flex h-20 w-32 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-[#0F0F0F]">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={imageSrc}
                      alt={style.label}
                      onLoad={() => setBrowActive((prev) => ({ ...prev, [style.key]: true }))}
                      onError={() =>
                        setBrowActive((prev) =>
                          prev[style.key] === false ? prev : { ...prev, [style.key]: false },
                        )
                      }
                      className={uploaded ? 'h-full w-full object-cover' : 'hidden'}
                    />
                    {uploaded ? null : <span className="text-[11px] text-mist/70">SVG خودکار</span>}
                  </div>

                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-extrabold">{style.label}</p>
                    <p className="mt-1 text-[11px] text-mist">
                      {uploaded ? (
                        <span className="text-emerald-300">تصویر اختصاصی فعال</span>
                      ) : (
                        'تصویر پیش‌فرض (SVG تولیدی)'
                      )}
                    </p>
                    <p className="mt-1 font-mono text-[10px] text-mist/60" dir="ltr">
                      {style.imagePath}
                    </p>
                  </div>

                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    <input
                      ref={(element) => {
                        browInputs.current[style.key] = element;
                      }}
                      type="file"
                      accept={BROW_ACCEPT}
                      className="hidden"
                      onChange={(event) => void handleBrowUpload(style.key, event.target.files?.[0])}
                    />
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => browInputs.current[style.key]?.click()}
                      className="btn-gold !px-5 !py-2.5 !text-xs disabled:opacity-60"
                    >
                      {busy ? (
                        <>
                          <span className="me-2 inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-ink/30 border-t-ink align-[-2px]" />
                          در حال آپلود…
                        </>
                      ) : uploaded ? (
                        'تغییر تصویر'
                      ) : (
                        'آپلود تصویر'
                      )}
                    </button>
                    {uploaded ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void handleBrowReset(style.key)}
                        className="rounded-xl border border-white/10 px-4 py-2.5 text-xs font-bold text-mist transition hover:border-red-400/40 hover:bg-red-500/10 hover:text-red-200 disabled:opacity-60"
                      >
                        حذف
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </section>
        ) : null}

        {/* ========================= تب ۳: تصویر هیرو ========================= */}
        {tab === 'hero' ? (
          <section className="space-y-4">
            <div className="card">
              <h2 className="mb-2 text-sm font-extrabold">تصویر هیرو صفحهٔ اصلی</h2>
              <p className="text-[11px] leading-6 text-mist">
                این تصویر در بخش هیرو (بالای صفحهٔ اصلی، ارتفاع ۳۲۰ پیکسل) به‌عنوان پس‌زمینه نمایش
                داده می‌شود و روی آن عنوان «{HERO_TITLE}» و دکمه‌های واتساپ/اینستاگرام می‌نشیند.
                پیشنهاد: عکس افقی با نسبت ۱۶:۹، فرمت JPG/PNG/WEBP و حداکثر {faSize(MAX_HERO_IMAGE_BYTES)}.
              </p>

              <div className="mt-5 overflow-hidden rounded-2xl border border-white/10 bg-[#0F0F0F]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${HERO_IMAGE_URL}?v=${version}`}
                  alt="تصویر هیرو"
                  onLoad={() => setHeroActive(true)}
                  onError={() => setHeroActive(false)}
                  className={heroActive ? 'h-56 w-full object-cover sm:h-72' : 'hidden'}
                />
                {heroActive ? null : (
                  <div className="flex h-40 flex-col items-center justify-center gap-2 bg-[linear-gradient(135deg,#120F08_0%,#0A0A0A_45%,#17120A_100%)] text-xs text-mist/70">
                    <span>هنوز تصویر هیرویی آپلود نشده است</span>
                    <span className="text-[10px] text-mist/50">پس‌زمینهٔ گرادیانی نمایش داده می‌شود</span>
                  </div>
                )}
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <input
                  ref={heroInput}
                  type="file"
                  accept={HERO_ACCEPT}
                  className="hidden"
                  onChange={(event) => void handleHeroUpload(event.target.files?.[0])}
                />
                <button
                  type="button"
                  disabled={heroUploading}
                  onClick={() => heroInput.current?.click()}
                  className="btn-gold !px-6 !py-3 !text-sm disabled:opacity-60"
                >
                  {heroUploading ? (
                    <>
                      <span className="me-2 inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-ink/30 border-t-ink align-[-2px]" />
                      در حال آپلود…
                    </>
                  ) : heroActive ? (
                    'تغییر تصویر هیرو'
                  ) : (
                    'آپلود تصویر هیرو'
                  )}
                </button>
                {heroActive ? (
                  <button
                    type="button"
                    disabled={heroUploading}
                    onClick={() => void handleHeroReset()}
                    className="rounded-xl border border-white/10 px-5 py-3 text-xs font-bold text-mist transition hover:border-red-400/40 hover:bg-red-500/10 hover:text-red-200 disabled:opacity-60"
                  >
                    حذف تصویر
                  </button>
                ) : null}
              </div>
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* کارت آماری                                                                 */
/* -------------------------------------------------------------------------- */

function StatCard({
  title,
  value,
  hint,
  icon,
}: {
  title: string;
  value: number | null;
  hint: string;
  icon: string;
}) {
  return (
    <div className="card !p-5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-bold text-mist">{title}</p>
        <span aria-hidden="true" className="text-lg">
          {icon}
        </span>
      </div>
      <p className="mt-3 text-3xl font-black text-gold">
        {value === null ? <span className="text-lg text-mist/60">…</span> : faNumber(value)}
      </p>
      <p className="mt-2 text-[11px] text-mist/70">{hint}</p>
    </div>
  );
}
