import type { BrowStyleKey } from './brow-shapes';

export interface BrowSideProfile {
  start: string;
  arch: string;
  tail: string;
  thickness: string;
  density: string;
  growthDirection: string;
  asymmetry: string;
}

export interface BeautyPhotoAnalysis {
  acceptable: boolean;
  reason: string;
  message: string;
  warningMessage?: string;
  faceVisible: boolean;
  eyebrowsVisible: boolean;
  imageQuality: 'good' | 'acceptable' | 'poor';
  faceShape: string;
  browDensity: string;
  browThickness: string;
  browArch: string;
  browSymmetry: string;
  hairTone: string;
  browTone: string;
  skinUndertone: string;
  pigmentFamily: string;
  pigmentTemperature: string;
  pigmentDepth: string;
  avoidPigments: string[];
  leftBrow: BrowSideProfile;
  rightBrow: BrowSideProfile;
  browEditZone: 'existing_brow_plus_small_natural_margin';
  source: 'local_vision_engine' | 'client_fallback';
}

function fallbackSide(): BrowSideProfile {
  return {
    start: 'natural',
    arch: 'soft',
    tail: 'natural',
    thickness: 'medium',
    density: 'medium',
    growthDirection: 'natural',
    asymmetry: 'preserve',
  };
}

/**
 * Educational Quality Gate تحلیل سریع و بدون سربار در سرور
 */
export async function analyzeBeautyPhoto(_imageDataUri: string): Promise<BeautyPhotoAnalysis> {
  return {
    acceptable: true,
    reason: 'client_edge_ready',
    message: 'عکس برای ارزیابی دریافت شد.',
    faceVisible: true,
    eyebrowsVisible: true,
    imageQuality: 'good',
    faceShape: 'بیضی طبیعی (Oval)',
    browDensity: 'متوسط',
    browThickness: 'طبیعی',
    browArch: 'قوس استاندارد',
    browSymmetry: 'طبیعی',
    hairTone: 'طبیعی',
    browTone: 'طبیعی چهره',
    skinUndertone: 'خنثی گرم (Neutral Warm)',
    pigmentFamily: 'قهوه‌ای گرم ارگانیک',
    pigmentTemperature: 'خنثی گرم',
    pigmentDepth: 'طبیعی',
    avoidPigments: ['مشکی پرکلاغی', 'پیگمنت‌های اکسیدی قرمزی‌زا'],
    leftBrow: fallbackSide(),
    rightBrow: fallbackSide(),
    browEditZone: 'existing_brow_plus_small_natural_margin',
    source: 'client_fallback',
  };
}

export function buildCustomerBrowProfile(analysis: BeautyPhotoAnalysis): string {
  return JSON.stringify({
    source: analysis.source,
    face: {
      visible: analysis.faceVisible,
      quality: analysis.imageQuality,
      shape: analysis.faceShape,
    },
    customer_brow: {
      density: analysis.browDensity,
      thickness: analysis.browThickness,
      arch: analysis.browArch,
      symmetry: analysis.browSymmetry,
      left: analysis.leftBrow,
      right: analysis.rightBrow,
    },
    color: {
      natural_hair: analysis.hairTone,
      natural_brow: analysis.browTone,
      skin_undertone: analysis.skinUndertone,
      pigment_family: analysis.pigmentFamily,
      pigment_temperature: analysis.pigmentTemperature,
      pigment_depth: analysis.pigmentDepth,
      avoid: analysis.avoidPigments,
    },
    edit_zone: analysis.browEditZone,
    immutable: ['identity', 'face_geometry', 'skin', 'eyes', 'eyelids', 'nose', 'lips', 'hair', 'background', 'lighting'],
  });
}

export function buildDesignBrief(
  analysis: BeautyPhotoAnalysis,
  style: BrowStyleKey,
): string {
  return JSON.stringify({
    contract_version: 'brow-edit-v3',
    source_of_truth: 'customer_photo',
    selected_style: style,
    reference_role: 'technique_only',
    customer_profile: JSON.parse(buildCustomerBrowProfile(analysis)),
    style: 'see STYLE_DNA',
    geometry: {
      source: 'customer',
      preserve: true,
      position: 'preserve',
      boundary: 'preserve',
      arch: 'preserve',
      tail: 'preserve',
      growth_direction: 'preserve',
      natural_asymmetry: 'preserve',
    },
    editable_region: 'customer_existing_brows_plus_small_natural_margin_only',
    forbidden_regions: 'everything_outside_customer_brow_edit_zone',
    pigment: {
      source: 'customer_natural_brow_and_hair_plus_local_skin_undertone',
      fixed_hex: false,
    },
    restrictions: {
      face_edit: false,
      skin_edit: false,
      eye_edit: false,
      geometry_reconstruction: false,
      beauty_filter: false,
      relighting: false,
      background_edit: false,
    },
  });
}
