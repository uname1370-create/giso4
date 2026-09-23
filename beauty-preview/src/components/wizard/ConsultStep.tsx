import React, { useEffect, useRef, useState } from 'react';

/**
 * src/components/wizard/ConsultStep.tsx
 * ---------------------------------------------------------------------------
 * مرحله «مشاور هوشمند ARIA»: پس از آپلود (و ایمنی)، عکس را به /api/consult
 * می‌فرستد، تحلیل کارشناسی + ۳ گزینه متنی را نمایش می‌دهد و گزینه منتخب
 * کاربر (پارامترهای prescription) را به مراحل بعد می‌سپارد.
 * فراخوانی فقط یک‌بار برای هر کلید انجام می‌شود (کش در والد) تا هزینه AI
 * با عقب/جلو رفتن تکرار نشود.
 * ---------------------------------------------------------------------------
 */

export interface ConsultOption {
  id: number;
  title_en: string;
  client_text_fa: string;
  recommended: boolean;
  not_recommended_reason?: string;
  params: Record<string, unknown>;
}

export interface ConsultPrescription {
  analysis_summary_en: string;
  face_shape: string;
  symmetry_score: number;
  skin_undertone: string;
  fitzpatrick: string;
  safety_flags: string[];
  requires_in_person: boolean;
  confidence: number;
  recommended_option: number;
  options: ConsultOption[];
}

interface ConsultStepProps {
  imageBase64: string;
  imagePreviewUrl: string;
  selectedService: string;
  serviceTitle: string;
  initialStyleKey: string;
  initialStyleLabel: string;
  faceMetrics?: Record<string, unknown> | null;
  cacheKey: string;
  cachedData: ConsultPrescription | null;
  selectedOptionId: number;
  onData: (key: string, data: ConsultPrescription) => void;
  onSelectOption: (id: number) => void;
  onBack: () => void;
  onNext: () => void;
}

const FACE_SHAPE_FA: Record<string, string> = {
  oval: 'بیضی',
  round: 'گرد',
  square: 'مربعی',
  oblong: 'کشیده',
  heart: 'قلبی',
  diamond: 'لوزی',
  unknown: 'نامشخص',
};

const UNDERTONE_FA: Record<string, string> = {
  warm: 'گرم',
  cool: 'سرد',
  neutral: 'خنثی',
};

const OPTION_META: Record<number, { label: string; icon: string }> = {
  1: { label: 'پیشنهاد کارشناس', icon: '🌟' },
  2: { label: 'نسخه جسورانه', icon: '✦' },
  3: { label: 'خواست شما', icon: '💫' },
};

type Status = 'loading' | 'success' | 'error';

