/**
 * src/plan-config.ts
 * ---------------------------------------------------------------------------
 * تعریف نوع پلن‌های تجاری و ماتریس دسترسی به امکانات پلتفرم
 * ---------------------------------------------------------------------------
 */

export type PlanTier = 'bronze' | 'silver' | 'gold';

export interface PlanConfig {
  tier: PlanTier;
  label: string;
  badge: string;
  priceMonthly: number; // به تومان
  monthlyGenerationsLimit: number; // -1 به معنای نامحدود
  allowedServices: ('eyebrows' | 'lips' | 'eyeliner' | 'removal')[];
  watermarkEnabled: boolean;
  biometricScanEffect: boolean;
  goldVipCard: boolean;
  aiChatbotEnabled: boolean;
  customAssistantName: boolean;
  customGalleryUpload: boolean;
}

export const PLAN_CONFIGS: Record<PlanTier, PlanConfig> = {
  bronze: {
    tier: 'bronze',
    label: 'پلن برنزی (پایه‌ای)',
    badge: '🥉 برنزی',
    priceMonthly: 500_000,
    monthlyGenerationsLimit: 50,
    allowedServices: ['eyebrows'],
    watermarkEnabled: true,
    biometricScanEffect: false,
    goldVipCard: false,
    aiChatbotEnabled: false,
    customAssistantName: false,
    customGalleryUpload: false,
  },
  silver: {
    tier: 'silver',
    label: 'پلن نقره‌ای (حرفه‌ای)',
    badge: '🥈 نقره‌ای',
    priceMonthly: 1_500_000,
    monthlyGenerationsLimit: 250,
    allowedServices: ['eyebrows', 'lips', 'eyeliner'],
    watermarkEnabled: false,
    biometricScanEffect: false,
    goldVipCard: false,
    aiChatbotEnabled: true,
    customAssistantName: false,
    customGalleryUpload: false,
  },
  gold: {
    tier: 'gold',
    label: 'پلن طلایی (VIP و اختصاصی)',
    badge: '🥇 طلایی VIP',
    priceMonthly: 3_000_000,
    monthlyGenerationsLimit: -1, // نامحدود
    allowedServices: ['eyebrows', 'lips', 'eyeliner', 'removal'],
    watermarkEnabled: false,
    biometricScanEffect: true,
    goldVipCard: true,
    aiChatbotEnabled: true,
    customAssistantName: true,
    customGalleryUpload: true,
  },
};

export function getPlanConfig(tier: string = 'gold'): PlanConfig {
  const normalized = (tier || '').toLowerCase() as PlanTier;
  return PLAN_CONFIGS[normalized] || PLAN_CONFIGS.gold;
}
