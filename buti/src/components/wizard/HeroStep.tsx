import React from 'react';
import Image from 'next/image';
import { HERO_IMAGE_URL, HERO_SUBTITLE, HERO_TITLE } from '@/options';

interface HeroStepProps {
  onStart: () => void;
}

export const HeroStep: React.FC<HeroStepProps> = ({ onStart }) => {
  return (
    <section className="max-w-4xl mx-auto w-full text-center py-6 md:py-12 animate-fadeIn">
      <div className="relative inline-block mb-6 md:mb-8">
        <div className="absolute -inset-2 rounded-full bg-gradient-to-r from-amber-500/30 via-emerald-500/20 to-amber-600/30 blur-2xl animate-pulse" />
        <div className="relative w-44 h-44 md:w-56 md:h-56 mx-auto rounded-full overflow-hidden border-2 border-amber-500/50 shadow-2xl bg-neutral-900">
          <Image
            src={HERO_IMAGE_URL}
            alt={HERO_TITLE}
            fill
            sizes="224px"
            className="object-cover"
            priority
            unoptimized
          />
        </div>
      </div>

      <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-emerald-950/70 border border-emerald-500/30 text-emerald-300 text-xs mb-4">
        <span className="w-2 h-2 rounded-full bg-emerald-400" />
        <span>پلتفرم VIP و هوشمند شبیه‌سازی خدمات آرایش دائم مشهد</span>
      </div>

      <h1 className="text-3xl md:text-5xl font-black tracking-tight mb-3 text-neutral-100">
        استودیو تخصصی {HERO_TITLE}
      </h1>

      <p className="text-xl md:text-2xl text-amber-300 font-light mb-6 tracking-wide italic">
        « {HERO_SUBTITLE} ✨ »
      </p>

      <p className="max-w-xl mx-auto text-neutral-400 text-xs md:text-sm leading-relaxed mb-8">
        پیش از هرگونه اقدام، هارمونی فرم‌ها را با نسبت‌های چهره، استخوان‌بندی و سلیقه شخصی‌تان
        با موتور هوش مصنوعی نسل جدید به طور دقیق شبیه‌سازی کنید.
      </p>

      <div className="flex justify-center">
        <button
          onClick={onStart}
          className="w-full sm:w-auto px-9 py-4 rounded-xl bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 hover:from-amber-400 hover:to-amber-300 text-neutral-950 font-extrabold text-sm md:text-base shadow-xl shadow-amber-500/25 hover:shadow-amber-500/40 hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 flex items-center justify-center gap-2 cursor-pointer border border-amber-300/50"
        >
          <span>🪄 ورود به انتخاب خدمت و مشاوره هوشمند</span>
          <svg
            className="w-5 h-5 -rotate-180"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </section>
  );
};
