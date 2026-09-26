import type { BrowStyleKey } from './brow-shapes';

export type ServiceKey = 'eyebrows' | 'lips' | 'eyeliner' | 'removal';

export interface StyleDNA {
  key: string;
  technique: string;
  front?: string;
  body?: string;
  tail?: string;
  density?: string;
  texture?: string;
  forbidden: string[];
}

export interface UserSubjectivePreferences {
  dailyMakeup?: 'natural' | 'soft' | 'bold'; // نچرال / ملایم / پررنگ
  browShape?: 'natural' | 'defined'; // طبیعی / کادردار
  density?: 'fluffy' | 'dense'; // کرکی / متراکم
  lipLook?: 'natural_blush' | 'nude_pink' | 'full_color' | 'dark_neutralization';
  eyelinerLook?: 'lash_line_enhancement' | 'classic_liner' | 'smokey_shade';
}

/** عبارات بازدارنده جهانی برای تمامی سبک‌ها */
export const GLOBAL_NEGATIVE_CONSTRAINTS = [
  'no harsh solid block',
  'no fake sticker look',
  'no tattooed cutout edge',
  'no overly dark cartoonish lines',
  'no blurry smudge',
  'no skin retouching or plastic airbrushing',
  'no waxy makeup paste',
  'no muddy gray undertone',
  'no blur halo or dirty shadow around edges',
  'no CGI 3D render look',
  'no altered facial anatomy',
];

