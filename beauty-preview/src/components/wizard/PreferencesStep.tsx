import React from 'react';
import { type ServiceInfo } from '@/services-content';
import { type TechniqueStyleOption } from '@/techniques';

interface ClientPreferences {
  dailyMakeup: 'natural' | 'soft' | 'bold';
  browShape: 'natural' | 'defined';
  density: 'fluffy' | 'dense';
}

interface PreferencesStepProps {
  currentServiceInfo: ServiceInfo;
  availableTechniques: TechniqueStyleOption[];
  selectedTechniqueKey: string;
  preferences: ClientPreferences;
  onSelectTechnique: (key: string) => void;
  onPreferencesChange: (preferences: ClientPreferences) => void;
  onBack: () => void;
  onNext: () => void;
}

export const PreferencesStep: React.FC<PreferencesStepProps> = ({
  currentServiceInfo,
  availableTechniques,
  selectedTechniqueKey,
  preferences,
  onSelectTechnique,
  onPreferencesChange,
  onBack,
  onNext,
}) => {
  return (
    <div className="bg-neutral-900/70 border border-neutral-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl animate-fadeIn">
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold text-neutral-100 mb-1">
          انتخاب تکنیک و مدل: {currentServiceInfo?.title}
        </h2>
        <p className="text-xs text-neutral-400">
          نمونه کارهای واقعی سالن را مشاهده و تکنیک مد نظرتان را انتخاب کنید
        </p>
      </div>

      {/* کارت‌های تکنیک‌های پویا متناسب با خدمت */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        {availableTechniques.map((technique) => {
          const isSelected = selectedTechniqueKey === technique.key;
          return (
            <div
              key={technique.key}
              onClick={() => onSelectTechnique(technique.key)}
              className={`p-4 rounded-2xl border cursor-pointer transition-all ${
                isSelected
                  ? 'bg-amber-500/15 border-amber-400 shadow-md shadow-amber-500/10'
                  : 'bg-neutral-950 border-neutral-800/80 hover:border-neutral-700'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-neutral-100">{technique.label}</span>
                <span className="text-[10px] text-amber-400 font-mono">{technique.labelEn}</span>
              </div>

              {/* تصویر نمونه‌کار آپلود شده یا پیش‌فرض */}
              <div className="relative aspect-[16/9] rounded-xl overflow-hidden border border-neutral-800 bg-neutral-900 mb-3">
                <img
                  src={technique.sampleImage}
                  alt={technique.label}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                />
              </div>

              <p className="text-[11px] text-neutral-400 leading-relaxed">{technique.hint}</p>
            </div>
          );
        })}
      </div>

      {/* سوالات تکمیلی سبک آرایش روزانه */}
      <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 mb-6">
        <label className="text-xs font-bold text-neutral-200 block mb-2">
          سبک آرایش روزانه شما چطور است؟
        </label>
        <div className="grid grid-cols-3 gap-2">
          {(['natural', 'soft', 'bold'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => onPreferencesChange({ ...preferences, dailyMakeup: m })}
              className={`p-2.5 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                preferences.dailyMakeup === m
                  ? 'bg-amber-500/20 border-amber-400 text-amber-300'
                  : 'bg-neutral-900 border-neutral-800 text-neutral-400'
              }`}
            >
              {m === 'natural' ? 'نچرال' : m === 'soft' ? 'ملایم' : 'پررنگ'}
            </button>
          ))}
        </div>
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
          className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold cursor-pointer text-center"
        >
          تأیید مدل و ساخت پیش‌نمایش 🎨
        </button>
      </div>
    </div>
  );
};
