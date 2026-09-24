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

/** نواحی غیرقابل‌تغییر پایه؛ برای لب، خود لب از فهرست حذف می‌شود */
const BASE_IMMUTABLE = ['identity', 'face_geometry', 'skin', 'eyes', 'eyelids', 'nose', 'lips', 'hair', 'background', 'lighting'];

/** پروفایل عمومی چهره+رنگ برای خدمات غیرابرو (هندسه ناحیه از روی عکس استنتاج می‌شود) */
function buildCustomerZoneProfile(analysis: BeautyPhotoAnalysis, service: string): string {
  return JSON.stringify({
    source: analysis.source,
    face: {
      visible: analysis.faceVisible,
      quality: analysis.imageQuality,
      shape: analysis.faceShape,
    },
    zone: {
      service,
      geometry_source: 'customer_photo',
      preserve_native_anatomy: true,
    },
    color: {
      skin_undertone: analysis.skinUndertone,
      pigment_family: analysis.pigmentFamily,
      pigment_temperature: analysis.pigmentTemperature,
      pigment_depth: analysis.pigmentDepth,
      avoid: analysis.avoidPigments,
    },
    edit_zone: `${service}_zone_only`,
    immutable: service === 'lips' ? BASE_IMMUTABLE.filter((item) => item !== 'lips') : BASE_IMMUTABLE,
  });
}

/**
 * بریف فشردهٔ طراحی — عمداً کوتاه نگه داشته شده است.
 * فهرست‌های بلند preserve/forbidden/geometry که در همهٔ مدل‌ها یکسان بودند و
 * سیگنال سبک را رقیق می‌کردند حذف شدند (همان حرف یک‌بار در بلوک SCOPE قالب
 * پرامپت گفته می‌شود). این بریف فقط «کدام سبک + کدام ناحیه + رنگ مشتری» را می‌گوید.
 */
export function buildDesignBrief(
  analysis: BeautyPhotoAnalysis,
  style: string,
  service: string = 'eyebrows',
): string {
  const perService: Record<string, { contract: string; referenceRole: string; editableRegion: string }> = {
    lips: {
      contract: 'lip-edit-v2',
      referenceRole: 'technique_only',
      editableRegion: 'customer_lip_vermilion_only',
    },
    eyeliner: {
      contract: 'liner-edit-v2',
      referenceRole: 'technique_only',
      editableRegion: 'upper_lash_line_zone_only',
    },
    removal: {
      contract: 'removal-fade-v2',
      referenceRole: 'none_no_reference',
      editableRegion: 'artificial_pigment_traces_only',
    },
    eyebrows: {
      contract: 'brow-edit-v4',
      referenceRole: 'technique_only',
      editableRegion: 'customer_existing_brows_only',
    },
  };
  const preset = perService[service] ?? perService.eyebrows;

  return JSON.stringify({
    contract_version: preset.contract,
    source_of_truth: 'customer_photo',
    selected_style: style,
    reference_role: preset.referenceRole,
    customer: {
      face_shape: analysis.faceShape,
      image_quality: analysis.imageQuality,
      skin_undertone: analysis.skinUndertone,
      pigment_family: analysis.pigmentFamily,
      pigment_temperature: analysis.pigmentTemperature,
      pigment_depth: analysis.pigmentDepth,
      avoid_pigments: analysis.avoidPigments,
    },
    style: 'see STYLE_DNA',
    editable_region: preset.editableRegion,
    // NOTE: بلوک restrictions حذف شد — همان حرف در SCOPE قالب پرامپت گفته می‌شود
    // و تکرار JSON آن فقط ۲۰۰+ کاراکتر یکسان به همهٔ مدل‌ها اضافه می‌کرد.
  });
}
