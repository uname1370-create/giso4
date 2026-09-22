/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // تصاویر SVG ابروها با تگ <img> ساده نمایش داده می‌شوند؛ نیازی به دامنهٔ خارجی نیست.
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' },
    ],
  },
};

export default nextConfig;
