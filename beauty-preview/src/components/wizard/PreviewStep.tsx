'use client';

/**
 * src/components/wizard/PreviewStep.tsx
 * ---------------------------------------------------------------------------
 * مرحله پیش‌نمایش هوشمند:
 * اجرای استخراج لندمارک‌های چهره با MediaPipe و ترکیب Hard Composite در مرورگر
 * بدون کوچک‌ترین وابستگی به پایتون یا مصرف منابع رم/سی‌پی‌یوی سرور
 * ---------------------------------------------------------------------------
 */

import React, { useState } from 'react';
import {
  ReactCompareSlider,
  ReactCompareSliderHandle,
  ReactCompareSliderImage,
} from 'react-compare-slider';
import { type ServiceInfo } from '@/services-content';
import { type TechniqueStyleOption } from '@/techniques';
import { type PlanTier } from '@/plan-config';

import { getFaceLandmarker } from '@/lib/vision/face-landmarker';
import { extractFeatureLandmarks } from '@/lib/vision/landmarks-extractor';
import { executeClientComposite, loadImage, type ServiceTarget } from '@/lib/vision/canvas-composite';

interface PreviewStepProps {
  selectedService: string;
  currentServiceInfo: ServiceInfo;
  planTier?: PlanTier;
  activeTechnique?: TechniqueStyleOption;
  genStatus: 'idle' | 'loading' | 'success' | 'error';
  statusMessage: string;
  resultImage: string;
  imagePreviewUrl: string;
  isDemo: boolean;
  isStale?: boolean;
  prescriptionOption?: { id: number; title_en: string } | null;
  onGenerate: () => void;
  onBack: () => void;
  onNext: () => void;
  onClientCompositeFinish?: (compositeDataUri: string) => void;
}