export const STYLE_DNA: Record<string, StyleDNA> = {
  // مدل‌های ابرو
  hairstroke: {
    key: 'hairstroke',
    technique:
      'ultra-fine crisp individual hair strokes, microblading precision, high-resolution raw beauty photography, perfectly blended pigment',
    front: 'soft gradient front with airy micro-feathers and visible skin beneath',
    body: 'individual ultra-fine tapered keratin hair shafts with natural sheen, macro skin pores visible, natural brow gaps showing bare skin underneath',
    tail: 'thin delicate tapered tail following natural anatomical brow line',
    density: 'low-to-medium natural density with sub-millimeter stroke crispness',
    texture:
      'realistic curvature matching natural brow hair follicle direction, variable stroke pressure (thinner at tip and root), air-permeable organic pigment settling into the epidermis',
    forbidden: [
      'powder fill',
      'solid block',
      'skin tint',
      'shadow halo',
      'new brow geometry',
      'harsh stencil outline',
      'stamp look',
    ],
  },
  feather: {
    key: 'feather',
    technique:
      'airy feather-stroke PMU, ultra-fine crisp hair strokes, microblading precision, raw beauty photography',
    front: 'very light and feathered, transparent airy spacing, visible skin pores',
    body: 'sub-millimeter separated tapered strokes with natural irregular growth, macro skin pores visible',
    tail: 'delicate ultra-thin tapered finish',
    density: 'very low natural airy density, never compact',
    texture:
      'separated feather shafts with natural light reflection and organic pigment blending seamlessly into skin',
    forbidden: [
      'solid pigment',
      'powder fill',
      'skin tint',
      'shadow halo',
      'new brow geometry',
      'blocky brow box',
    ],
  },
  ombre: {
    key: 'ombre',
    technique:
      'translucent micro-dot powder shading, velvety airbrush pixelation, raw beauty macro texture',
    front: 'lightest soft powdery mist, seamless vanishing gradient into natural skin',
    body: 'translucent warm velvet micro-dots with visible skin pores and hair follicles underneath',
    tail: 'gradually deeper but soft and clean, zero harsh outline',
    density: 'medium visual fill without hard edges, breathable skin appearance',
    texture: 'velvety organic micro-pigment gradient, no heavy paint, no flat blocks',
    forbidden: [
      'hair strokes',
      'pigment outside customer brow zone',
      'eyelid shadow',
      'skin retouching',
      'new brow geometry',
      'sharp sharpie outline',
    ],
  },
  combination: {
    key: 'combination',
    technique:
      'fine hairstrokes at front plus translucent velvety powder, high-definition natural beauty macro',
    front: 'fine ultra-realistic micro hairstrokes with visible skin gaps',
    body: 'soft translucent pixel powder layered gently between real natural hair strokes, macro pores visible',
    tail: 'soft powder with a few tapered hairs matching native growth',
    density: 'medium natural dimensional density, never opaque or blocky',
    texture: 'layered multidimensional hair-stroke and powder finish with organic skin sheen',
    forbidden: [
      'solid block',
      'pigment outside customer brow zone',
      'under-brow shadow',
      'eyelid makeup',
      'new brow geometry',
      'sticker appearance',
    ],
  },

  // مدل‌های لب (Lips)
  natural_blush: {
    key: 'natural_blush',
    technique:
      'translucent lip tint, soft velvet finish, natural lip texture, seamless border, no over-lined lipstick',
    density: 'sheer watercolor wash, natural hydration sheen',
    texture:
      'dewy hydrated velvety finish with preserved natural vermilion folds and delicate micro-creases, no dry caking',
    forbidden: [
      'heavy opaque lipstick',
      'overlined lip border',
      'skin staining outside lips',
      'teeth discoloration',
      'matte crust',
      'fake sticker look',
    ],
  },
  nude_pink: {
    key: 'nude_pink',
    technique:
      'elegant soft nude pink translucent lip blush, natural lip texture, seamless fading contour',
    density: 'medium-sheer organic tint blending into native mucosal tone',
    texture:
      'soft dewy velvet finish, realistic moisture reflection, subtle micro-pigment infusion',
    forbidden: [
      'heavy dark liner',
      'dry matte crinkles',
      'unnatural neon shades',
      'harsh outline',
      'cakey cosmetic layer',
    ],
  },
  full_color: {
    key: 'full_color',
    technique:
      'rich organic permanent lip blush with velvety soft edge, authentic lip texture, high-resolution beauty macro',
    density: 'saturated yet luminous velvet lip pigment',
    texture:
      'smooth uniform velvet tint preserving realistic lip texture and delicate creases, non-sticky natural glow',
    forbidden: [
      'smudged borders',
      'asymmetrical outline',
      'staining outside the lips',
      'thick oily gloss',
      'plastic sheen',
    ],
  },
  dark_neutralization: {
    key: 'dark_neutralization',
    technique:
      'warm translucent peach-coral melanin neutralization, corrective sheer glow, natural lip texture',
    density: 'delicate corrective warm balance',
    texture:
      'brightened natural peach undertone, dewy soft velvet finish, completely even color tone',
    forbidden: [
      'purple or grey tones',
      'dark outline',
      'patchy application',
      'opaque orange mask',
      'overlined border',
    ],
  },

  // مدل‌های خط چشم (Eyeliner)
  lash_line_enhancement: {
    key: 'lash_line_enhancement',
    technique:
      'tightline lash enhancement, subtle smudge-proof pigment, soft smokey edge, natural eye geometry',
    density: 'ultra-fine micro pigment line embedded directly into lash base roots',
    texture:
      'invisible natural eye depth definition, rooted precisely between eyelash follicles with zero spill',
    forbidden: [
      'thick winged tails',
      'eyeshadow halos',
      'blue or green color bleed',
      'heavy liquid liner look',
      'unnatural line wobble',
    ],
  },
  classic_liner: {
    key: 'classic_liner',
    technique:
      'crisp clean classic permanent eyeliner with delicate tapered flick, tightline lash enhancement, razor-fine elegance',
    density: 'opaque jet black line tapering into sheer wing',
    texture:
      'smooth sharp edge hugging lash roots, natural eyelid skin texture preserved, clean photographic clarity',
    forbidden: [
      'smudged shadow',
      'drooping tail',
      'harsh blocky thickness',
      'blue color migration',
      'jagged digital edges',
    ],
  },
  smokey_shade: {
    key: 'smokey_shade',
    technique:
      'stardust shaded eyeliner with soft diffused gradient on upper eyelid, subtle smudge-proof pigment, soft smokey edge',
    density: 'gradient smoky shading fading upward into skin tone',
    texture:
      'soft pixelated micro-gradient above crisp base lash line, authentic skin texture and pores visible',
    forbidden: [
      'raccoon eye effect',
      'under-eye bleeding',
      'harsh lines',
      'muddy gray patch',
      'pigment fallout look',
    ],
  },

  // ریمو (محو پیگمنت قدیمی — بدون پیگمنت جدید)
  removal: {
    key: 'removal',
    technique:
      'gradual enzymatic PMU pigment fading toward clean natural skin, healed realistic result, zero new pigment',
    density: 'fully faded old pigment, native skin and hair fully visible',
    texture:
      'natural skin texture with visible pores, no bleaching halo, no scar sheen, realistic healed finish',
    forbidden: [
      'new pigment',
      'dark outline',
      'bleached white patch',
      'scar gloss',
      'color inversion',
      'fresh tattoo look',
    ],
  },
};

