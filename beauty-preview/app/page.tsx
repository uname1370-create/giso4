'use client';

/**
 * app/page.tsx
 * ---------------------------------------------------------------------------
 * تنها صفحهٔ اپلیکیشن — پیش‌نمایش هوشمند ابرو (میکروبلیدینگ)
 *
 * مراحل:
 *   ۱) انتخاب مدل ابرو   ۲) انتخاب رنگ   ۳) آپلود عکس   ۴) دکمهٔ ساخت   ۵) نتیجه
 * تمام فراخوانی‌های هوش مصنوعی از طریق POST /api/generate و فقط سمت سرور
 * انجام می‌شود؛ هیچ کلید API‌ای در مرورگر نیست.
 * ---------------------------------------------------------------------------
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactCompareSlider,
  ReactCompareSliderHandle,
  ReactCompareSliderImage,
} from 'react-compare-slider';

import {
  DEMO_OVERLAY_SIZE,
  buildDemoOverlaySvg,
  svgToDataUri,
  type BrowStyleKey,
} from '@/brow-shapes';
import {
  ACCEPTED_MIME_TYPES,
  ACCEPT_ATTRIBUTE,
  BROW_COLORS,
  EYEBROW_STYLES,
  MAX_FILE_SIZE_BYTES,
  buildWhatsAppLink,
  styleSampleImage,
  type BrowColor,
  type EyebrowStyle,
} from '@/options';

/* -------------------------------------------------------------------------- */
/* انواع و ابزارها                                                            */
/* -------------------------------------------------------------------------- */

type Status = 'idle' | 'loading' | 'success' | 'error';

interface AttemptInfo {
  provider?: string;
  label: string;
  ok: boolean;
  error?: string;
}

interface GenerateResponse {
  ok: boolean;
  provider?: string;
  providerLabel?: string;
  resultUrl?: string;
  demo?: boolean;
  error?: string;
  attempts?: AttemptInfo[];
  ms?: number;
}

