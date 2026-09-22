/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  /**
   * پوشهٔ خروجی build.
   * به‌صورت پیش‌فرض `.next` است. اسکریپت تست پنل مدیریت با تنظیم
   * `NEXT_DIST_DIR=.next-admin-test` یک پوشهٔ جدا می‌سازد تا اگر سرور `npm run dev`
   * شما در حال اجرا باشد، خراب نشود.
   */
  distDir: process.env.NEXT_DIST_DIR || '.next',
  // تصاویر SVG ابروها با تگ <img> ساده نمایش داده می‌شوند؛ نیازی به دامنهٔ خارجی نیست.
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' },
    ],
  },
};

export default nextConfig;
