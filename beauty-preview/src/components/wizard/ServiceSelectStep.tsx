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
              className={`rounded-2xl border cursor-pointer transition-all relative overflow-hidden flex flex-col sm:flex-row ${
                isSelected
                  ? 'bg-neutral-900 border-amber-400 shadow-lg shadow-amber-500/10 scale-[1.01]'
                  : allowed
                  ? 'bg-neutral-900/60 border-neutral-800 hover:border-neutral-600'
                  : 'bg-neutral-950/80 border-neutral-800/60 opacity-70 hover:opacity-90'
              }`}
            >
              {/* متن خدمت (سمت راست) */}
              <div className="order-2 sm:order-1 flex-1 p-5 flex flex-col justify-center gap-2 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  {allowed ? (
                    <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-medium">
                      {service.badge}
                    </span>
                  ) : (
                    <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-neutral-800 text-neutral-400 font-medium">
                      🔒 {service.requiredTier === 'gold' ? 'ویژه پلن طلایی' : 'ویژه نقره‌ای/طلایی'}
                    </span>
                  )}
                  {isSelected && (
                    <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold">
                      ✓ انتخاب شد
                    </span>
                  )}
                </div>
                <h3 className="text-sm sm:text-base font-bold text-neutral-100">{service.title}</h3>
                <p className="text-xs text-neutral-400 leading-relaxed">{service.desc}</p>
                <div className="text-[10px] sm:text-[11px] text-emerald-400 flex flex-wrap items-center gap-1 pt-1">
                  <span>مدت زمان: {SERVICES_CONTENT[service.id]?.duration}</span>
                  <span className="text-neutral-600">•</span>
                  <span>ماندگاری: {SERVICES_CONTENT[service.id]?.durability}</span>
                </div>
              </div>

              {/* عکس خدمت (سمت چپ) */}
              <div className="order-1 sm:order-2 relative sm:w-40 md:w-44 shrink-0 h-36 sm:h-auto sm:min-h-[196px]">
                <img
                  src={service.bgImage}
                  alt={service.title}
                  className={`absolute inset-0 w-full h-full object-cover ${
                    allowed ? '' : 'grayscale'
                  }`}
                  onError={(e) => {
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-neutral-900/70 via-transparent to-transparent sm:bg-gradient-to-r sm:from-transparent sm:via-transparent sm:to-neutral-900 pointer-events-none" />
                {isSelected && (
                  <div className="absolute inset-0 ring-1 ring-inset ring-amber-400/60 pointer-events-none" />
                )}
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