const LOADING_MESSAGES = [
  'در حال ارسال تصویر به سرویس هوش مصنوعی…',
  'تحلیل چهره و تشخیص خط ابرو…',
  'اعمال میکروبلیدینگ با مدل و رنگ انتخابی…',
  'آماده‌سازی پیش‌نمایش نهایی…',
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} بایت`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} کیلوبایت`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} مگابایت`;
}

/** آیا همهٔ تلاش‌ها با خطای اتصال/شبکه رد شده‌اند؟ (سرور به اینترنت دسترسی ندارد) */
function looksLikeNetworkFailure(attempts: AttemptInfo[] | undefined): boolean {
  if (!attempts || attempts.length === 0) return false;
  const networkPattern = /fetch failed|Connection error|ECONNRESET|ENOTFOUND|ETIMEDOUT|EAI_AGAIN|زمان انتظار/i;
  return attempts.every((attempt) => !attempt.ok && networkPattern.test(attempt.error ?? ''));
}

function isAcceptedMime(type: string): boolean {
  return (ACCEPTED_MIME_TYPES as readonly string[]).includes(type) || type === 'image/jpg';
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const element = new Image();
    element.onload = () => resolve(element);
    element.onerror = () => reject(new Error('بارگذاری تصویر ناموفق بود'));
    element.src = src;
  });
}

function readFileAsDataUri(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('خواندن فایل ناموفق بود'));
    reader.readAsDataURL(file);
  });
}

/**
 * حالت نمایشی (وقتی هیچ کلید API تنظیم نشده باشد):
 * شکل ابرو با مدل و رنگ انتخابی، به‌صورت محلی و تقریبی روی عکس کشیده می‌شود.
 * این تصویر «شبیه‌سازی» است و نه خروجی واقعی هوش مصنوعی.
 */
async function composeDemoPreview(
  photoDataUri: string,
  styleKey: BrowStyleKey,
  colorHex: string,
): Promise<string> {
  const base = await loadImage(photoDataUri);
  const width = base.naturalWidth || 1024;
  const height = base.naturalHeight || 1024;

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return photoDataUri;

  ctx.drawImage(base, 0, 0, width, height);

  const overlay = await loadImage(svgToDataUri(buildDemoOverlaySvg(styleKey, colorHex)));
  const overlayWidth = width * 0.6;
  const overlayHeight = overlayWidth * (DEMO_OVERLAY_SIZE.height / DEMO_OVERLAY_SIZE.width);

  ctx.save();
  ctx.globalAlpha = 0.92;
  ctx.filter = 'blur(0.8px)';
  ctx.drawImage(overlay, (width - overlayWidth) / 2, height * 0.315, overlayWidth, overlayHeight);
  ctx.restore();

  return canvas.toDataURL('image/jpeg', 0.92);
}

/* -------------------------------------------------------------------------- */
/* اجزای کوچک                                                                 */
/* -------------------------------------------------------------------------- */

function StepSection({
  index,
  title,
  subtitle,
  locked,
  lockHint,
  children,
  id,
}: {
  index: string;
  title: string;
  subtitle?: string;
  locked: boolean;
  lockHint?: string;
  children: React.ReactNode;
  id?: string;
}) {
  return (
    <section
      id={id}
      className={`card transition-all duration-500 ${
        locked ? 'opacity-45 saturate-50' : 'animate-fadeUp opacity-100'
      }`}
    >
      <header className="mb-6 flex items-center gap-3">
        <span className="step-badge">{index}</span>
        <div className="min-w-0">
          <h2 className="text-base font-extrabold sm:text-lg">{title}</h2>
          {subtitle ? <p className="mt-1 text-xs text-mist">{subtitle}</p> : null}
        </div>
        {locked && lockHint ? (
          <span className="ms-auto hidden shrink-0 rounded-full border border-white/10 px-3 py-1 text-[11px] text-mist/80 sm:block">
            {lockHint}
          </span>
        ) : null}
      </header>
      <div className={locked ? 'pointer-events-none select-none' : undefined}>{children}</div>
    </section>
  );
}

function Spinner() {
  return (
    <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-ink/30 border-t-ink" />
  );
}

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="mx-auto h-10 w-10 text-gold" aria-hidden="true">
      <path
        d="M12 16V4m0 0L8 8m4-4 4 4"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4 15v2a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-2"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
      <path
        d="M12 4v12m0 0 4-4m-4 4-4-4M5 20h14"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function WhatsAppIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4" aria-hidden="true">
      <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.28-1.38a9.9 9.9 0 0 0 4.76 1.21h.01c5.46 0 9.91-4.45 9.91-9.91A9.86 9.86 0 0 0 12.04 2Zm0 18.13h-.01a8.2 8.2 0 0 1-4.18-1.15l-.3-.18-3.11.82.83-3.04-.19-.31a8.16 8.16 0 0 1-1.25-4.36c0-4.54 3.7-8.24 8.25-8.24a8.2 8.2 0 0 1 5.83 2.42 8.18 8.18 0 0 1 2.42 5.83c0 4.54-3.7 8.24-8.29 8.24Zm4.52-6.17c-.25-.12-1.47-.72-1.69-.8-.23-.09-.39-.13-.56.12s-.64.8-.78.96c-.14.17-.29.19-.53.06a6.7 6.7 0 0 1-1.97-1.21 7.4 7.4 0 0 1-1.36-1.69c-.14-.25-.01-.38.11-.5.11-.11.25-.29.37-.43.12-.15.16-.25.25-.42.08-.16.04-.31-.02-.43-.06-.12-.55-1.34-.76-1.83-.2-.48-.4-.41-.55-.42h-.47c-.16 0-.42.06-.64.31-.22.25-.84.82-.84 2 0 1.18.86 2.32.98 2.48.12.17 1.68 2.57 4.07 3.6.57.25 1.01.39 1.36.5.57.18 1.09.16 1.5.1.46-.07 1.41-.58 1.61-1.13.2-.56.2-1.03.14-1.13-.06-.1-.22-.17-.47-.29Z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
      <path d="m5 13 4.5 4.5L19 7" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* -------------------------------------------------------------------------- */
/* صفحهٔ اصلی                                                                  */
/* -------------------------------------------------------------------------- */

export default function HomePage() {
  const [selectedStyle, setSelectedStyle] = useState<EyebrowStyle | null>(null);
  const [selectedColor, setSelectedColor] = useState<BrowColor | null>(null);

  const [photoDataUri, setPhotoDataUri] = useState<string | null>(null);
  const [photoName, setPhotoName] = useState<string>('');
  const [photoSize, setPhotoSize] = useState<number>(0);

  const [dragging, setDragging] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  const [status, setStatus] = useState<Status>('idle');
  const [loadingStep, setLoadingStep] = useState(0);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  /* --------------------------------- مشتقات -------------------------------- */
  const samples = useMemo(
    () => EYEBROW_STYLES.map((style) => ({ style, src: styleSampleImage(style) })),
    [],
  );

  const colorUnlocked = Boolean(selectedStyle);
  const uploadUnlocked = Boolean(selectedStyle && selectedColor);
  const generateUnlocked = Boolean(selectedStyle && selectedColor && photoDataUri);
  const canGenerate = generateUnlocked && status !== 'loading';

  const whatsappLink = useMemo(() => {
    if (!selectedStyle || !selectedColor) return null;
    return buildWhatsAppLink(selectedStyle.label, selectedColor.name);
  }, [selectedStyle, selectedColor]);

  /* --------------------------- پیام‌های در حال ساخت -------------------------- */
  useEffect(() => {
    if (status !== 'loading') {
      setLoadingStep(0);
      return;
    }
    const timer = setInterval(() => {
      setLoadingStep((step) => (step + 1) % LOADING_MESSAGES.length);
    }, 5000);
    return () => clearInterval(timer);
  }, [status]);

  /* ------------------------- اسکرول به نتیجه پس از ساخت ------------------------ */
  useEffect(() => {
    if (status === 'success' && resultRef.current) {
      resultRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [status, result]);

  /* -------------------------------- فایل عکس ------------------------------- */
  const handleFile = useCallback(async (file: File | undefined | null) => {
    if (!file) return;
    setFileError(null);

    if (!isAcceptedMime(file.type)) {
      setFileError('فقط فایل‌های JPG، PNG و WEBP پذیرفته می‌شوند.');
      return;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setFileError(`حجم فایل ${formatBytes(file.size)} است؛ حداکثر ۵ مگابایت مجاز است.`);
      return;
    }

    try {
      const dataUri = await readFileAsDataUri(file);
      setPhotoDataUri(dataUri);
      setPhotoName(file.name || 'تصویر آپلودشده');
      setPhotoSize(file.size);
      // با تغییر عکس، نتیجهٔ قبلی بی‌اعتبار می‌شود
      setStatus('idle');
      setResult(null);
      setError(null);
    } catch {
      setFileError('خواندن فایل ناموفق بود. لطفاً دوباره تلاش کنید.');
    }
  }, []);

  const removePhoto = useCallback(() => {
    setPhotoDataUri(null);
    setPhotoName('');
    setPhotoSize(0);
    setFileError(null);
    setStatus('idle');
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  /* --------------------------------- ساخت --------------------------------- */
  const handleGenerate = useCallback(async () => {
    if (!selectedStyle || !selectedColor || !photoDataUri) {
      setError('برای ساخت پیش‌نمایش، مدل ابرو، رنگ و عکس چهره لازم است.');
      return;
    }

    setStatus('loading');
    setError(null);
    setResult(null);

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          imageBase64: photoDataUri,
          style: selectedStyle.label,
          colorName: selectedColor.name,
          colorHex: selectedColor.hex,
        }),
      });

      const data = (await res.json()) as GenerateResponse;

      if (!res.ok || !data.ok) {
        setError(data?.error || 'ساخت پیش‌نمایش ناموفق بود. لطفاً دوباره تلاش کنید.');
        setResult(data);
        setStatus('error');
        return;
      }

      // حالت نمایشی: شکل ابرو به‌صورت محلی و تقریبی روی عکس کشیده می‌شود
      if (data.demo) {
        try {
          const composed = await composeDemoPreview(
            photoDataUri,
            selectedStyle.key,
            selectedColor.hex,
          );
          setResult({ ...data, resultUrl: composed });
        } catch {
          setResult({ ...data, resultUrl: photoDataUri });
        }
        setStatus('success');
        return;
      }

      if (!data.resultUrl) {
        setError('پاسخ سرویس بدون تصویر بود. لطفاً دوباره تلاش کنید.');
        setResult(data);
        setStatus('error');
        return;
      }

      setResult(data);
      setStatus('success');
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? `خطای شبکه: ${requestError.message}`
          : 'خطای ناشناخته در ارتباط با سرور.',
      );
      setStatus('error');
    }
  }, [photoDataUri, selectedColor, selectedStyle]);

  /* --------------------------------- دانلود -------------------------------- */
  const handleDownload = useCallback(async () => {
    const url = result?.resultUrl;
    if (!url) return;

    const fileName = `microblading-${selectedStyle?.key ?? 'preview'}-${
      selectedColor?.hex.replace('#', '') ?? 'color'
    }.jpg`;

    try {
      const res = await fetch(url);
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 5000);
    } catch {
      // در بدترین حالت، تصویر در تب جدید باز می‌شود تا کاربر ذخیره کند
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  }, [result, selectedColor, selectedStyle]);

  /* ---------------------------------- UI ---------------------------------- */
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 lg:py-16">
      {/* ------------------------------- سربرگ ------------------------------- */}
      <header className="text-center">
        <p className="text-[11px] font-bold uppercase tracking-[0.4em] text-gold/80">BEAUTY STUDIO</p>
        <h1 className="mt-5 text-3xl font-extrabold leading-tight sm:text-4xl">
          پیش‌نمایش هوشمند <span className="text-gold">ابرو</span>
        </h1>
        <p className="mt-4 text-sm text-mist sm:text-base">
          مدل و رنگ میکروبلیدینگ را انتخاب کنید، عکس چهره‌تان را آپلود کنید و نتیجه را قبل از
          نوبت‌گرفتن ببینید.
        </p>
        <div className="mx-auto mt-7 h-px w-44 bg-gradient-to-l from-transparent via-gold to-transparent" />
      </header>

      <div className="mt-10 space-y-6 lg:mt-14">
        {/* --------------------------- ۱) مدل ابرو --------------------------- */}
        <StepSection
          index="۱"
          title="مدل ابرو را انتخاب کنید"
          subtitle="چهار سبک محبوب میکروبلیدینگ"
          locked={false}
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {samples.map(({ style, src }) => {
              const isSelected = selectedStyle?.key === style.key;
              return (
                <button
                  key={style.key}
                  type="button"
                  onClick={() => {
                    setSelectedStyle(style);
                    setStatus('idle');
                    setResult(null);
                    setError(null);
                  }}
                  aria-pressed={isSelected}
                  className={`group relative overflow-hidden rounded-2xl border p-4 text-center transition-all duration-300 ${
                    isSelected
                      ? 'border-gold bg-gold/[0.07] shadow-gold'
                      : 'border-white/[0.08] bg-cardSoft hover:-translate-y-0.5 hover:border-gold/40'
                  }`}
                >
                  <div className="mb-3 flex h-28 items-center justify-center rounded-xl bg-[radial-gradient(circle_at_50%_40%,rgba(212,175,55,0.12),transparent_65%)]">
                    <img
                      src={src}
                      alt={style.label}
                      className="h-20 w-auto max-w-full opacity-95 transition group-hover:scale-[1.04]"
                      draggable={false}
                    />
                  </div>
                  <span className="block text-sm font-bold">{style.label}</span>
                  <span className="mt-1 block text-[11px] text-mist">{style.hint}</span>
                  {isSelected ? (
                    <span className="absolute end-3 top-3 flex h-7 w-7 items-center justify-center rounded-full bg-gold text-ink">
                      <CheckIcon />
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </StepSection>

        {/* ----------------------------- ۲) رنگ ----------------------------- */}
        <StepSection
          index="۲"
          title="رنگ ابرو را انتخاب کنید"
          subtitle="شش رنگ استاندارد پیگمنت میکروبلیدینگ"
          locked={!colorUnlocked}
          lockHint="ابتدا مدل ابرو"
        >
          <div className="flex flex-wrap items-center gap-x-6 gap-y-5">
            {BROW_COLORS.map((color) => {
              const isSelected = selectedColor?.hex === color.hex;
              return (
                <div key={color.hex} className="group relative">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedColor(color);
                      setStatus('idle');
                      setResult(null);
                      setError(null);
                    }}
                    aria-pressed={isSelected}
                    aria-label={color.name}
                    title={color.name}
                    className={`h-12 w-12 rounded-full transition-all duration-300 ${
                      isSelected
                        ? 'scale-105 ring-2 ring-white ring-offset-4 ring-offset-card'
                        : 'ring-1 ring-white/20 hover:scale-105 hover:ring-gold/60'
                    }`}
                    style={{ backgroundColor: color.hex }}
                  />
                  <span className="tooltip">{color.name}</span>
                </div>
              );
            })}
          </div>

          <p className="mt-5 text-xs text-mist">
            {selectedColor ? (
              <>
                رنگ انتخابی:{' '}
                <span className="font-bold text-gold">{selectedColor.name}</span>{' '}
                <span className="font-mono text-[11px] text-mist/80">({selectedColor.hex})</span>
              </>
            ) : (
              'روی هر دایره بمانید تا نام فارسی رنگ را ببینید.'
            )}
          </p>
        </StepSection>

        {/* --------------------------- ۳) آپلود عکس -------------------------- */}
        <StepSection
          index="۳"
          title="عکس چهره خود را آپلود کنید"
          subtitle="عکس واضح، روبه‌رو و بدون فیلتر بهترین نتیجه را می‌دهد"
          locked={!uploadUnlocked}
          lockHint="ابتدا مدل و رنگ"
        >
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              void handleFile(event.dataTransfer.files?.[0]);
            }}
            className={`cursor-pointer rounded-2xl border border-dashed px-6 py-9 text-center transition-all duration-300 ${
              dragging
                ? 'border-gold bg-gold/10'
                : 'border-white/15 hover:border-gold/50 hover:bg-white/[0.02]'
            }`}
          >
            <UploadIcon />
            <p className="mt-4 text-sm font-bold">عکس چهره خود را آپلود کنید</p>
            <p className="mt-2 text-xs text-mist">
              فایل را اینجا رها کنید یا کلیک کنید — JPG، PNG یا WEBP، حداکثر ۵ مگابایت
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT_ATTRIBUTE}
              className="hidden"
              onChange={(event) => void handleFile(event.target.files?.[0])}
            />
          </div>

          {fileError ? (
            <p className="mt-4 rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-xs font-semibold text-red-200">
              {fileError}
            </p>
          ) : null}

          {photoDataUri ? (
            <div className="mt-5 flex items-center gap-4 rounded-2xl border border-white/[0.08] bg-cardSoft p-3">
              <img
                src={photoDataUri}
                alt="پیش‌نمایش عکس آپلودشده"
                className="h-16 w-16 rounded-xl object-cover ring-1 ring-white/10"
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold">{photoName}</p>
                <p className="mt-1 text-[11px] text-mist">{formatBytes(photoSize)}</p>
              </div>
              <button type="button" onClick={removePhoto} className="btn-outline !px-4 !py-2 text-xs">
                حذف عکس
              </button>
            </div>
          ) : null}
        </StepSection>

        {/* ---------------------------- ۴) دکمهٔ ساخت -------------------------- */}
        <StepSection
          index="۴"
          title="پیش‌نمایش هوشمند را بسازید"
          subtitle="ترکیب مدل، رنگ و عکس شما در یک تصویر"
          locked={false}
        >
          <button
            type="button"
            disabled={!canGenerate}
            onClick={() => void handleGenerate()}
            className="btn-gold w-full text-lg"
          >
            {status === 'loading' ? (
              <>
                <Spinner />
                <span>{LOADING_MESSAGES[loadingStep]}</span>
              </>
            ) : (
              'ایجاد پیش‌نمایش هوشمند'
            )}
          </button>

          {!generateUnlocked ? (
            <p className="mt-4 text-center text-xs text-mist">
              برای فعال شدن دکمه، انتخاب مدل ابرو، انتخاب رنگ و آپلود عکس لازم است.
            </p>
          ) : (
            <p className="mt-4 text-center text-[11px] text-mist/80">
              ساخت تصویر ممکن است تا یک دقیقه زمان ببرد؛ لطفاً صفحه را نبندید.
            </p>
          )}

          {status === 'error' && error ? (
            <div className="mt-5 rounded-2xl border border-red-400/30 bg-red-500/10 p-4">
              <p className="text-xs font-bold text-red-100">خطا در ساخت پیش‌نمایش</p>
              <p className="mt-2 text-xs leading-6 text-red-100/90">{error}</p>

              {result?.attempts?.length ? (
                <details className="mt-3">
                  <summary className="cursor-pointer text-[11px] text-red-100/70">
                    جزئیات فنی تلاش سرویس‌ها
                  </summary>
                  <ul className="mt-2 space-y-1 text-[11px] text-red-100/70">
                    {result.attempts.map((attempt, index) => (
                      <li key={`${attempt.provider ?? attempt.label}-${index}`}>
                        {attempt.ok ? '✓' : '✕'} {attempt.label}
                        {attempt.error ? ` — ${attempt.error}` : ''}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}

              {looksLikeNetworkFailure(result?.attempts) ? (
                <p className="mt-3 rounded-xl border border-gold/30 bg-gold/10 px-3 py-2 text-[11px] leading-6 text-gold/90">
                  <strong>نکته:</strong> همهٔ سرویس‌ها با خطای <em>اتصال</em> رد شده‌اند، نه با خطای
                  کلید. یعنی این سرور به اینترنت دسترسی ندارد. اپ را روی کامپیوتر/سرور خودتان
                  (<code>npm run dev</code>) اجرا کنید یا وضعیت کلیدها را با{' '}
                  <code>/api/providers?check=1</code> ببینید.
                </p>
              ) : null}

              <p className="mt-3 text-[11px] text-red-100/70">
                اگر همهٔ سرویس‌ها پاسخ ندهند، کلیدهای API را در فایل <code>.env</code> (یا{' '}
                <code>.env.local</code>) بررسی کنید و با <code>/api/providers?check=1</code> تست
                بگیرید.
              </p>
            </div>
          ) : null}
        </StepSection>

        {/* ----------------------------- ۵) نتیجه ----------------------------- */}
        <div ref={resultRef}>
          {status === 'success' && result?.resultUrl && photoDataUri ? (
            <section className="card animate-fadeUp">
              <header className="mb-6 flex flex-wrap items-center gap-3">
                <span className="step-badge">۵</span>
                <div>
                  <h2 className="text-base font-extrabold sm:text-lg">نتیجهٔ پیش‌نمایش</h2>
                  <p className="mt-1 text-xs text-mist">
                    دستگیرهٔ وسط را بکشید تا «قبل» و «بعد» را مقایسه کنید.
                  </p>
                </div>
                <span className="ms-auto rounded-full border border-gold/30 bg-gold/10 px-3 py-1 text-[11px] font-bold text-gold">
                  {result.demo ? 'حالت نمایشی (بدون کلید API)' : `ساخته‌شده با ${result.providerLabel}`}
                </span>
              </header>

              <div className="giso-compare overflow-hidden rounded-2xl border border-white/[0.08] bg-black">
                <ReactCompareSlider
                  itemOne={
                    <div className="relative h-full w-full">
                      <ReactCompareSliderImage
                        src={photoDataUri}
                        alt="قبل"
                        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                      />
                      <span className="side-label left-4">قبل</span>
                    </div>
                  }
                  itemTwo={
                    <div className="relative h-full w-full">
                      <ReactCompareSliderImage
                        src={result.resultUrl}
                        alt="بعد"
                        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                      />
                      <span className="side-label right-4">بعد</span>
                    </div>
                  }
                  handle={
                    <ReactCompareSliderHandle
                      buttonStyle={{
                        width: 46,
                        height: 46,
                        border: '2px solid #D4AF37',
                        background: 'rgba(10,10,10,0.85)',
                        color: '#D4AF37',
                        boxShadow: '0 10px 30px -12px rgba(212,175,55,0.9)',
                        backdropFilter: 'blur(6px)',
                      }}
                      linesStyle={{ color: 'rgba(212,175,55,0.85)', width: 2 }}
                    />
                  }
                  style={{ width: '100%', height: 'min(68vh, 620px)' }}
                />
              </div>

              {result.demo ? (
                <p className="mt-4 rounded-xl border border-gold/25 bg-gold/[0.06] px-4 py-3 text-[11px] leading-6 text-gold/90">
                  این تصویر <strong>شبیه‌سازی محلی</strong> است (چون هیچ کلید API فعالی تنظیم نشده)
                  و شکل ابرو به‌صورت تقریبی روی عکس کشیده شده است. با وارد کردن کلید یکی از
                  سرویس‌ها در فایل <code>.env.local</code>، پیش‌نمایش واقعی با هوش مصنوعی ساخته
                  می‌شود.
                </p>
              ) : null}

              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <button type="button" onClick={() => void handleDownload()} className="btn-gold flex-1 !py-3.5 !text-base">
                  <DownloadIcon />
                  دانلود تصویر
                </button>

                {whatsappLink ? (
                  <a
                    href={whatsappLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-whatsapp flex-1 !py-3.5 !text-base"
                  >
                    <WhatsAppIcon />
                    رزرو نوبت در واتساپ
                  </a>
                ) : null}
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11px] text-mist">
                <span>
                  مدل: <span className="font-bold text-white">{selectedStyle?.label}</span>
                </span>
                <span className="flex items-center gap-2">
                  رنگ: <span className="font-bold text-white">{selectedColor?.name}</span>
                  <span
                    className="inline-block h-3 w-3 rounded-full ring-1 ring-white/25"
                    style={{ backgroundColor: selectedColor?.hex }}
                  />
                </span>
                {typeof result.ms === 'number' && !result.demo ? (
                  <span>زمان ساخت: {(result.ms / 1000).toFixed(1)} ثانیه</span>
                ) : null}
                <button
                  type="button"
                  onClick={() => void handleGenerate()}
                  className="ms-auto text-[11px] font-bold text-gold underline decoration-gold/40 underline-offset-4 transition hover:text-gold-soft"
                >
                  ساخت دوباره
                </button>
              </div>
            </section>
          ) : (
            <section className="rounded-3xl border border-dashed border-white/[0.08] px-6 py-10 text-center">
              <p className="text-sm font-bold text-mist">پیش‌نمایش شما اینجا نمایش داده می‌شود</p>
              <p className="mt-2 text-xs text-mist/70">
                با انتخاب مدل، رنگ و آپلود عکس، دکمهٔ «ایجاد پیش‌نمایش هوشمند» فعال می‌شود.
              </p>
            </section>
          )}
        </div>
      </div>

      {/* ------------------------------- پانویس ------------------------------ */}
      <footer className="mt-12 border-t border-white/[0.06] pt-6 text-center text-[11px] leading-6 text-mist/70">
        <p>
          این پیش‌نمایش با هوش مصنوعی ساخته می‌شود و نتیجهٔ نهایی بستگی به پوست، مو و تکنیک اجرا
          دارد. برای مشاورهٔ دقیق، در واتساپ پیام بدهید.
        </p>
        <p className="mt-3">میکروبلیدینگ تخصصی — خانم رجبی · تمام حقوق محفوظ است.</p>
      </footer>
    </main>
  );
}
