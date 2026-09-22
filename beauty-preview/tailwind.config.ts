import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        ink: '#0A0A0A',        // پس‌زمینهٔ اصلی (deep black)
        card: '#1A1A1A',       // کارت‌ها
        cardSoft: '#121212',   // کارت ثانویه
        gold: {
          DEFAULT: '#D4AF37',  // اکسنت طلایی
          soft: '#E7CE7B',
          deep: '#A8842A',
          dim: 'rgba(212, 175, 55, 0.35)',
        },
        hair: '#2A2A2A',       // خطوط جداکننده
        mist: '#B8B8B8',       // متن روشن‌خاکستری
      },
      fontFamily: {
        vazir: ['var(--font-vazirmatn)', 'Vazirmatn', 'Tahoma', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        gold: '0 0 0 1px rgba(212,175,55,0.55), 0 18px 46px -22px rgba(212,175,55,0.55)',
        glow: '0 10px 40px -18px rgba(212,175,55,0.65)',
      },
      keyframes: {
        shine: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '0.35' },
          '50%': { opacity: '0.75' },
        },
      },
      animation: {
        shine: 'shine 2.4s linear infinite',
        fadeUp: 'fadeUp 0.5s ease-out both',
        pulseSoft: 'pulseSoft 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};

export default config;
