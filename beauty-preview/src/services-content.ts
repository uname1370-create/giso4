export interface ServiceInfo {
  id: 'eyebrows' | 'lips' | 'eyeliner' | 'removal';
  title: string;
  titleEn: string;
  icon: string;
  shortDesc: string;
  duration: string;
  durability: string;
  idealFor: string;
  careTips: string[];
}

export const SERVICES_CONTENT: Record<string, ServiceInfo> = {
  eyebrows: {
    id: 'eyebrows',
    title: 'میکروبلیدینگ و نانوبروز ابرو',
    titleEn: 'Microblading & Nano Brows',
    icon: '✨',
    shortDesc: 'ترسیم ظریف‌ترین تارهای نچرال مویی و شیدینگ پودری متناسب با آناتومی چهره شما.',
    duration: '۲ الی ۲.۵ ساعت',
    durability: '۱۲ تا ۱۸ ماه',
    idealFor: 'ابروهای کم‌پشت، نامتقارن یا افرادی که فرم طبیعی و آراسته می‌پسندند.',
    careTips: [
      'عدم شستشو و تماس با آب تا ۳ روز اول',
      'استفاده از پماد مراقبتی مخصوص طبق دستور پیگمنتر',
      'پرهیز از نور مستقیم خورشید، سونا و استخر تا ۲ هفته',
    ],
  },
  lips: {
    id: 'lips',
    title: 'شیدینگ و کانتورینگ لب (لیپ بلاش)',
    titleEn: 'Lip Blush & Shading',
    icon: '💋',
    shortDesc: 'شاداب‌سازی، اصلاح تقارن و ایجاد تینت طبیعی مخملی بدون کادر ضخیم و غیرطبیعی.',
    duration: '۲ الی ۲.۵ ساعت',
    durability: '۲ تا ۳ سال',
    idealFor: 'لب‌های رنگ‌پریده، دارای تیرگی ملانینی یا فرم‌های نامتقارن.',
    careTips: [
      'استفاده مداوم از بالم لب هیدراته و استریل',
      'پرهیز از مصرف غذاهای تند، اسیدی یا بسیار داغ تا ۵ روز',
      'مصرف داروی ضدویروس در صورت سابقه تبخال با مشورت پزشک',
    ],
  },
  eyeliner: {
    id: 'eyeliner',
    title: 'خط چشم دائم و بن‌مژه ظریف',
    titleEn: 'Permanent Eyeliner & Lash Line',
    icon: '👁️',
    shortDesc: 'کاشت پیگمنت مشکی بدون تغییر رنگ در خط مژه‌ها برای گیرایی عمیق نگاه.',
    duration: '۱.۵ الی ۲ ساعت',
    durability: '۳ تا ۵ سال',
    idealFor: 'افرادی که می‌خواهند بدون آرایش روزانه، چشمانی درشت‌تر و خوش‌حالت‌تر داشته باشند.',
    careTips: [
      'استفاده نکردن از ریمل یا لوازم آرایشی چشم تا ۱۰ روز',
      'کمپرس سرد غیرمستقیم در صورت تورم خفیف اولیه',
      'پرهیز از دستکاری یا کشیدن پوسته‌های ناحیه پلک',
    ],
  },
  removal: {
    id: 'removal',
    title: 'ریمو تخصصی تاتوی قدیمی',
    titleEn: 'Tattoo & PMU Removal',
    icon: '🫧',
    shortDesc: 'تخلیه و خروج ایمن پیگمنت‌های اکسید شده، قرمز یا بدفرم با متد آنزیمی و بدون آسیب به پوست.',
    duration: '۴۵ دقیقه',
    durability: 'دائمی (خروج کامل پیگمنت)',
    idealFor: 'تاتوهای قدیمی پررنگ، بدرنگ یا دفرم شده جهت بستر‌سازی اجرای مجدد.',
    careTips: [
      'خشک نگه داشتن موضع تا افتادن طبیعی دلمه‌ها',
      'عدم کندن زخم‌ها و پوسته‌های محافظ',
      'استفاده منظم از پمادهای ترمیم‌کننده پوست',
    ],
  },
};
