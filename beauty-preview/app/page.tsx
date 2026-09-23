'use client';

/**
 * app/page.tsx
 * ---------------------------------------------------------------------------
 * ویزارد هوشمند ۷ مرحله‌ای استودیو PMU عسل رجبی (معماری کامپوننت‌بندی شده)
 * ---------------------------------------------------------------------------
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  buildDemoOverlaySvg,
  svgToDataUri,
  type BrowStyleKey,
} from '@/brow-shapes';
import {
  ACCEPTED_MIME_TYPES,
  MAX_FILE_SIZE_BYTES,
} from '@/options';
import { StepIndicator } from '@/components/StepIndicator';
import { SERVICES_CONTENT, type ServiceInfo } from '@/services-content';
import { SERVICE_TECHNIQUES, type TechniqueStyleOption } from '@/techniques';

// کامپوننت‌های ماژولار مراحل ویزارد
import { HeroStep } from '@/components/wizard/HeroStep';
import { ServiceSelectStep } from '@/components/wizard/ServiceSelectStep';
import { UploadStep } from '@/components/wizard/UploadStep';
import { SafetyCheckStep } from '@/components/wizard/SafetyCheckStep';
import { PreferencesStep } from '@/components/wizard/PreferencesStep';
import { PreviewStep } from '@/components/wizard/PreviewStep';
import { BookingStep } from '@/components/wizard/BookingStep';
import { ConsultStep, type ConsultPrescription } from '@/components/wizard/ConsultStep';
import { AiChatWidget } from '@/components/AiChatWidget';
import { type PlanTier } from '@/plan-config';

type ServiceType = 'eyebrows' | 'lips' | 'eyeliner' | 'removal';
type WizardStep = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;
type GenerationStatus = 'idle' | 'loading' | 'success' | 'error';

interface ClientPreferences {
  dailyMakeup: 'natural' | 'soft' | 'bold';
  browShape: 'natural' | 'defined';
  density: 'fluffy' | 'dense';
}

interface MedicalSafetyCheck {
  pregnantOrNursing: boolean;
  skinAllergyOrKeloid: boolean;
  specialMedication: boolean;
}

interface BookingFormData {
  fullName: string;
  phoneNumber: string;
  instagramId: string;
  notes: string;
}

const WIZARD_STEPS = [
  { id: 0, title: 'خانه' },
  { id: 1, title: 'انتخاب خدمت' },
  { id: 2, title: 'آپلود تصویر' },
  { id: 3, title: 'بررسی ایمنی' },
  { id: 4, title: 'مشاور هوشمند' },
  { id: 5, title: 'سلیقه و انتخاب مدل' },
  { id: 6, title: 'پیش‌نمایش هوشمند' },
  { id: 7, title: 'رزرو نوبت' },
];

export default function HomePage() {
  const [currentStep, setCurrentStep] = useState<WizardStep>(0);
  const [selectedService, setSelectedService] = useState<ServiceType>('eyebrows');
  const [planTier, setPlanTier] = useState<PlanTier>('gold');
  const [tenantName, setTenantName] = useState<string>('استودیو تخصصی عسل رجبی');
  const [customAssistantName, setCustomAssistantName] = useState<string>('');

  useEffect(() => {
    fetch('/api/plan')
      .then((res) => res.json())
      .then((data) => {
        if (data.ok && data.tenant) {
          if (data.tenant.planTier) setPlanTier(data.tenant.planTier);
          if (data.tenant.name) setTenantName(data.tenant.name);
          if (data.tenant.customAssistantName) setCustomAssistantName(data.tenant.customAssistantName);
        }
      })
      .catch(() => {});
  }, []);

  const [imageBase64, setImageBase64] = useState<string>('');
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string>('');
  const [uploadError, setUploadError] = useState<string>('');

  const [educationalWarning, setEducationalWarning] = useState<string>('');

  const [safety, setSafety] = useState<MedicalSafetyCheck>({
    pregnantOrNursing: false,
    skinAllergyOrKeloid: false,
    specialMedication: false,
  });

  const isSafetyRestricted =
    safety.pregnantOrNursing || safety.skinAllergyOrKeloid || safety.specialMedication;

  // کش مشاوره هوشمند: کلید = خدمت + استایل + اثر سلفی؛ داده و گزینه منتخب کاربر
  const [consultCacheKey, setConsultCacheKey] = useState('');
  const [consultData, setConsultData] = useState<ConsultPrescription | null>(null);
  const [selectedOptionId, setSelectedOptionId] = useState(0);

  const [preferences, setPreferences] = useState<ClientPreferences>({
    dailyMakeup: 'natural',
    browShape: 'natural',
    density: 'fluffy',
  });

  const availableTechniques = useMemo<TechniqueStyleOption[]>(() => {
    if (selectedService === 'removal') return [];
    return SERVICE_TECHNIQUES[selectedService] || [];
  }, [selectedService]);

  const [selectedTechniqueKey, setSelectedTechniqueKey] = useState<string>('hairstroke');

  useEffect(() => {
    if (selectedService !== 'removal' && availableTechniques.length > 0) {
      setSelectedTechniqueKey(availableTechniques[0].key);
    }
  }, [selectedService, availableTechniques]);

  const activeTechnique = useMemo<TechniqueStyleOption | undefined>(() => {
    return availableTechniques.find((t) => t.key === selectedTechniqueKey) || availableTechniques[0];
  }, [availableTechniques, selectedTechniqueKey]);

  // گزینه منتخب مشاوره هوشمند (منبع نسخه ARIA برای تولید و نمایش)
  const selectedConsultOption = useMemo(() => {
    if (!consultData || selectedOptionId <= 0) return null;
    return consultData.options.find((o) => o.id === selectedOptionId) ?? null;
  }, [consultData, selectedOptionId]);

  // گوش دادن به اکشن‌های چت‌بات برای تغییر زنده مراحل
  useEffect(() => {
    const handleStepEvent = (e: Event) => {
      const custom = e as CustomEvent<{ step: number }>;
      if (custom.detail && typeof custom.detail.step === 'number') {
        setCurrentStep(custom.detail.step as WizardStep);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    };
    window.addEventListener('set_wizard_step', handleStepEvent);
    return () => window.removeEventListener('set_wizard_step', handleStepEvent);
  }, []);

  const [genStatus, setGenStatus] = useState<GenerationStatus>('idle');
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [resultImage, setResultImage] = useState<string>('');
  const [isDemo, setIsDemo] = useState(false);
  // کلید انتخاب‌هایی که آخرین پیش‌نمایش با آن ساخته شد (تشخیص کهنگی نتیجه)
  const [lastGenKey, setLastGenKey] = useState<string>('');

  const [booking, setBooking] = useState<BookingFormData>({
    fullName: '',
    phoneNumber: '',
    instagramId: '',
    notes: '',
  });
  const [bookingSubmitting, setBookingSubmitting] = useState(false);
  const [bookingSuccess, setBookingSuccess] = useState(false);
  const [bookingError, setBookingError] = useState('');

  const handleFileSelection = useCallback((file: File) => {
    setUploadError('');
    setEducationalWarning('');

    if (!ACCEPTED_MIME_TYPES.includes(file.type as (typeof ACCEPTED_MIME_TYPES)[number])) {
      setUploadError('فرمت تصویر پشتیبانی نمی‌شود. لطفاً فایل JPG، PNG یا WEBP انتخاب نمایید.');
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError('حجم فایل بیش از ۵ مگابایت است. لطفاً عکس کم‌حجم‌تری انتخاب کنید.');
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    setImagePreviewUrl(objectUrl);

    const reader = new FileReader();
    reader.onload = async () => {
      const b64 = typeof reader.result === 'string' ? reader.result : '';
      setImageBase64(b64);

      try {
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image: b64 }),
        });
        const data = await res.json();
        if (data.ok && data.analysis && data.analysis.warningMessage) {
          setEducationalWarning(data.analysis.warningMessage);
        }
      } catch {
        // فلو متوقف نمی‌شود
      }

      setCurrentStep(3);
    };
    reader.readAsDataURL(file);
  }, []);

  const handleGeneratePreview = useCallback(async () => {
    if (!imageBase64) {
      setUploadError('تصویر چهره یافت نشد. لطفاً ابتدا عکس را بارگذاری نمایید.');
      setCurrentStep(2);
      return;
    }

    setGenStatus('loading');
    setStatusMessage('در حال اسکن بیومتریک چهره و اعمال پیگمنت‌های نانو...');
    setResultImage('');

    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          imageBase64,
          style: activeTechnique?.label || 'طبیعی',
          colorName: 'طبیعی چهره',
          colorHex: '#3D2817',
          preferences: {
            ...preferences,
            lipLook: selectedService === 'lips' ? selectedTechniqueKey : undefined,
            eyelinerLook: selectedService === 'eyeliner' ? selectedTechniqueKey : undefined,
          },
          prescription: selectedConsultOption?.params ?? null,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        setGenStatus('error');
        setStatusMessage(data.error || 'خطا در تولید پیش‌نمایش هوشمند.');
        return;
      }

      if (data.demo) {
        setIsDemo(true);
        const demoSvg = svgToDataUri(
          buildDemoOverlaySvg(
            selectedService === 'eyebrows' ? (selectedTechniqueKey as BrowStyleKey) : 'hairstroke',
            '#78522A',
          ),
        );
        setResultImage(demoSvg);
      } else {
        setIsDemo(false);
        setResultImage(data.resultUrl);
      }

      setGenStatus('success');
      setLastGenKey(
        JSON.stringify({
          s: selectedService,
          t: selectedTechniqueKey,
          p: preferences,
          o: selectedOptionId,
        }),
      );
      setStatusMessage('');
    } catch {
      setGenStatus('error');
      setStatusMessage('خطا در برقراری ارتباط با سرور.');
    }
  }, [imageBase64, activeTechnique, preferences, selectedService, selectedTechniqueKey, selectedConsultOption, selectedOptionId]);

  const handleBookingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBookingSubmitting(true);
    setBookingError('');

    try {
      const payload = {
        fullName: booking.fullName,
        phoneNumber: booking.phoneNumber,
        instagramId: booking.instagramId,
        selectedService,
        selectedStyle:
          selectedService === 'removal'
            ? 'ریمو تخصصی تاتو'
            : `${SERVICES_CONTENT[selectedService]?.title} (${activeTechnique?.label})`,
        notes: booking.notes,
        originalImageData: imageBase64 || undefined,
        resultImageData: resultImage || undefined,
      };

      const res = await fetch('/api/appointments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.error || 'خطا در ثبت نوبت');
      }

      setBookingSuccess(true);
    } catch (err) {
      setBookingError(err instanceof Error ? err.message : 'خطایی رخ داد.');
    } finally {
      setBookingSubmitting(false);
    }
  };

  // کلید انتخاب فعلی؛ اگر با کلید آخرین تولید فرق کند، نتیجه کهنه است
  const currentGenKey = JSON.stringify({
    s: selectedService,
    t: selectedTechniqueKey,
    p: preferences,
    o: selectedOptionId,
  });

  // کلید کش مشاوره: خدمت + استایل + اثر انگشت سلفی (طول + ۶۴ حرف آخر base64)
  const consultRequestKey = `${selectedService}|${selectedTechniqueKey}|${imageBase64.length}:${imageBase64.slice(-64)}`;
  const isStaleResult =
    genStatus === 'success' && !!resultImage && lastGenKey !== '' && lastGenKey !== currentGenKey;

  const currentServiceInfo: ServiceInfo = SERVICES_CONTENT[selectedService];

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col justify-between selection:bg-amber-500 selection:text-neutral-950 font-[family-name:var(--font-vazirmatn)]">
      {/* سربرگ لوکس VIP */}
      <header className="border-b border-neutral-800/80 bg-neutral-950/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div
            onClick={() => setCurrentStep(0)}
            className="flex items-center gap-3 cursor-pointer group"
          >
            <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-amber-600 via-amber-400 to-amber-200 flex items-center justify-center text-neutral-950 font-black text-xs shadow-lg shadow-amber-500/20 group-hover:scale-105 transition-transform border border-amber-300/40">
              AR
            </div>
            <div>
              <span className="text-sm md:text-base font-bold tracking-wide text-neutral-100 group-hover:text-amber-400 transition-colors">
                عسل رجبی
              </span>
              <span className="text-[10px] text-emerald-400 block -mt-0.5 font-medium tracking-widest">
                PMU STUDIO • MASHHAD
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 md:gap-4 text-xs">
            <span className="text-neutral-400 hidden sm:inline">مشهد مقدس</span>
          </div>
        </div>
      </header>

      {/* محتوای ویزارد */}
      <div className="flex-1 py-6 md:py-10 px-4 flex flex-col justify-center">
        {currentStep === 0 && <HeroStep onStart={() => setCurrentStep(1)} />}

        {currentStep > 0 && (
          <div className="max-w-4xl mx-auto w-full">
            <StepIndicator
              currentStep={currentStep}
              steps={WIZARD_STEPS}
              onStepClick={(s: number) => {
                if (s > 3 && isSafetyRestricted) return;
                setCurrentStep(s as WizardStep);
              }}
            />

            {currentStep === 1 && (
              <ServiceSelectStep
                selectedService={selectedService}
                planTier={planTier}
                onSelectService={(s) => setSelectedService(s)}
                onBack={() => setCurrentStep(0)}
                onNext={() => {
                  if (selectedService === 'removal') setCurrentStep(6);
                  else setCurrentStep(2);
                }}
              />
            )}

            {currentStep === 2 && (
              <UploadStep
                currentServiceInfo={currentServiceInfo}
                imagePreviewUrl={imagePreviewUrl}
                uploadError={uploadError}
                educationalWarning={educationalWarning}
                onFileSelect={handleFileSelection}
                onBack={() => setCurrentStep(1)}
                onNext={() => setCurrentStep(3)}
              />
            )}

            {currentStep === 3 && (
              <SafetyCheckStep
                currentServiceInfo={currentServiceInfo}
                imagePreviewUrl={imagePreviewUrl}
                educationalWarning={educationalWarning}
                safety={safety}
                isSafetyRestricted={isSafetyRestricted}
                onSafetyChange={(newSafety) => setSafety(newSafety)}
                onBack={() => setCurrentStep(2)}
                onNext={() => setCurrentStep(4)}
              />
            )}

            {currentStep === 4 && (
              <ConsultStep
                imageBase64={imageBase64}
                imagePreviewUrl={imagePreviewUrl}
                selectedService={selectedService}
                serviceTitle={currentServiceInfo.title}
                initialStyleKey={selectedTechniqueKey}
                initialStyleLabel={activeTechnique?.label ?? selectedTechniqueKey}
                cacheKey={consultRequestKey}
                cachedData={consultCacheKey === consultRequestKey ? consultData : null}
                selectedOptionId={selectedOptionId}
                onData={(key, data) => {
                  setConsultCacheKey(key);
                  setConsultData(data);
                }}
                onSelectOption={(id) => setSelectedOptionId(id)}
                onBack={() => setCurrentStep(3)}
                onNext={() => setCurrentStep(5)}
              />
            )}

            {currentStep === 5 && (
              <PreferencesStep
                currentServiceInfo={currentServiceInfo}
                availableTechniques={availableTechniques}
                selectedTechniqueKey={selectedTechniqueKey}
                preferences={preferences}
                onSelectTechnique={(key) => setSelectedTechniqueKey(key)}
                onPreferencesChange={(p) => setPreferences(p)}
                onBack={() => setCurrentStep(4)}
                onNext={() => {
                  // اگر انتخاب عوض شده، نتیجه قبلی دور ریخته می‌شود تا تازه ساخته شود
                  if (isStaleResult) {
                    setResultImage('');
                    setGenStatus('idle');
                    setStatusMessage('انتخاب شما تغییر کرد — پیش‌نمایش جدید بسازید ✨');
                  }
                  setCurrentStep(6);
                }}
              />
            )}

            {currentStep === 6 && (
              <PreviewStep
                selectedService={selectedService}
                currentServiceInfo={currentServiceInfo}
                planTier={planTier}
                activeTechnique={activeTechnique}
                genStatus={genStatus}
                statusMessage={statusMessage}
                resultImage={resultImage}
                imagePreviewUrl={imagePreviewUrl}
                isDemo={isDemo}
                isStale={isStaleResult}
                prescriptionOption={selectedConsultOption}
                onGenerate={handleGeneratePreview}
                onBack={() => setCurrentStep(5)}
                onNext={() => setCurrentStep(7)}
              />
            )}

            {currentStep === 7 && (
              <BookingStep
                currentServiceInfo={currentServiceInfo}
                planTier={planTier}
                activeTechnique={activeTechnique}
                booking={booking}
                bookingSuccess={bookingSuccess}
                bookingSubmitting={bookingSubmitting}
                bookingError={bookingError}
                onBookingChange={(b) => setBooking(b)}
                onSubmit={handleBookingSubmit}
                onBack={() => setCurrentStep(6)}
                onReset={() => {
                  setBookingSuccess(false);
                  setCurrentStep(0);
                }}
              />
            )}
          </div>
        )}
      </div>

      <footer className="border-t border-neutral-900 bg-neutral-950/90 py-5 text-center text-xs text-neutral-500">
        <div className="max-w-4xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2.5">
          <p>© {new Date().getFullYear()} {tenantName}</p>
          <div className="flex items-center gap-3 text-[11px] text-neutral-400">
            <span>طراحی اختصاصی با هوش مصنوعی و بینایی ماشین</span>
          </div>
        </div>
      </footer>

      {/* چت‌بات هوشمند مشاور با Feature Gate بر اساس پلن */}
      <AiChatWidget planTier={planTier} customAssistantName={customAssistantName} />
    </main>
  );
}
