import React, { useRef, useState } from 'react';
import { ACCEPT_ATTRIBUTE } from '@/options';
import { type ServiceInfo } from '@/services-content';

interface UploadStepProps {
  currentServiceInfo: ServiceInfo;
  imagePreviewUrl: string;
  uploadError: string;
  educationalWarning: string;
  onFileSelect: (file: File) => void;
  onBack: () => void;
  onNext: () => void;
}

export const UploadStep: React.FC<UploadStepProps> = ({
  currentServiceInfo,
  imagePreviewUrl,
  uploadError,
  educationalWarning,
  onFileSelect,
  onBack,
  onNext,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="bg-neutral-900/70 border border-neutral-800 rounded-2xl p-6 md:p-8 backdrop-blur-md shadow-2xl animate-fadeIn">
      <div className="text-center mb-6">
        <span className="text-xs text-amber-400 font-bold block mb-1">
          خدمت منتخب: {currentServiceInfo?.title}
        </span>
        <h2 className="text-xl font-bold text-neutral-100 mb-1">
          تصویر چهره خود را آپلود کنید
        </h2>
        <p className="text-xs text-neutral-400">
          برای بررسی هندسه چهره و شبیه‌سازی هوشمند {currentServiceInfo?.titleEn}
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          const droppedFile = e.dataTransfer.files?.[0];
          if (droppedFile) onFileSelect(droppedFile);
        }}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 md:p-10 text-center cursor-pointer transition-all duration-300 ${
          isDragging
            ? 'border-amber-400 bg-amber-500/10 scale-[0.99]'
            : 'border-neutral-700 hover:border-amber-500/60 bg-neutral-950/50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_ATTRIBUTE}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFileSelect(f);
          }}
          className="hidden"
        />
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-neutral-800/80 border border-neutral-700 flex items-center justify-center text-amber-400 text-2xl">
          {currentServiceInfo?.icon}
        </div>
        <p className="text-sm font-semibold text-neutral-200 mb-1">
          برای انتخاب عکس کلیک کنید یا فایل را اینجا رها کنید
        </p>
        <p className="text-xs text-neutral-500">پشتیبانی از JPG، PNG یا WEBP (حداکثر ۵ مگابایت)</p>
      </div>

      {uploadError && (
        <div className="mt-4 p-3 rounded-lg bg-red-950/60 border border-red-800 text-red-300 text-xs">
          {uploadError}
        </div>
      )}

      {educationalWarning && (
        <div className="mt-4 p-3.5 rounded-xl bg-amber-950/50 border border-amber-600/70 text-amber-200 text-xs flex items-center gap-2">
          <span className="text-amber-400 font-bold">💡 راهنمایی:</span>
          <span>{educationalWarning}</span>
        </div>
      )}

      <div className="mt-6 p-4 rounded-xl bg-neutral-950/80 border border-neutral-800/90">
        <h4 className="text-xs font-bold text-amber-400 mb-2.5 flex items-center gap-1.5">
          <span>💡 راهنمای ثبت تصویر مناسب برای {currentServiceInfo?.title}:</span>
        </h4>
        <ul className="text-xs text-neutral-400 space-y-2 list-disc list-inside">
          <li>نور ملایم رو به پنجره بتابد تا جزئیات طبیعی پوست واضح باشد.</li>
          <li>چهره مستقیم و بدون فیلتر اینستاگرام یا عینک باشد.</li>
          <li>ناحیه مد نظر ({currentServiceInfo?.title}) به وضوح در کادر دیده شود.</li>
        </ul>
      </div>

      <div className="mt-6 flex flex-col-reverse sm:flex-row justify-between items-stretch sm:items-center gap-3">
        <button
          onClick={onBack}
          className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-neutral-800 text-neutral-400 text-xs hover:text-neutral-200 cursor-pointer text-center"
        >
          تغییر خدمت
        </button>
        {imagePreviewUrl && (
          <button
            onClick={onNext}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-xs font-bold cursor-pointer text-center"
          >
            ادامه به بررسی ایمنی ←
          </button>
        )}
      </div>
    </div>
  );
};
