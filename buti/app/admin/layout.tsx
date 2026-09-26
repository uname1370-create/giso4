import type { Metadata } from 'next';

/**
 * app/admin/layout.tsx
 * ---------------------------------------------------------------------------
 * پوستهٔ مشترک پنل مدیریت (پس‌زمینهٔ تیره + متادیتای noindex).
 * راست‌به‌چپ و فونت وزیرمتن از layout ریشه به ارث می‌رسد.
 * ---------------------------------------------------------------------------
 */

export const metadata: Metadata = {
  title: 'پنل مدیریت | عسل رجبی',
  description: 'پنل مدیریت سالن زیبایی عسل رجبی — آمار بازدید و مدیریت تصاویر',
  robots: { index: false, follow: false },
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-ink text-white">{children}</div>;
}