export const PreviewStep: React.FC<PreviewStepProps> = ({
  selectedService,
  currentServiceInfo,
  planTier = 'gold',
  activeTechnique,
  genStatus,
  statusMessage,
  resultImage,
  imagePreviewUrl,
  isDemo,
  isStale = false,
  prescriptionOption = null,
  onGenerate,
  onBack,
  onNext,
  onClientCompositeFinish,
}) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [clientCompositing, setClientCompositing] = useState(false);
  const [finalCompositedImage, setFinalCompositedImage] = useState<string>('');

  const isGold = planTier === 'gold';
  const watermarkEnabled = planTier === 'bronze';

  // بزرگنمایی هوشمند: نقطه پیش‌فرض زوم روی ناحیه هدف هر خدمت
  const [zoom, setZoom] = useState(1);
  const ZOOM_ORIGIN: Record<string, string> = {
    eyebrows: '50% 26%',
    lips: '50% 74%',
    eyeliner: '50% 40%',
    removal: '50% 50%',
  };
  const zoomOrigin = ZOOM_ORIGIN[selectedService] ?? '50% 50%';

  // هر زمان تصویر خروجی جنریت شد، ترکیب کلاینتی Hard Composite را بی‌درنگ اجرا می‌کنیم
  React.useEffect(() => {
    if (!resultImage || !imagePreviewUrl || isDemo) {
      setFinalCompositedImage(resultImage);
      return;
    }

    let isMounted = true;

    async function runClientVision() {
      try {
        setClientCompositing(true);

        // ۱. بارگذاری تصویر اصلی در یک المنت موقت جهت استخراج لندمارک‌ها
        const baseImg = await loadImage(imagePreviewUrl);
        const landmarker = await getFaceLandmarker();
        const results = landmarker.detect(baseImg);

        if (results.faceLandmarks && results.faceLandmarks.length > 0) {
          const landmarks = results.faceLandmarks[0];
          const features = extractFeatureLandmarks(landmarks, baseImg.width, baseImg.height);

          // ۲. اجرای Hard Composite دقیق با Canvas در مرورگر
          const composited = await executeClientComposite(
            imagePreviewUrl,
            resultImage,
            features,
            (selectedService as ServiceTarget) || 'eyebrows',
            {
              featherRadius: selectedService === 'eyeliner' ? 3 : 8,
              watermarkEnabled,
            }
          );

          if (isMounted) {
            setFinalCompositedImage(composited);
            if (onClientCompositeFinish) {
              onClientCompositeFinish(composited);
            }
          }
        } else {
          // در صورت عدم شناسایی لندمارک، همان تصویر خام AI استفاده می‌شود
          if (isMounted) setFinalCompositedImage(resultImage);
        }
      } catch (err) {
        console.warn('Client-side vision processing notice:', err);
        if (isMounted) setFinalCompositedImage(resultImage);
      } finally {
        if (isMounted) setClientCompositing(false);
      }
    }

    runClientVision();

    return () => {
      isMounted = false;
    };
  }, [resultImage, imagePreviewUrl, isDemo, selectedService, onClientCompositeFinish]);

  if (selectedService === 'removal') {
    return (
      <div className="bg-neutral-900/70 border border-neutral-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl animate-fadeIn">
        <div className="text-center py-6 animate-fadeIn">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center text-3xl">
            🫧
          </div>
          <h2 className="text-xl font-bold text-neutral-100 mb-2">
            ارزیابی بالینی تاتوی قدیمی (ریمو تخصصی)
          </h2>
          <p className="text-xs text-neutral-300 max-w-lg mx-auto leading-relaxed mb-6">
            طبق پروتکل‌های ایمنی سلامت و الزامات علمی، خروج پیگمنت‌های تاتوی قدیمی نیازمند
            بررسی عمق کاشت، نوع رنگ و سن تاتو در معاینه حضوری توسط متخصص است.
          </p>
          <div className="p-4 rounded-xl bg-neutral-950 border border-amber-500/30 max-w-md mx-auto text-xs text-amber-300 mb-8 text-right space-y-2">
            <p>• متد ریمو: آنزیمی ایمن بدون اسیدهای مخرب و بدون لیزر سوختگی‌زا</p>
            <p>• تعداد جلسات معمول: ۱ تا ۳ جلسه بر اساس تیرگی رنگدانه</p>
          </div>
          <button
            onClick={onNext}
            className="px-8 py-3 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 text-neutral-950 font-bold text-xs shadow-lg shadow-amber-500/25 cursor-pointer"
          >
            ثبت اطلاعات برای ویزیت و ارزیابی حضوری 📅
          </button>
        </div>
      </div>
    );
  }

  const effectiveResultImage = finalCompositedImage || resultImage;

  return (
    <div className="bg-neutral-900/70 border border-neutral-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl animate-fadeIn">
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold text-neutral-100 mb-1">
          پیش‌نمایش اختصاصی {currentServiceInfo?.title}
        </h2>
        <p className="text-xs text-neutral-400">
          تکنیک انتخابی: <strong className="text-amber-300">{activeTechnique?.label}</strong>
        </p>
        {prescriptionOption && (
          <p className="mt-2 inline-block text-[11px] font-bold text-emerald-300 bg-emerald-950/60 border border-emerald-500/40 rounded-full px-3 py-1">
            ✨ نسخه ARIA: گزینه {prescriptionOption.id}
          </p>
        )}
        {isStale && effectiveResultImage && (
          <div className="mt-4 p-3.5 rounded-xl bg-amber-950/60 border border-amber-500/50 max-w-lg mx-auto">
            <p className="text-xs text-amber-200 font-bold mb-2">
              ⚠️ انتخاب شما تغییر کرده — این پیش‌نمایش مربوط به مدل قبلی است
            </p>
            <button
              onClick={onGenerate}
              className="px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs shadow-md shadow-amber-500/20 cursor-pointer"
            >
              🔄 ساخت مجدد با انتخاب جدید
            </button>
          </div>
        )}
      </div>

      <div
        className={`relative rounded-2xl overflow-hidden border border-neutral-800 bg-neutral-950 transition-all mx-auto flex items-center justify-center ${
          isFullscreen ? 'fixed inset-4 z-[9999] max-w-none shadow-2xl' : 'aspect-[4/3] max-w-lg'
        }`}
      >
        {/* انیمیشن اسکن بیومتریک طلایی فقط در پلن طلایی، لودینگ ساده در برنزی و نقره‌ای */}
        {(genStatus === 'loading' || clientCompositing) && (
          <div className="absolute inset-0 z-30 bg-neutral-950/85 backdrop-blur-sm flex flex-col items-center justify-center p-6 text-center select-none overflow-hidden">
            {isGold && imagePreviewUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={imagePreviewUrl}
                alt="Scanning Face"
                className="absolute inset-0 w-full h-full object-cover opacity-20 filter grayscale"
              />
            )}

            {/* خط لیزر اسکن متحرک عمودی فقط در پلن طلایی */}
            {isGold && (
              <div className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-amber-400 to-transparent shadow-[0_0_20px_#F59E0B] animate-[scan_2.5s_ease-in-out_infinite]" />
            )}

            {/* براکت‌های طلایی ۴ گوشه اسکن بیومتریک فقط در پلن طلایی */}
            {isGold && (
              <>
                <div className="absolute top-4 right-4 w-6 h-6 border-t-2 border-r-2 border-amber-400" />
                <div className="absolute top-4 left-4 w-6 h-6 border-t-2 border-l-2 border-amber-400" />
                <div className="absolute bottom-4 right-4 w-6 h-6 border-b-2 border-r-2 border-amber-400" />
                <div className="absolute bottom-4 left-4 w-6 h-6 border-b-2 border-l-2 border-amber-400" />
              </>
            )}

            <div className="relative z-10 flex flex-col items-center">
              <div className="w-12 h-12 rounded-full border-2 border-amber-400 border-t-transparent animate-spin mb-4" />
              <p className="text-sm font-bold text-amber-300 mb-1">
                {clientCompositing
                  ? 'در حال ترکیب فوق‌دقیق و ماسک‌گذاری لندمارک‌های چهره با GPU...'
                  : statusMessage}
              </p>
              <p className="text-xs text-neutral-400 font-mono">
                {isGold
                  ? (clientCompositing ? 'VIP Biometric Hard Composite' : 'AI Biometric Mesh & Pigment Calibration...')
                  : 'AI Photo Generation & Processing...'}
              </p>
            </div>
          </div>
        )}

        {effectiveResultImage && imagePreviewUrl ? (
          <div className="relative w-full h-full">
            {/* برچسب‌های شیشه‌ای شناور ریسپانسیو */}
            <div className="absolute top-2.5 right-2.5 z-20 px-2.5 py-1 rounded-full bg-neutral-950/70 backdrop-blur-md border border-white/20 text-[9px] sm:text-[10px] text-neutral-200 font-medium shadow-lg pointer-events-none">
              قبل | طبیعی
            </div>
            <div className="absolute top-2.5 left-2.5 z-20 px-2.5 py-1 rounded-full bg-amber-500/30 backdrop-blur-md border border-amber-400/50 text-[9px] sm:text-[10px] text-amber-200 font-bold shadow-lg pointer-events-none flex items-center gap-1">
              <span>بعد | پیش‌نمایش</span>
              <span className="text-xs">✨</span>
            </div>

            {/* دکمه زوم / تمام‌صفحه */}
            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="absolute bottom-2.5 left-2.5 z-20 px-2.5 py-1.5 rounded-xl bg-neutral-950/80 backdrop-blur-md border border-neutral-700 hover:border-amber-400 text-neutral-300 hover:text-amber-300 text-[9px] sm:text-[10px] transition-all cursor-pointer flex items-center gap-1 shadow-lg"
            >
              <span>{isFullscreen ? 'خروج ✕' : 'تمام‌صفحه 🔍'}</span>
            </button>

            {/* کنترل‌های بزرگنمایی هوشمند روی ناحیه هدف */}
            <div className="absolute bottom-2.5 right-2.5 z-20 flex items-center gap-1.5">
              <button
                onClick={() => setZoom((z) => Math.max(1, +(z - 0.5).toFixed(1)))}
                className="px-2.5 py-1.5 rounded-xl bg-neutral-950/80 backdrop-blur-md border border-neutral-700 hover:border-amber-400 text-neutral-300 hover:text-amber-300 text-xs font-bold transition-all cursor-pointer shadow-lg"
                title="کوچک‌نمایی"
              >
                −
              </button>
              <span className="px-2 py-1.5 rounded-xl bg-neutral-950/80 backdrop-blur-md border border-neutral-700 text-amber-300 text-[10px] font-mono font-bold shadow-lg min-w-[3rem] text-center">
                {zoom.toFixed(1)}×
              </span>
              <button
                onClick={() => setZoom((z) => Math.min(3, +(z + 0.5).toFixed(1)))}
                className="px-2.5 py-1.5 rounded-xl bg-neutral-950/80 backdrop-blur-md border border-neutral-700 hover:border-amber-400 text-neutral-300 hover:text-amber-300 text-xs font-bold transition-all cursor-pointer shadow-lg"
                title="بزرگنمایی روی ناحیه هدف"
              >
                +
              </button>
              {zoom > 1 && (
                <button
                  onClick={() => setZoom(1)}
                  className="px-2.5 py-1.5 rounded-xl bg-amber-500/80 backdrop-blur-md border border-amber-400 text-neutral-950 text-xs font-bold transition-all cursor-pointer shadow-lg"
                  title="بازنشانی زوم"
                >
                  ⟲
                </button>
              )}
            </div>

            <div
              className="w-full h-full transition-transform duration-300 ease-out"
              style={{ transform: `scale(${zoom})`, transformOrigin: zoomOrigin }}
            >
            <ReactCompareSlider
              className="w-full h-full"
              itemOne={
                <ReactCompareSliderImage
                  src={imagePreviewUrl}
                  alt="چهره قبل"
                  className="object-cover w-full h-full"
                />
              }
              itemTwo={
                isDemo ? (
                  <div className="relative w-full h-full">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={imagePreviewUrl}
                      alt="پس‌زمینه"
                      className="object-cover w-full h-full"
                    />
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={effectiveResultImage}
                      alt="اورلی دمو"
                      className="absolute top-[28%] left-1/2 -translate-x-1/2 w-[65%] pointer-events-none drop-shadow-md"
                    />
                  </div>
                ) : (
                  <ReactCompareSliderImage
                    src={effectiveResultImage}
                    alt="پیش‌نمایش نهایی"
                    className="object-cover w-full h-full"
                  />
                )
              }
              handle={
                <ReactCompareSliderHandle
                  buttonStyle={{
                    backgroundColor: '#F59E0B',
                    color: '#0A0A0A',
                    border: '2px solid #FEF3C7',
                    boxShadow: '0 0 15px rgba(245, 158, 11, 0.6)',
                  }}
                  linesStyle={{ backgroundColor: '#F59E0B' }}
                />
              }
            />
            </div>
          </div>
        ) : (
          <div className="p-8 text-center">
            <button
              onClick={onGenerate}
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 text-neutral-950 font-bold text-xs shadow-lg shadow-amber-500/25 cursor-pointer"
            >
              ⚡ تولید پیش‌نمایش {currentServiceInfo?.title}
            </button>
          </div>
        )}
      </div>

      <div className="mt-6 flex flex-col-reverse sm:flex-row justify-between items-stretch sm:items-center gap-3">
        <button
          onClick={onBack}
          className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-neutral-700 text-neutral-400 text-xs cursor-pointer text-center"
        >
          تغییر مدل و سلیقه
        </button>
        <button
          onClick={onNext}
          className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs shadow-md shadow-amber-500/20 cursor-pointer text-center"
        >
          رزرو نوبت حضوری در مشهد 📅
        </button>
      </div>
    </div>
  );
};