export function styleDnaFor(key: string): StyleDNA {
  return STYLE_DNA[key] ?? STYLE_DNA['hairstroke'];
}

export function styleDnaText(
  key: string,
  preferences?: UserSubjectivePreferences,
  service: string = 'eyebrows',
): string {
  const s = styleDnaFor(key);
  const additions: string[] = [];

  if (service === 'lips') {
    if (preferences?.dailyMakeup === 'bold') {
      additions.push('dense pigment saturation, crisp clean vermilion edge');
    } else if (preferences?.dailyMakeup === 'natural') {
      additions.push('sheer watercolor tint, ultra-natural breathable finish, visible lip texture');
    } else if (preferences?.dailyMakeup === 'soft') {
      additions.push('delicate soft daywear tint, seamless melt into native tone');
    }

    if (preferences?.density === 'dense') {
      additions.push('full luxurious velvet volume');
    } else if (preferences?.density === 'fluffy') {
      additions.push('airy sheer wash, light translucent glow');
    }
  } else if (service === 'eyeliner') {
    if (preferences?.dailyMakeup === 'bold') {
      additions.push('denser carbon fill at lash roots, defined elegant flick');
    } else if (preferences?.dailyMakeup === 'natural') {
      additions.push('invisible tightline, ultra-natural depth only');
    } else if (preferences?.dailyMakeup === 'soft') {
      additions.push('soft diffused edge, gentle daywear definition');
    }

    if (preferences?.density === 'dense') {
      additions.push('denser lash-base fill, richer black');
    } else if (preferences?.density === 'fluffy') {
      additions.push('light sparse micro pigment, barely-there line');
    }
  } else if (service !== 'removal') {
    if (preferences?.dailyMakeup === 'bold') {
      additions.push('defined arch, dense pigment saturation, crisp clean edge');
    } else if (preferences?.dailyMakeup === 'natural') {
      additions.push('sparse front, very soft strokes, no harsh lines, ultra-natural breathable finish, visible skin pores');
    } else if (preferences?.dailyMakeup === 'soft') {
      additions.push('delicate soft daywear tint, medium gradient transitions, seamless skin melt');
    }

    if (preferences?.browShape === 'defined') {
      additions.push('structured clean border within natural margin, neat elegant arch');
    } else if (preferences?.browShape === 'natural') {
      additions.push('preserve natural irregular contour, follow exact native geometry, organic asymmetry');
    }

    if (preferences?.density === 'dense') {
      additions.push('higher density with subtle under-shading, full luxurious volume');
    } else if (preferences?.density === 'fluffy') {
      additions.push('airy feather spacing between micro strokes, light and separated keratin texture with visible skin gaps');
    }
  }

  if (preferences?.lipLook) {
    additions.push(`lip_preference=${preferences.lipLook}`);
  }
  if (preferences?.eyelinerLook) {
    additions.push(`eyeliner_preference=${preferences.eyelinerLook}`);
  }

  const customDna = additions.length > 0 ? `user_preferences=[${additions.join(', ')}]` : '';
  const mergedForbidden = Array.from(new Set([...GLOBAL_NEGATIVE_CONSTRAINTS, ...s.forbidden]));

  // ترتیب عمدی: هویت سبک اول (متمایزکننده)، محدودیت‌های سلبی بعد
  return [
    `STYLE_DNA key=${s.key}`,
    `technique=${s.technique}`,
    s.front ? `front=${s.front}` : '',
    s.body ? `body=${s.body}` : '',
    s.tail ? `tail=${s.tail}` : '',
    s.density ? `density=${s.density}` : '',
    s.texture ? `texture=${s.texture}` : '',
    customDna,
    `STRICT_NEGATIVE_CONSTRAINTS: AVOID AT ALL COSTS [${GLOBAL_NEGATIVE_CONSTRAINTS.join(', ')}]`,
    `forbidden=${mergedForbidden.join(', ')}`,
  ]
    .filter(Boolean)
    .join('; ');
}
