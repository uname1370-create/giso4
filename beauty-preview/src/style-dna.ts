import type { BrowStyleKey } from './brow-shapes';

export interface StyleDNA {
  key: BrowStyleKey;
  technique: string;
  front: string;
  body: string;
  tail: string;
  density: string;
  texture: string;
  forbidden: string[];
}

export const STYLE_DNA: Record<BrowStyleKey, StyleDNA> = {
  hairstroke: {
    key: 'hairstroke',
    technique: 'individual micro hair strokes',
    front: 'soft and sparse',
    body: 'low-to-medium natural density with visible gaps',
    tail: 'thin and tapered',
    density: 'low natural density',
    texture: 'separated tapered strokes following the customer hair-growth direction',
    forbidden: ['powder fill', 'solid block', 'skin tint', 'shadow halo', 'new brow geometry'],
  },
  feather: {
    key: 'feather',
    technique: 'airy feather-stroke PMU',
    front: 'very light and feathered',
    body: 'low density with separated strokes',
    tail: 'thin and tapered',
    density: 'very low natural density',
    texture: 'soft separated feather strokes with natural irregularity',
    forbidden: ['solid pigment', 'powder fill', 'skin tint', 'shadow halo', 'new brow geometry'],
  },
  ombre: {
    key: 'ombre',
    technique: 'translucent powder shading',
    front: 'lightest and softly faded',
    body: 'medium translucent powder',
    tail: 'deeper but still soft',
    density: 'medium visual fill without hard edges',
    texture: 'velvety powder, no individual hair strokes',
    forbidden: ['hair strokes', 'pigment outside customer brow zone', 'eyelid shadow', 'skin retouching', 'new brow geometry'],
  },
  combination: {
    key: 'combination',
    technique: 'fine hairstrokes plus translucent powder',
    front: 'fine natural hairstrokes',
    body: 'soft translucent powder between natural strokes',
    tail: 'soft powder with a few tapered strokes only when consistent with the customer brow',
    density: 'medium natural density, never blocky',
    texture: 'mixed hair-stroke and powder finish',
    forbidden: ['solid block', 'pigment outside customer brow zone', 'under-brow shadow', 'eyelid makeup', 'new brow geometry'],
  },
};

export function styleDnaFor(key: BrowStyleKey): StyleDNA {
  return STYLE_DNA[key];
}

export function styleDnaText(key: BrowStyleKey): string {
  const s = styleDnaFor(key);
  return [
    `STYLE_DNA key=${s.key}`,
    `technique=${s.technique}`,
    `front=${s.front}`,
    `body=${s.body}`,
    `tail=${s.tail}`,
    `density=${s.density}`,
    `texture=${s.texture}`,
    `forbidden=${s.forbidden.join(', ')}`,
  ].join('; ');
}
