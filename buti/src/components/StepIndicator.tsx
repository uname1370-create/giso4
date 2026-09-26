import React from 'react';

export interface StepIndicatorProps {
  currentStep: number; // 0 to steps.length - 1
  steps: { id: number; title: string }[];
  onStepClick?: (step: number) => void;
}

export const StepIndicator: React.FC<StepIndicatorProps> = ({ currentStep, steps, onStepClick }) => {
  if (currentStep === 0) return null;

  const currentStepObj = steps.find((s) => s.id === currentStep);

  return (
    <div className="w-full max-w-3xl mx-auto mb-8 px-4">
      {/* تیتر مرحله در موبایل */}
      <div className="sm:hidden text-center mb-3">
        <span className="text-[11px] text-amber-400 font-bold bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20">
          مرحله {currentStep} از {steps.length - 1}: {currentStepObj?.title}
        </span>
      </div>

      <div className="relative flex items-center justify-between">
        {/* نوار پس‌زمینه */}
        <div className="absolute top-1/2 right-0 left-0 -translate-y-1/2 h-0.5 bg-neutral-800 -z-0" />
        {/* نوار پر شده */}
        <div
          className="absolute top-1/2 right-0 -translate-y-1/2 h-0.5 bg-gradient-to-l from-amber-400 to-amber-600 transition-all duration-500 -z-0"
          style={{
            width: `${Math.min(100, Math.max(0, ((currentStep - 1) / (steps.length - 2)) * 100))}%`,
          }}
        />

        {steps.slice(1).map((s) => {
          const isPassed = s.id < currentStep;
          const isCurrent = s.id === currentStep;

          return (
            <div
              key={s.id}
              onClick={() => {
                if (isPassed && onStepClick) {
                  onStepClick(s.id);
                }
              }}
              className={`relative z-10 flex flex-col items-center group ${
                isPassed ? 'cursor-pointer' : 'cursor-default'
              }`}
            >
              <div
                className={`w-7 h-7 sm:w-9 sm:h-9 rounded-full flex items-center justify-center text-[11px] sm:text-xs font-bold transition-all duration-300 border ${
                  isCurrent
                    ? 'bg-amber-500 text-neutral-950 border-amber-300 shadow-[0_0_15px_rgba(245,158,11,0.5)] scale-110'
                    : isPassed
                    ? 'bg-neutral-900 text-amber-400 border-amber-500/60'
                    : 'bg-neutral-900 text-neutral-500 border-neutral-800'
                }`}
              >
                {isPassed ? (
                  <svg className="w-3.5 h-3.5 sm:w-4 sm:h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  s.id
                )}
              </div>
              {/* عناوین در موبایل پنهان هستند تا فضا فشرده نشود */}
              <span
                className={`hidden sm:block text-[11px] mt-2 whitespace-nowrap transition-colors duration-300 ${
                  isCurrent ? 'text-amber-300 font-bold' : isPassed ? 'text-neutral-300' : 'text-neutral-500'
                }`}
              >
                {s.title}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
