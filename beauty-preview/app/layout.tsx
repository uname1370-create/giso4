import type { Metadata, Viewport } from 'next';
import localFont from 'next/font/local';

import './globals.css';
import { AiChatWidget } from '@/components/AiChatWidget';

/**
 * فونت وزیرمتن — در همه‌جای صفحه.
 * فایل فونت به‌صورت لوکال (self-hosted) داخل app/fonts قرار دارد.
 */
const vazirmatn = localFont({
  src: [{ path: './fonts/Vazirmatn-Variable.woff2', weight: '100 900', style: 'normal' }],
  variable: '--font-vazirmatn',
  display: 'swap',
  fallback: ['Vazirmatn', 'Tahoma', 'system-ui', 'sans-serif'],
});

export const metadata: Metadata = {
  title: 'استودیو تخصصی PMU عسل رجبی | پیش‌نمایش هوشمند زیبایی',
  description:
    'شبیه‌سازی زنده و اختصاصی میکروبلیدینگ ابرو، شیدینگ لب، خط چشم و ریمو با هوش مصنوعی نسل جدید و مشاوره آنلاین.',
  keywords: ['میکروبلیدینگ مشهد', 'شیدینگ لب', 'عسل رجبی', 'PMU', 'ریمو تاتو', 'پیش‌نمایش هوشمند'],
};

export const viewport: Viewport = {
  themeColor: '#0A0A0A',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" className={vazirmatn.variable}>
      <body className="font-vazir text-white antialiased relative min-h-screen">
        {children}
        {/* دستیار هوشمند غزل — فعال در تمام صفحات با بالاترین z-index */}
        <AiChatWidget />
      </body>
    </html>
  );
}
