import React, { useState } from 'react';
import { SERVICES_CONTENT, type ServiceInfo } from '@/services-content';
import { type PlanTier } from '@/plan-config';

type ServiceType = 'eyebrows' | 'lips' | 'eyeliner' | 'removal';

interface ServiceSelectStepProps {
  selectedService: ServiceType;
  planTier?: PlanTier;
  onSelectService: (service: ServiceType) => void;
  onBack: () => void;
  onNext: () => void;
}

export const ServiceSelectStep: React.FC<ServiceSelectStepProps> = ({
  selectedService,
  planTier = 'gold',
  onSelectService,
  onBack,
  onNext,
}) => {
  const currentServiceInfo: ServiceInfo = SERVICES_CONTENT[selectedService];
  const [lockedNotice, setLockedNotice] = useState<string>('');

  const services = [
    {
      id: 'eyebrows' as const,
      title: 'میکروبلیدینگ و نانوبروز ابرو',
      desc: 'طراحی مویی و کرکی، شیدینگ پودری و فیبروز متقارن',
      badge: 'پرطرفدارترین',
      icon: '✨',
      bgImage: '/services/eyebrows.jpg',
      requiredTier: 'bronze' as PlanTier,
    },
    {
      id: 'lips' as const,
      title: 'شیدینگ و کانتورینگ لب (لیپ بلاش)',
      desc: 'شادابی طبیعی، رفع تیرگی و حجم‌دهی بصری بدون کادر خطی',
      badge: 'تکنیک روز',
      icon: '💋',
      bgImage: '/services/lips.jpg',
      requiredTier: 'silver' as PlanTier,
    },
    {
      id: 'eyeliner' as const,
      title: 'خط چشم دائم و بن‌مژه ظریف',
      desc: 'تیره‌سازی عمق نگاه و خط مژه با پیگمنت کربن مشکی خالص',
      badge: 'ماندگاری ۳ تا ۵ سال',
      icon: '👁️',
      bgImage: '/services/eyeliner.jpg',
      requiredTier: 'silver' as PlanTier,
    },
    {
      id: 'removal' as const,
      title: 'ریمو تخصصی تاتوی قدیمی',
      desc: 'خروج ایمن پیگمنت‌های قرمز یا اکسید شده بدون آسیب به پوست',
      badge: 'مشاوره حضوری',
      icon: '🫧',
      bgImage: '/services/removal.jpg',
      requiredTier: 'gold' as PlanTier,
    },
  ];

  const isServiceAllowed = (serviceId: ServiceType) => {
    if (planTier === 'gold') return true;
    if (planTier === 'silver') return serviceId !== 'removal';
    // bronze
    return serviceId === 'eyebrows';
  };

  const handleCardClick = (serviceId: ServiceType) => {
    if (!isServiceAllowed(serviceId)) {
      if (serviceId === 'removal') {
        setLockedNotice('خدمت ریمو تخصصی تاتو ویژه پلن طلایی (VIP) است. جهت ارتقا با پشتیبانی تماس بگیرید.');
      } else {
        setLockedNotice(`خدمت ${SERVICES_CONTENT[serviceId]?.title} ویژه پلن‌های نقره‌ای و طلایی است.`);
      }
      return;
    }
    setLockedNotice('');
    onSelectService(serviceId);
  };

  return (
    <div className="bg-neutral-900/70 border border-neutral-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl animate-fadeIn">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-black text-neutral-100 mb-2">
          خدمت تخصصی مورد نظرتان را انتخاب کنید
        </h2>
        <p className="text-xs text-neutral-400">
          ارائه خدمات تخصصی PMU با ضمانت سلامت و زیبایی
        </p>
      </div>

      {lockedNotice && (
        <div className="mb-6 p-3.5 rounded-xl bg-amber-950/60 border border-amber-500/50 text-amber-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>🔒</span>
            <span>{lockedNotice}</span>
          </div>
          <button
            onClick={() => setLockedNotice('')}
            className="text-neutral-400 hover:text-neutral-200 text-xs cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
        {services.map((service) => {
          const allowed = isServiceAllowed(service.id);
          const isSelected = selectedService === service.id;

          return (
            <div
              key={service.id}
              onClick={() => handleCardClick(service.id)}
              className={`p-5 rounded-2xl border cursor-pointer transition-all relative overflow-hidden ${
                isSelected
                  ? 'bg-amber-500/15 border-amber-400 shadow-lg shadow-amber-500/10 scale-[1.01]'
                  : allowed
                  ? 'bg-neutral-900/60 border-neutral-800 hover:border-neutral-700'
                  : 'bg-neutral-950/80 border-neutral-800/60 opacity-60 hover:opacity-80'
              }`}
            >
              {/* بکگراند تصویری تمام‌کارت + گرادیان خوانایی متن */}
              <img
                src={service.bgImage}
                alt=""
                aria-hidden
                className="absolute inset-0 w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-neutral-950 via-neutral-950/70 to-neutral-950/20 pointer-events-none" />

              {!allowed && (
                <div className="absolute top-2.5 start-2.5 z-10 px-2 py-0.5 rounded-full bg-neutral-950/90 border border-amber-500/40 text-[9px] sm:text-[10px] text-amber-300 font-bold flex items-center gap-1 shadow-md">
                  <span>🔒</span>
                  <span>
                    {service.requiredTier === 'gold' ? 'ویژه پلن طلایی' : 'ویژه نقره‌ای/طلایی'}
                  </span>
                </div>
              )}

              <div className="relative z-[5] flex flex-col justify-end min-h-[170px]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-2xl">{service.icon}</span>
                {allowed && (
                  <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-medium">
                    {service.badge}
                  </span>
                )}
              </div>
              <h3 className="text-sm sm:text-base font-bold text-neutral-100 mb-1">{service.title}</h3>
              <p className="text-xs text-neutral-400 leading-relaxed mb-3">{service.desc}</p>
              <div className="text-[10px] sm:text-[11px] text-emerald-400 flex flex-wrap items-center gap-1">
                <span>مدت زمان: {SERVICES_CONTENT[service.id]?.duration}</span>
                <span className="text-neutral-600">•</span>
                <span>ماندگاری: {SERVICES_CONTENT[service.id]?.durability}</span>
              </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex flex-col-reverse sm:flex-row justify-between items-stretch sm:items-center gap-3">
        <button
          onClick={onBack}
          className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-neutral-800 text-neutral-400 text-xs hover:text-neutral-200 cursor-pointer text-center"
        >
          بازگشت به خانه
        </button>
        <button
          onClick={onNext}
          className="w-full sm:w-auto px-8 py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs shadow-lg shadow-amber-500/25 cursor-pointer text-center"
        >
          ادامه با {currentServiceInfo?.title} ←
        </button>
      </div>
    </div>
  );
};
