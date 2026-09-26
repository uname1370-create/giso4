import React, { useRef } from 'react';
import { type ServiceInfo } from '@/services-content';
import { type TechniqueStyleOption } from '@/techniques';
import { type PlanTier } from '@/plan-config';
import { buildWhatsAppLink } from '@/options';

interface BookingFormData {
  fullName: string;
  phoneNumber: string;
  instagramId: string;
  notes: string;
}

interface BookingStepProps {
  currentServiceInfo: ServiceInfo;
  planTier?: PlanTier;
  activeTechnique?: TechniqueStyleOption;
  booking: BookingFormData;
  bookingSuccess: boolean;
  bookingSubmitting: boolean;
  bookingError: string;
  onBookingChange: (booking: BookingFormData) => void;
  onSubmit: (e: React.FormEvent) => void;
  onBack: () => void;
  onReset: () => void;
  safety?: {
    pregnantOrNursing: boolean;
    skinAllergyOrKeloid: boolean;
    specialMedication: boolean;
  };
  isSafetyRestricted?: boolean;
  onSafetyChange?: (safety: {
    pregnantOrNursing: boolean;
    skinAllergyOrKeloid: boolean;
    specialMedication: boolean;
  }) => void;
}

export const BookingStep: React.FC<BookingStepProps> = ({
  currentServiceInfo,
  planTier = 'gold',
  activeTechnique,
  booking,
  bookingSuccess,
  bookingSubmitting,
  bookingError,
  onBookingChange,
  onSubmit,
  onBack,
  onReset,
  safety,
  isSafetyRestricted = false,
  onSafetyChange,
}) => {
  const cardRef = useRef<HTMLDivElement>(null);
  const isGold = planTier === 'gold';

  const trackingCode = `VIP-${Math.floor(100000 + Math.random() * 900000)}`;
  const reservationDate = new Date().toLocaleDateString('fa-IR');

  const handleDownloadCard = () => {
    window.print();
  };

  return (
    <div className="bg-neutral-900/70 border border-neutral-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl animate-fadeIn relative overflow-hidden">
      {/* انیمیشن جرقه‌های طلایی فقط در پلن طلایی */}
      {bookingSuccess && isGold && (
        <div className="absolute inset-0 pointer-events-none overflow-hidden -z-0">
          <div className="absolute top-0 left-1/4 w-2 h-2 rounded-full bg-amber-400 animate-ping opacity-75" />
          <div className="absolute top-10 right-1/3 w-3 h-3 rounded-full bg-amber-300 animate-pulse opacity-60" />
          <div className="absolute top-20 left-10 w-2 h-2 rounded-full bg-amber-500 animate-bounce opacity-80" />
          <div className="absolute bottom-10 right-10 w-2.5 h-2.5 rounded-full bg-amber-200 animate-ping opacity-70" />
          <div className="absolute top-1/2 right-1/4 w-2 h-2 rounded-full bg-amber-400 animate-pulse opacity-90" />
        </div>
      )}

      <div className="text-center mb-6 relative z-10">
        <h2 className="text-xl font-bold text-neutral-100 mb-1">
          {isGold ? 'رزرو نوبت VIP و دریافت کارت اختصاصی' : `ثبت نوبت مشاوره ${currentServiceInfo?.title}`}
        </h2>
        <p className="text-xs text-neutral-400">
          اطلاعات شما نزد سالن کاملاً محرمانه محفوظ خواهد بود.
        </p>
      </div>

      {bookingSuccess ? (
        <div className="max-w-md mx-auto space-y-6 relative z-10">
          {/* کارت عضویت دیجیتال VIP لوکس در پلن طلایی، یا رسید متنی شیک در برنزی و نقره‌ای */}
          {isGold ? (
            <div
              ref={cardRef}
              className="p-6 rounded-2xl bg-gradient-to-br from-neutral-950 via-neutral-900 to-[#1c160c] border-2 border-amber-500/60 shadow-2xl shadow-amber-500/20 text-right relative overflow-hidden"
            >
              {/* واتر مارک طلایی برند */}
              <div className="absolute -right-6 -bottom-6 w-32 h-32 rounded-full border border-amber-500/10 -z-0" />

              <div className="flex items-center justify-between border-b border-amber-500/30 pb-3 mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-amber-500 text-neutral-950 font-black flex items-center justify-center text-xs">
                    VIP
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-neutral-100">کارت عضویت دیجیتال VIP</h4>
                    <p className="text-[9px] text-amber-400">استودیو تخصصی PMU</p>
                  </div>
                </div>
                <span className="text-[10px] px-2.5 py-1 rounded-full bg-amber-500/20 border border-amber-400/40 text-amber-300 font-mono font-bold">
                  {trackingCode}
                </span>
              </div>

              <div className="space-y-2.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-neutral-400">نام مراجع محترم:</span>
                  <strong className="text-neutral-100">{booking.fullName}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-400">خدمت و سبک:</span>
                  <span className="text-amber-300 font-medium">
                    {currentServiceInfo?.title} ({activeTechnique?.label || 'طبیعی'})
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-400">تاریخ ثبت درخواست:</span>
                  <span className="text-neutral-300 font-mono">{reservationDate}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-400">شماره هماهنگی:</span>
                  <span className="text-neutral-300 font-mono" dir="ltr">{booking.phoneNumber}</span>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-neutral-800 text-center">
                <p className="text-[10px] text-emerald-400 font-medium">
                  ✓ پرونده شما در اولویت VIP بررسی و تماس مشاوران قرار گرفت.
                </p>
              </div>
            </div>
          ) : (
            <div className="p-5 rounded-xl bg-neutral-950 border border-emerald-500/40 text-right space-y-3">
              <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs">
                <span>✓</span>
                <span>درخواست نوبت شما با موفقیت ثبت شد</span>
              </div>
              <div className="text-xs text-neutral-300 space-y-1.5 border-t border-neutral-800 pt-2.5">
                <p>مراجع محترم: <strong>{booking.fullName}</strong></p>
                <p>خدمت انتخابی: <span className="text-amber-300">{currentServiceInfo?.title}</span></p>
                <p>کد پیگیری: <span className="font-mono text-amber-400">{trackingCode}</span></p>
              </div>
            </div>
          )}

          {/* دکمه‌های اقدام بعد از رزرو */}
          <div className="flex flex-col sm:flex-row justify-center items-stretch sm:items-center gap-2.5">
            {isGold && (
              <button
                onClick={handleDownloadCard}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-neutral-900 border border-amber-500/40 hover:bg-neutral-800 text-amber-300 font-bold text-xs transition-colors flex items-center justify-center gap-1.5 cursor-pointer text-center"
              >
                <span>دانلود یا چاپ کارت VIP 📄</span>
              </button>
            )}
            <a
              href={buildWhatsAppLink(currentServiceInfo?.title, activeTechnique?.label || 'طبیعی')}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-neutral-950 font-bold text-xs transition-colors flex items-center justify-center gap-1.5 text-center"
            >
              <span>تایید سریع در واتساپ 💬</span>
            </a>
            <button
              onClick={onReset}
              className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-neutral-700 text-neutral-400 text-xs cursor-pointer hover:text-neutral-200 text-center"
            >
              شروع مجدد
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4 max-w-md mx-auto relative z-10">
          {bookingError && (
            <div className="p-3 rounded-xl bg-red-950/60 border border-red-800 text-red-200 text-xs">
              {bookingError}
            </div>
          )}

          <div>
            <label className="text-xs text-neutral-300 block mb-1">نام و نام خانوادگی:</label>
            <input
              type="text"
              required
              placeholder="مثال: سارا محمدی"
              value={booking.fullName}
              onChange={(e) => onBookingChange({ ...booking, fullName: e.target.value })}
              className="w-full px-3.5 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-amber-400"
            />
          </div>

          <div>
            <label className="text-xs text-neutral-300 block mb-1">شماره تماس (موبایل):</label>
            <input
              type="tel"
              required
              dir="ltr"
              placeholder="0915..."
              value={booking.phoneNumber}
              onChange={(e) => onBookingChange({ ...booking, phoneNumber: e.target.value })}
              className="w-full px-3.5 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-amber-400 text-right"
            />
          </div>

          <div>
            <label className="text-xs text-neutral-300 block mb-1">آیدی اینستاگرام (اختیاری):</label>
            <input
              type="text"
              dir="ltr"
              placeholder="@username"
              value={booking.instagramId}
              onChange={(e) => onBookingChange({ ...booking, instagramId: e.target.value })}
              className="w-full px-3.5 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-amber-400 text-right"
            />
          </div>

          <div>
            <label className="text-xs text-neutral-300 block mb-1">توضیحات تکمیلی (اختیاری):</label>
            <textarea
              rows={2}
              placeholder="نکته یا سوال خاصی دارید بنویسید..."
              value={booking.notes}
              onChange={(e) => onBookingChange({ ...booking, notes: e.target.value })}
              className="w-full px-3.5 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-amber-400"
            />
          </div>

          {safety && onSafetyChange && (
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2.5">
              <p className="text-xs font-bold text-neutral-200">تأیید سلامت (قبل از رزرو):</p>
              {(
                [
                  ['pregnantOrNursing', '۱. در دوران بارداری یا شیردهی قرار دارم.'],
                  ['skinAllergyOrKeloid', '۲. سابقه حساسیت پوستی شدید، اگزمای موضعی یا تشکیل کلوئید (گوشت اضافه) دارم.'],
                  ['specialMedication', '۳. داروی راکوتان (در ۶ ماه اخیر) یا داروی ضدانعقاد خون مصرف می‌کنم.'],
                ] as const
              ).map(([field, label]) => (
                <label key={field} className="flex items-start gap-2.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={safety[field]}
                    onChange={(e) => onSafetyChange({ ...safety, [field]: e.target.checked })}
                    className="mt-0.5 w-4 h-4 rounded accent-amber-500"
                  />
                  <span className="text-[11px] text-neutral-300 leading-relaxed">{label}</span>
                </label>
              ))}
              {isSafetyRestricted && (
                <p className="text-[11px] text-red-300 leading-relaxed bg-red-950/50 border border-red-500/40 rounded-lg p-2.5">
                  ⚠️ با توجه به شرایط خاص شما، اجرای PMU نیاز به ویزیت حضوری داره — رزرو شما به‌صورت مشاوره حضوری ثبت می‌شه.
                </p>
              )}
            </div>
          )}

          <p className="text-[11px] text-neutral-500 text-center leading-relaxed">
            🔒 اطلاعات و عکس شما به صورت محرمانه نزد مرکز عسل رجبی محفوظ است.
          </p>

          <div className="pt-2 flex flex-col-reverse sm:flex-row justify-between items-stretch sm:items-center gap-3">
            <button
              type="button"
              onClick={onBack}
              className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-neutral-700 text-neutral-400 hover:text-neutral-200 text-xs cursor-pointer text-center"
            >
              مرحله قبل
            </button>
            <button
              type="submit"
              disabled={bookingSubmitting}
              className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 text-neutral-950 text-xs font-bold shadow-md shadow-amber-500/20 disabled:opacity-50 cursor-pointer text-center"
            >
              {bookingSubmitting
                ? 'در حال ثبت...'
                : isSafetyRestricted
                  ? 'رزرو مشاوره حضوری 🩺'
                  : 'ثبت درخواست و دریافت کارت VIP ✨'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
