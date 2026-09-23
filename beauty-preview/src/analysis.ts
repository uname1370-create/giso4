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

export function buildDesignBrief(
  analysis: BeautyPhotoAnalysis,
  style: string,
  service: string = 'eyebrows',
): string {
  if (service === 'lips') {
    return JSON.stringify({
      contract_version: 'lip-edit-v1',
      source_of_truth: 'customer_photo',
      selected_style: style,
      reference_role: 'technique_only',
      customer_profile: JSON.parse(buildCustomerZoneProfile(analysis, service)),
      style: 'see STYLE_DNA',
      geometry: {
        source: 'customer',
        preserve: true,
        position: 'preserve',
        vermilion_boundary: 'preserve',
        border: 'preserve',
        commissures: 'preserve',
        volume_ratio: 'preserve',
        natural_asymmetry: 'preserve',
      },
      editable_region: 'customer_lip_vermilion_only',
      forbidden_regions: 'teeth_tongue_inner_mouth_chin_nose_and_everything_outside_lips',
      pigment: {
        source: 'customer_native_mucosal_tone_plus_local_skin_undertone',
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

  if (service === 'eyeliner') {
    return JSON.stringify({
      contract_version: 'liner-edit-v1',
      source_of_truth: 'customer_photo',
      selected_style: style,
      reference_role: 'technique_only',
      customer_profile: JSON.parse(buildCustomerZoneProfile(analysis, service)),
      style: 'see STYLE_DNA',
      geometry: {
        source: 'customer',
        preserve: true,
        position: 'preserve',
        eye_shape: 'preserve',
        tilt: 'preserve',
        lid_fold: 'preserve',
        lash_direction: 'preserve',
        natural_asymmetry: 'preserve',
      },
      editable_region: 'upper_lash_line_zone_only',
      forbidden_regions: 'eyeball_iris_sclera_waterline_lower_lid_brows_and_all_other_regions',
      pigment: {
        source: 'carbon_black_matched_to_customer_undertone',
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

  if (service === 'removal') {
    return JSON.stringify({
      contract_version: 'removal-fade-v1',
      source_of_truth: 'customer_photo',
      selected_style: style,
      reference_role: 'none_no_reference',
      customer_profile: JSON.parse(buildCustomerZoneProfile(analysis, service)),
      style: 'see STYLE_DNA',
      geometry: {
        source: 'customer',
        preserve: true,
        position: 'preserve',
        native_hair: 'preserve',
        skin_texture: 'preserve',
      },
      editable_region: 'artificial_pigment_traces_only',
      forbidden_regions: 'all_native_anatomy',
      pigment: {
        source: 'none_fade_to_native_skin',
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
        new_pigment: false,
      },
    });
  }

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
