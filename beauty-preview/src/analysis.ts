import { ProviderError, timeoutSignal } from './providers/http';
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
  source: 'local_vision_engine';
}

const DEFAULT_TIMEOUT_MS = 12_000;

function engineUrl(): string {
  return (process.env.VISION_ENGINE_URL ?? 'http://127.0.0.1:8010').trim().replace(/\/$/, '');
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

function stringValue(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

function listValue(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string').slice(0, 6)
    : [];
}

export async function analyzeBeautyPhoto(imageDataUri: string): Promise<BeautyPhotoAnalysis> {
  const { signal, done } = timeoutSignal(
    Number(process.env.VISION_ANALYSIS_TIMEOUT_MS) > 1000
      ? Number(process.env.VISION_ANALYSIS_TIMEOUT_MS)
      : DEFAULT_TIMEOUT_MS,
  );

  try {
    const response = await fetch(engineUrl() + '/v1/analyze', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ service: 'eyebrows', image: imageDataUri }),
      signal,
      cache: 'no-store',
    });

    const raw = await response.text();
    let payload: unknown = null;
    try { payload = raw ? JSON.parse(raw) : null; } catch { payload = null; }

    if (!response.ok) {
      const detail =
        payload && typeof payload === 'object' && typeof (payload as Record<string, unknown>).detail === 'string'
          ? String((payload as Record<string, unknown>).detail)
          : raw.slice(0, 500);
      throw new ProviderError('تحلیل عکس انجام نشد', detail);
    }

    if (!payload || typeof payload !== 'object') {
      throw new ProviderError('پاسخ تحلیل عکس نامعتبر بود');
    }

    const data = payload as Record<string, unknown>;
    const acceptable = data.acceptable === true;
    const left = data.leftBrow && typeof data.leftBrow === 'object'
      ? data.leftBrow as Record<string, unknown>
      : {};
    const right = data.rightBrow && typeof data.rightBrow === 'object'
      ? data.rightBrow as Record<string, unknown>
      : {};

    const makeSide = (side: Record<string, unknown>): BrowSideProfile => ({
      start: stringValue(side.start, 'natural'),
      arch: stringValue(side.arch, 'soft'),
      tail: stringValue(side.tail, 'natural'),
      thickness: stringValue(side.thickness, 'medium'),
      density: stringValue(side.density, 'medium'),
      growthDirection: stringValue(side.growthDirection, 'natural'),
      asymmetry: stringValue(side.asymmetry, 'preserve'),
    });

    return {
      acceptable,
      reason: stringValue(data.reason, acceptable ? 'good_photo' : 'photo_not_suitable'),
      message: stringValue(
        data.message,
        acceptable
          ? 'عکس برای پیش‌نمایش مناسب است.'
          : 'لطفاً عکس واضح و روبه‌رو بفرستید و ابروها مشخص باشند.',
      ),
      faceVisible: data.faceVisible === true,
      eyebrowsVisible: data.eyebrowsVisible === true,
      imageQuality: ['good', 'acceptable', 'poor'].includes(String(data.imageQuality))
        ? String(data.imageQuality) as BeautyPhotoAnalysis['imageQuality']
        : 'acceptable',
      faceShape: stringValue(data.faceShape, 'natural'),
      browDensity: stringValue(data.browDensity, 'medium'),
      browThickness: stringValue(data.browThickness, 'medium'),
      browArch: stringValue(data.browArch, 'soft'),
      browSymmetry: stringValue(data.browSymmetry, 'natural'),
      hairTone: stringValue(data.hairTone, 'natural'),
      browTone: stringValue(data.browTone, 'natural'),
      skinUndertone: stringValue(data.skinUndertone, 'neutral'),
      pigmentFamily: stringValue(data.pigmentFamily, 'natural_brown'),
      pigmentTemperature: stringValue(data.pigmentTemperature, 'neutral'),
      pigmentDepth: stringValue(data.pigmentDepth, 'medium'),
      avoidPigments: listValue(data.avoidPigments),
      leftBrow: makeSide(left),
      rightBrow: makeSide(right),
      browEditZone: 'existing_brow_plus_small_natural_margin',
      source: 'local_vision_engine',
    };
  } catch (error) {
    if (error instanceof ProviderError) throw error;
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ProviderError('تحلیل عکس بیش از حد طول کشید');
    }
    throw new ProviderError(
      'سرویس تحلیل عکس در دسترس نیست',
      error instanceof Error ? error.message : String(error),
    );
  } finally {
    done();
  }
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
