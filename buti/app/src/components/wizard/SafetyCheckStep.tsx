import React from 'react';
import Image from 'next/image';
import { type ServiceInfo } from '@/services-content';

interface MedicalSafetyCheck {
  pregnantOrNursing: boolean;
  skinAllergyOrKeloid: boolean;
  specialMedication: boolean;
}

interface SafetyCheckStepProps {
  currentServiceInfo: ServiceInfo;
  imagePreviewUrl: string;
  educationalWarning: string;
  safety: MedicalSafetyCheck;
  isSafetyRestricted: boolean;
  onSafetyChange: (safety: MedicalSafetyCheck) => void;
  onBack: () => void;
  onNext: () => void;
}

export const SafetyCheckStep: React.FC<SafetyCheckStepProps> = ({
  currentServiceInfo,
  imagePreviewUrl,
  educationalWarning,
  safety,
  isSafetyRestricted,
  onSafetyChange,
  onBack,
  onNext,
}) => {
  return (
    <div className="bg-neutral-900/70 border border-neutral-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl animate-fadeIn">
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold text-neutral-100 mb-1">
          بررسی الزامات ایمنی و سلامت
        </h2>
        <p className="text-xs text-neutral-400">
          سلامتی شما برای مجموعه عسل رجبی اولویت اول و غیرقابل‌مذاکره است.
        </p>
      </div>

      <div className="flex items-center gap-4 mb-6 p-3.5 rounded-xl bg-neutral-950/70 border border-neutral-800">
        <div className="relative w-16 h-16 rounded-lg overflow-hidden border border-neutral-700 shrink-0">
          {imagePreviewUrl && (
            <Image src={imagePreviewUrl} alt="عکس شما" fill className="object-cover" unoptimized />
          )}
        </div>
        <div className="text-xs text-neutral-300">
          <p className="font-semibold text-neutral-200">عکس چهره دریافت شد.</p>
          {educationalWarning ? (
            <p className="text-amber-400/90 text-[11px] mt-0.5">نکته نوری: {educationalWarning}</p>
          ) : (
            <p className="text-emerald-400 text-[11px] mt-0.5">کیفیت و وضوح تصویر بسیار مطلوب است ✓</p>
          )}
        </div>
      </div>

      <div className="p-5 rounded-xl bg-neutral-950 border border-neutral-800 mb-6 space-y-3.5">
        <h3 className="text-xs font-bold text-amber-300 mb-2">
          موارد منع موقت برای {currentServiceInfo?.title}:
        </h3>

        <label className="flex items-start gap-3 p-3 rounded-lg bg-neutral-900/60 border border-neutral-800/80 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={safety.pregnantOrNursing}
            onChange={(e) =>
              onSafetyChange({ ...safety, pregnantOrNursing: e.target.checked })
            }
            className="w-4 h-4 mt-0.5 rounded border-neutral-700 bg-neutral-950 text-amber-500 focus:ring-amber-500 cursor-pointer"
          />
          <span className="text-xs text-neutral-200">
            ۱. در دوران بارداری یا شیردهی قرار دارم.
          </span>
        </label>

        <label className="flex items-start gap-3 p-3 rounded-lg bg-neutral-900/60 border border-neutral-800/80 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={safety.skinAllergyOrKeloid}
            onChange={(e) =>
              onSafetyChange({ ...safety, skinAllergyOrKeloid: e.target.checked })
            }
            className="w-4 h-4 mt-0.5 rounded border-neutral-700 bg-neutral-950 text-amber-500 focus:ring-amber-500 cursor-pointer"
          />
          <span className="text-xs text-neutral-200">
            ۲. سابقه حساسیت پوستی شدید، اگزمای موضعی یا تشکیل کلوئید (گوشت اضافه) دارم.
          </span>
        </label>

        <label className="flex items-start gap-3 p-3 rounded-lg bg-neutral-900/60 border border-neutral-800/80 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={safety.specialMedication}
            onChange={(e) =>
              onSafetyChange({ ...safety, specialMedication: e.target.checked })
            }
            className="w-4 h-4 mt-0.5 rounded border-neutral-700 bg-neutral-950 text-amber-500 focus:ring-amber-500 cursor-pointer"
          />
          <span className="text-xs text-neutral-200">
            ۳. داروی راکوتان (در ۶ ماه اخیر) یا داروی ضدانعقاد خون مصرف می‌کنم.
          </span>
        </label>

        {isSafetyRestricted && (
          <div className="mt-4 p-3.5 rounded-xl bg-red-950/60 border border-red-700/80 text-red-200 text-xs leading-relaxed flex items-start gap-2.5">
            <span className="text-red-400 font-bold text-sm shrink-0">⚠️</span>
            <div>
              <strong>محدودیت موقت پزشکی:</strong> لطفاً پیش از انجام کار با پزشک خود مشورت
              کنید و جهت راهنمایی با ما تماس بگیرید.
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-col-reverse sm:flex-row justify-between items-stretch sm:items-center gap-3">
        <button
          onClick={onBack}
          className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-neutral-700 text-neutral-400 hover:text-neutral-200 text-xs cursor-pointer text-center"
        >
          تغییر عکس
        </button>
        <button
          disabled={isSafetyRestricted}
          onClick={onNext}
          className={`w-full sm:w-auto px-6 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer text-center ${
            isSafetyRestricted
              ? 'bg-neutral-800 text-neutral-500 cursor-not-allowed opacity-50'
              : 'bg-amber-500 hover:bg-amber-400 text-neutral-950 shadow-md shadow-amber-500/20'
          }`}
        >
          تأیید سلامت و ادامه به انتخاب مدل
        </button>
      </div>
    </div>
  );
};
