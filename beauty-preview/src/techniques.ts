export interface TechniqueStyleOption {
  key: string;
  label: string;
  labelEn: string;
  hint: string;
  sampleImage: string;
}

export const SERVICE_TECHNIQUES: Record<'eyebrows' | 'lips' | 'eyeliner', TechniqueStyleOption[]> = {
  eyebrows: [
    {
      key: 'hairstroke',
      label: 'هایر استروک طبیعی',
      labelEn: 'Natural Hairstroke',
      hint: 'تارهای فوق‌العاده ظریف و کرکی متناسب با جهت رویش موهای طبیعی',
      sampleImage: '/eyebrows/natural-hairstroke.png',
    },
    {
      key: 'feather',
      label: 'فدر براو (Feather)',
      labelEn: 'Feather Brow',
      hint: 'تارهای سبک و پر مانند با فاصله طبیعی بدون ایجاد کادر',
      sampleImage: '/eyebrows/feather.png',
    },
    {
      key: 'ombre',
      label: 'آمبره پودری (Ombre)',
      labelEn: 'Ombre Powder',
      hint: 'شیدینگ مخملی و پودری ملایم، روشن در تاج و تیره در دنباله',
      sampleImage: '/eyebrows/ombre-powder.png',
    },
    {
      key: 'combination',
      label: 'کامبینیشن تلفیقی',
      labelEn: 'Combination',
      hint: 'تلفیق تارهای مویی در تاج و سایه پودری لطیف در انتهای ابرو',
      sampleImage: '/eyebrows/combination.png',
    },
  ],
  lips: [
    {
      key: 'natural_blush',
      label: 'لیپ بلاش آبرنگی نچرال',
      labelEn: 'Sheer Watercolor Blush',
      hint: 'تینت ملایم و شاداب بدون حاشیه خطی مشخص (جلوه تینت طبیعی)',
      sampleImage: '/lips/natural_blush.png',
    },
    {
      key: 'nude_pink',
      label: 'شیدینگ نود پینک کالباسی',
      labelEn: 'Nude Pink Contour',
      hint: 'تناژ کالباسی هلویی شیک و ملایم مناسب استفاده روزمره',
      sampleImage: '/lips/nude_pink.png',
    },
    {
      key: 'full_color',
      label: 'فول کالر خوش‌رنگ و بادوام',
      labelEn: 'Full Velvet Lip',
      hint: 'تراکم و درخشندگی بیشتر پیگمنت برای لب‌های یکدست و پررنگ‌تر',
      sampleImage: '/lips/full_color.png',
    },
    {
      key: 'dark_neutralization',
      label: 'خنثی‌سازی تیرگی لب',
      labelEn: 'Dark Lip Neutralization',
      hint: 'متد دو مرحله‌ای اصلاح پیگمنت‌های تیره و بنفش لب با تناژ گرم',
      sampleImage: '/lips/dark_neutralization.png',
    },
  ],
  eyeliner: [
    {
      key: 'lash_line_enhancement',
      label: 'بُن‌مژه مخفی و بسیار طبیعی',
      labelEn: 'Lash Line Enhancement',
      hint: 'کاشت پیگمنت کربن‌بلک در لابه لای ریشه مژه‌ها بدون امتداد دم',
      sampleImage: '/eyeliner/lash_line_enhancement.png',
    },
    {
      key: 'classic_liner',
      label: 'خط چشم کلاسیک ظریف',
      labelEn: 'Classic Eyeliner',
      hint: 'خط صاف و ممتد با کشیدگی ظریف متناسب با فرم چشم',
      sampleImage: '/eyeliner/classic_liner.png',
    },
    {
      key: 'smokey_shade',
      label: 'شیدینگ پودری اسموکی',
      labelEn: 'Smokey Stardust Liner',
      hint: 'سایه مخملی مات در لبه بالایی خط چشم برای پلک‌های دارای پف',
      sampleImage: '/eyeliner/smokey_shade.png',
    },
  ],
};