export const ConsultStep: React.FC<ConsultStepProps> = ({
  imageBase64,
  imagePreviewUrl,
  selectedService,
  serviceTitle,
  initialStyleKey,
  initialStyleLabel,
  faceMetrics,
  cacheKey,
  cachedData,
  selectedOptionId,
  onData,
  onSelectOption,
  onBack,
  onNext,
}) => {
  const [status, setStatus] = useState<Status>(cachedData ? 'success' : 'loading');
  const [data, setData] = useState<ConsultPrescription | null>(cachedData);
  const [error, setError] = useState('');
  const [isDemo, setIsDemo] = useState(false);
  const [nonce, setNonce] = useState(0);
  const fetchedRef = useRef('');
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!imageBase64) {
      setError('NO_PHOTO');
      setStatus('error');
      return;
    }
    if (cachedData) {
      setData(cachedData);
      setStatus('success');
      if (!selectedOptionId) onSelectOption(cachedData.recommended_option || 1);
      return;
    }
    if (fetchedRef.current === cacheKey) return;
    fetchedRef.current = cacheKey;
    setStatus('loading');
    setError('');

    fetch('/api/consult', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        imageBase64,
        service: selectedService,
        initialStyle: initialStyleKey,
        faceMetrics: faceMetrics ?? null,
      }),
    })
      .then(async (res) => {
        const d = await res.json();
        if (!res.ok || !d.ok) throw new Error(d.error || 'خطا در تحلیل هوشمند.');
        return d;
      })
      .then((d) => {
        if (!mountedRef.current) return;
        const p = d.prescription as ConsultPrescription;
        if (!p || !Array.isArray(p.options) || p.options.length !== 3) {
          throw new Error('پاسخ نامعتبر از سرویس تحلیل.');
        }
        setData(p);
        setIsDemo(!!d.demo);
        setStatus('success');
        onData(cacheKey, p);
        if (!selectedOptionId) onSelectOption(p.recommended_option || 1);
      })
      .catch((e: unknown) => {
        if (!mountedRef.current) return;
        setError(e instanceof Error ? e.message : 'خطای ناشناخته.');
        setStatus('error');
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey, nonce]);

  const retry = () => {
    fetchedRef.current = '';
    setNonce((n) => n + 1);
  };

  /* ------------------------------ لودینگ اسکن ------------------------------ */
  if (status === 'loading') {
    return (
      <div className="bg-neutral-900/70 border border-neutral-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl animate-fadeIn">
        <div className="text-center mb-6">
          <h2 className="text-xl font-bold text-neutral-100 mb-1">مشاور هوشمند ARIA ✨</h2>
          <p className="text-xs text-neutral-400">
            تحلیل کارشناسی چهره شما برای {serviceTitle} ...
          </p>
        </div>

        <div className="relative rounded-2xl overflow-hidden border border-neutral-800 bg-neutral-950 aspect-[16/9] max-w-xl mx-auto">
          {imagePreviewUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imagePreviewUrl}
              alt="در حال تحلیل"
              className="absolute inset-0 w-full h-full object-cover opacity-25 filter grayscale"
            />
          )}
          <div className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-amber-400 to-transparent shadow-[0_0_20px_#F59E0B] animate-[scan_2.5s_ease-in-out_infinite]" />
          <div className="absolute top-4 right-4 w-6 h-6 border-t-2 border-r-2 border-amber-400" />
          <div className="absolute top-4 left-4 w-6 h-6 border-t-2 border-l-2 border-amber-400" />
          <div className="absolute bottom-4 right-4 w-6 h-6 border-b-2 border-r-2 border-amber-400" />
          <div className="absolute bottom-4 left-4 w-6 h-6 border-b-2 border-l-2 border-amber-400" />
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="w-12 h-12 rounded-full border-2 border-amber-400 border-t-transparent animate-spin mb-4" />
            <p className="text-sm font-bold text-amber-300 mb-1">
              در حال تحلیل کارشناسی چهره شما...
            </p>
            <p className="text-xs text-neutral-400 font-mono">
              ARIA Face Morphology & Colorimetry...
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-center">
          <button
            onClick={onBack}
            className="px-4 py-2.5 rounded-xl border border-neutral-700 text-neutral-400 text-xs cursor-pointer"
          >
            مرحله قبل
          </button>
        </div>
      </div>
    );
  }

  /* -------------------------------- خطا -------------------------------- */
  if (status === 'error' || !data) {
    const noPhoto = error === 'NO_PHOTO';
    return (
      <div className="bg-neutral-900/70 border border-neutral-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl animate-fadeIn">
        <div className="text-center py-6">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/15 text-red-400 flex items-center justify-center text-3xl">
            {noPhoto ? '📷' : '⚠️'}
          </div>
          <h2 className="text-xl font-bold text-neutral-100 mb-2">
            {noPhoto ? 'عکسی برای تحلیل یافت نشد' : 'تحلیل هوشمند ناموفق بود'}
          </h2>
          <p className="text-xs text-neutral-400 max-w-md mx-auto leading-relaxed mb-6">
            {noPhoto
              ? 'لطفاً ابتدا در مرحله آپلود، عکس چهره خود را بارگذاری کنید.'
              : error}
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <button
              onClick={onBack}
              className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-neutral-700 text-neutral-300 text-xs cursor-pointer"
            >
              بازگشت
            </button>
            {!noPhoto && (
              <>
                <button
                  onClick={retry}
                  className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-amber-500/60 text-amber-300 text-xs font-bold cursor-pointer"
                >
                  تلاش مجدد 🔄
                </button>
                <button
                  onClick={onNext}
                  className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-neutral-800 text-neutral-300 text-xs cursor-pointer"
                >
                  ادامه بدون مشاوره ←
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  /* --------------------------- تحلیل + ۳ گزینه --------------------------- */
  const meta = (id: number) => OPTION_META[id] ?? OPTION_META[1];

  return (
    <div className="bg-neutral-900/70 border border-neutral-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl animate-fadeIn">
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold text-neutral-100 mb-1">
          مشاور هوشمند ARIA ✨ — {serviceTitle}
        </h2>
        <p className="text-xs text-neutral-400">
          مدل اولیه شما: <strong className="text-amber-300">{initialStyleLabel}</strong>
          {isDemo && (
            <span className="ms-2 px-2 py-0.5 rounded-full bg-neutral-800 text-neutral-400 text-[10px]">
              حالت نمایشی
            </span>
          )}
        </p>
      </div>

      {/* باکس تحلیل کارشناسی */}
      <div className="p-5 rounded-2xl bg-gradient-to-br from-amber-500/10 via-neutral-950 to-neutral-950 border border-amber-500/30 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-amber-600 via-amber-400 to-amber-200 flex items-center justify-center text-neutral-950 font-black text-xs shadow-lg shadow-amber-500/20">
            AR
          </div>
          <div>
            <p className="text-sm font-bold text-neutral-100">تحلیل کارشناسی چهره شما</p>
            <p className="text-[10px] text-neutral-400">بر اساس معیارهای تخصصی PMU و تناسب چهره</p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-4">
          <div className="p-3 rounded-xl bg-neutral-950/70 border border-neutral-800 text-center">
            <p className="text-[10px] text-neutral-500 mb-1">فرم صورت</p>
            <p className="text-sm font-bold text-amber-300">
              {FACE_SHAPE_FA[data.face_shape] ?? data.face_shape}
            </p>
          </div>
          <div className="p-3 rounded-xl bg-neutral-950/70 border border-neutral-800 text-center">
            <p className="text-[10px] text-neutral-500 mb-1">تناژ پوست</p>
            <p className="text-sm font-bold text-amber-300">
              {UNDERTONE_FA[data.skin_undertone] ?? data.skin_undertone}
            </p>
          </div>
          <div className="p-3 rounded-xl bg-neutral-950/70 border border-neutral-800 text-center">
            <p className="text-[10px] text-neutral-500 mb-1">تایپ پوستی</p>
            <p className="text-sm font-bold text-amber-300 font-mono" dir="ltr">
              {data.fitzpatrick}
            </p>
          </div>
          <div className="p-3 rounded-xl bg-neutral-950/70 border border-neutral-800 text-center">
            <p className="text-[10px] text-neutral-500 mb-1">تقارن چهره</p>
            <p className="text-sm font-bold text-emerald-300 font-mono" dir="ltr">
              {data.symmetry_score}%
            </p>
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-neutral-950/70 border border-neutral-800 mb-3">
          <p className="text-[10px] text-neutral-500 mb-1.5">گزارش فنی (EN)</p>
          <p className="text-[11px] text-neutral-300 leading-relaxed" dir="ltr">
            {data.analysis_summary_en}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] text-neutral-500">اطمینان تحلیل:</span>
          <div className="flex-1 h-2 rounded-full bg-neutral-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-amber-600 to-amber-400"
              style={{ width: `${Math.max(0, Math.min(100, data.confidence))}%` }}
            />
          </div>
          <span className="text-[11px] text-amber-300 font-mono font-bold" dir="ltr">
            {data.confidence}%
          </span>
        </div>

        {(data.safety_flags.length > 0 || data.requires_in_person) && (
          <div className="mt-3 p-3 rounded-xl bg-red-950/50 border border-red-500/40 text-[11px] text-red-300 leading-relaxed">
            ⚠️ نکته ایمنی: {data.requires_in_person ? 'توصیه می‌شود قبل از اجرا، ویزیت حضوری انجام شود. ' : ''}
            {data.safety_flags.join(' • ')}
          </div>
        )}
      </div>

      {/* ۳ کارت گزینه */}
      <p className="text-sm font-bold text-neutral-100 mb-3 text-center">
        نسخه پیشنهادی ARIA — یکی را انتخاب کنید 👇
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 mb-6">
        {data.options.map((opt) => {
          const isSelected = selectedOptionId === opt.id;
          const m = meta(opt.id);
          return (
            <div
              key={opt.id}
              onClick={() => onSelectOption(opt.id)}
              className={`p-4 rounded-2xl border cursor-pointer transition-all flex flex-col ${
                isSelected
                  ? 'bg-amber-500/15 border-amber-400 shadow-lg shadow-amber-500/10 scale-[1.01]'
                  : 'bg-neutral-950 border-neutral-800/80 hover:border-neutral-600'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-lg">{m.icon}</span>
                {opt.recommended && (
                  <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold">
                    توصیه ARIA ✓
                  </span>
                )}
                {isSelected && (
                  <span className="text-[9px] px-2 py-0.5 rounded-full bg-amber-500/25 text-amber-300 font-bold">
                    ✓ انتخاب شد
                  </span>
                )}
              </div>
              <p className="text-xs font-bold text-neutral-100 mb-1.5">{m.label}</p>
              <p className="text-[11px] text-neutral-300 leading-relaxed flex-1">
                {opt.client_text_fa}
              </p>
              {opt.not_recommended_reason && (
                <p className="mt-2 text-[10px] text-red-400/90 leading-relaxed">
                  ⚠️ {opt.not_recommended_reason}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex flex-col-reverse sm:flex-row justify-between items-stretch sm:items-center gap-3">
        <button
          onClick={onBack}
          className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-neutral-700 text-neutral-400 text-xs cursor-pointer text-center"
        >
          مرحله قبل
        </button>
        <button
          onClick={onNext}
          disabled={!selectedOptionId}
          className={`w-full sm:w-auto px-6 py-2.5 rounded-xl text-xs font-bold text-center transition-all ${
            selectedOptionId
              ? 'bg-amber-500 hover:bg-amber-400 text-neutral-950 shadow-md shadow-amber-500/20 cursor-pointer'
              : 'bg-neutral-800 text-neutral-500 cursor-not-allowed'
          }`}
        >
          تأیید گزینه و ادامه ←
        </button>
      </div>
    </div>
  );
};
