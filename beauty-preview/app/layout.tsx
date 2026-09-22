import type { Metadata, Viewport } from 'next';
import localFont from 'next/font/local';

import './globals.css';

/**
 * فونت وزیرمتن — در همه‌جای صفحه.
 * فایل فونت به‌صورت لوکال (self-hosted) داخل app/fonts قرار دارد تا ساخت
 * پروژه به دسترسی به Google Fonts وابسته نباشد.
 */
const vazirmatn = localFont({
  src: [{ path: './fonts/Vazirmatn-Variable.woff2', weight: '100 900', style: 'normal' }],
  variable: '--font-vazirmatn',
  display: 'swap',
  fallback: ['Vazirmatn', 'Tahoma', 'system-ui', 'sans-serif'],
});

export const metadata: Metadata = {
  title: 'پیش‌نمایش هوشمند ابرو | میکروبلیدینگ خانم رجبی',
  description:
    'مدل ابرو و رنگ دلخواه را انتخاب کنید، عکس چهره‌تان را آپلود کنید و پیش‌نمایش میکروبلیدینگ را با هوش مصنوعی ببینید.',
  keywords: ['میکروبلیدینگ', 'ابرو', 'پیش‌نمایش هوشمند', 'رجببی', 'زیبایی'],
};

export const viewport: Viewport = {
  themeColor: '#0A0A0A',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" className={vazirmatn.variable}>
      <body className="font-vazir text-white antialiased">{children}</body>
    </html>
  );
}
