/**
 * src/brow-shapes.ts
 * ---------------------------------------------------------------------------
 * تولید تصاویر SVG سادهٔ ابرو (بدون چهره و بدون پوست — فقط شکل ابرو روی
 * پس‌زمینهٔ شفاف) برای ۴ سبک میکروبلیدینگ:
 *
 *   hairstroke  → هایر استروک طبیعی (فقط تار مو، بدون سایه)
 *   feather     → فدر براو (ابتدای محو، تارهای نازک)
 *   ombre       → اومبره پودری (گرادیان محو، بدون تار)
 *   combination → کامبینیشن (تار مو در ابتدا + پودر پررنگ در دم)
 *
 * این ماژول تنها منبع حقیقت (single source of truth) هندسهٔ ابروها است و
 * هم در کارت‌های انتخاب سبک و هم در «حالت نمایشی» (demo) استفاده می‌شود.
 * خروجی قطعی (deterministic) است تا تصویر در هر رندر یکسان بماند.
 * ---------------------------------------------------------------------------
 */

export type BrowStyleKey = 'hairstroke' | 'feather' | 'ombre' | 'combination';

export interface Point {
  x: number;
  y: number;
}

/** فضای ترسیم یک ابرو */
export const BROW_VIEWBOX = { width: 420, height: 190 } as const;

/** اندازهٔ SVG دوتایی (ابروی چپ و راست) در حالت نمایشی */
export const DEMO_OVERLAY_SIZE = {
  width: BROW_VIEWBOX.width * 2 + 60,
  height: BROW_VIEWBOX.height,
} as const;

type CubicSegment = [Point, Point, Point, Point];

/* -------------------------------------------------------------------------- */
/* ۱) هندسهٔ پایهٔ ابرو                                                       */
/* -------------------------------------------------------------------------- */

/** لبهٔ بالایی: از ابتدای ابرو (سمت بینی) تا دم ابرو */
const TOP_SEGMENTS: CubicSegment[] = [
  [{ x: 48, y: 122 }, { x: 78, y: 92 }, { x: 152, y: 58 }, { x: 224, y: 54 }],
  [{ x: 224, y: 54 }, { x: 292, y: 51 }, { x: 342, y: 64 }, { x: 372, y: 88 }],
];

/** لبهٔ پایینی: از دم ابرو برمی‌گردد تا ابتدای ابرو (برای بستن مسیر) */
const BOTTOM_SEGMENTS: CubicSegment[] = [
  [{ x: 372, y: 88 }, { x: 356, y: 99 }, { x: 312, y: 96 }, { x: 262, y: 100 }],
  [{ x: 262, y: 100 }, { x: 196, y: 106 }, { x: 126, y: 118 }, { x: 76, y: 134 }],
  [{ x: 76, y: 134 }, { x: 58, y: 141 }, { x: 42, y: 134 }, { x: 48, y: 122 }],
];

function cubicPoint([p0, p1, p2, p3]: CubicSegment, t: number): Point {
  const mt = 1 - t;
  const a = mt * mt * mt;
  const b = 3 * mt * mt * t;
  const c = 3 * mt * t * t;
  const d = t * t * t;
  return {
    x: a * p0.x + b * p1.x + c * p2.x + d * p3.x,
    y: a * p0.y + b * p1.y + c * p2.y + d * p3.y,
  };
}

/** نمونه‌گیری یکنواخت از یک زنجیرهٔ بزیه (t بین ۰ و ۱) */
function sampleChain(segments: CubicSegment[], t: number): Point {
  const clamped = Math.min(Math.max(t, 0), 1);
  const scaled = clamped * segments.length;
  const index = Math.min(Math.floor(scaled), segments.length - 1);
  return cubicPoint(segments[index], scaled - index);
}

/**
 * نکتهٔ مهم جهت پیمایش:
 * TOP_SEGMENTS از سر ابرو (سمت بینی) به دم می‌رود، اما BOTTOM_SEGMENTS برای
 * بستن مسیر، از دم به سر برمی‌گردد. پس برای مقایسهٔ درست دو لبه در نقطهٔ t،
 * پارامتر لبهٔ پایین باید معکوس شود.
 */
function topEdgeAt(t: number): Point {
  return sampleChain(TOP_SEGMENTS, t);
}

function bottomEdgeAt(t: number): Point {
  return sampleChain(BOTTOM_SEGMENTS, 1 - t);
}

/** بخش «C ...» یک زنجیره (بدون نقطهٔ شروع) */
function curvesOnly(segments: CubicSegment[]): string {
  return segments
    .map(([, c1, c2, end]) => `C ${c1.x} ${c1.y} ${c2.x} ${c2.y} ${end.x} ${end.y}`)
    .join(' ');
}

const TOP_HEAD = TOP_SEGMENTS[0][0];

/** مسیر بستهٔ کامل ابرو */
export function browOutlinePath(): string {
  return `M ${TOP_HEAD.x} ${TOP_HEAD.y} ${curvesOnly(TOP_SEGMENTS)} ${curvesOnly(BOTTOM_SEGMENTS)} Z`;
}

/* -------------------------------------------------------------------------- */
/* ۲) تارهای مو (hair strokes)                                                */
/* -------------------------------------------------------------------------- */

/** مولد اعداد تصادفی قطعی (mulberry32) — تصویر همیشه یکسان می‌ماند */
function seededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function seedOf(text: string): number {
  let hash = 21;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 33 + text.charCodeAt(i)) % 100000;
  }
  return hash + 7;
}

interface StrandOptions {
  /** ضخامت خط تار */
  width: number;
  /** طول تار به‌صورت کسری از ضخامت موضعی ابرو */
  minLength: number;
  maxLength: number;
  /** شروع تار از چه ارتفاعی (کسری از ضخامت) */
  minStart: number;
  maxStart: number;
  /** زاویهٔ تار نسبت به راستای عمودی ابرو، به رادیان (به سمت دم ابرو) */
  minAngle: number;
  maxAngle: number;
}

/**
 * تارهای موی کوتاه و مورب می‌سازد: از لبهٔ پایین ابرو شروع می‌شوند و به سمت
 * بالا و دم ابرو کشیده می‌شوند (جهت طبیعی رشد موی ابرو). انحنای هر تار ملایم
 * است و تارها با clipPath درون شکل ابرو بریده می‌شوند.
 *
 * طول تار متناسب با ضخامت موضعی ابرو است؛ بنابراین در ابتدای ضخیم کوتاه و
 * فشرده و در دم نازک، ریز و کشیده به سمت دم دیده می‌شود.
 */
function strandGroup(
  seed: string,
  from: number,
  to: number,
  count: number,
  options: StrandOptions,
): string {
  const random = seededRandom(seedOf(seed));
  const items: string[] = [];

  for (let i = 0; i < count; i += 1) {
    const ratio = count === 1 ? 0.5 : i / (count - 1);
    const t = Math.min(Math.max(from + (to - from) * ratio + (random() - 0.5) * 0.02, 0.01), 0.99);

    const bottom = bottomEdgeAt(t);
    const top = topEdgeAt(t);

    const vx = top.x - bottom.x;
    const vy = top.y - bottom.y;
    const thickness = Math.hypot(vx, vy) || 1;
    const ux = vx / thickness; // راستای «بالا»ی موضعی ابرو
    const uy = vy / thickness;

    const startRatio = options.minStart + random() * (options.maxStart - options.minStart);
    const sx = bottom.x + ux * thickness * startRatio;
    const sy = bottom.y + uy * thickness * startRatio;

    // طول تار نسبت به ضخامت موضعی (در دم نازک که ضخامت کم است، تار کوتاه می‌شود)
    const lengthRatio = options.minLength + random() * (options.maxLength - options.minLength);
    const length = lengthRatio * thickness;
    // تارهای نزدیک دم ابرو کمی بلندتر و خوابیده‌تر می‌شوند
    const angle =
      (options.minAngle + random() * (options.maxAngle - options.minAngle)) * (0.75 + 0.5 * t);

    const ex = sx + ux * length * Math.cos(angle) + length * Math.sin(angle);
    const ey = sy + uy * length * Math.cos(angle);

    // انحنای ملایم تار (به سمت پایین قوس می‌گیرد)
    const bow = (0.1 + random() * 0.16) * thickness;
    const cx = (sx + ex) / 2 + uy * bow * 0.25;
    const cy = (sy + ey) / 2 - ux * bow * 0.25;

    const width = options.width * (0.85 + random() * 0.3);
    items.push(
      `<path d="M ${sx.toFixed(1)} ${sy.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${ex.toFixed(
        1,
      )} ${ey.toFixed(1)}" stroke-width="${width.toFixed(2)}" />`,
    );
  }

  return items.join('');
}

/* -------------------------------------------------------------------------- */
/* ۳) ابزار رنگ                                                               */
/* -------------------------------------------------------------------------- */

function normalizeHex(hex: string): string {
  const clean = hex.replace('#', '').trim();
  if (clean.length === 3) return clean.split('').map((c) => c + c).join('');
  return clean.length >= 6 ? clean.slice(0, 6) : '8B6914';
}

function channels(hex: string): { r: number; g: number; b: number } {
  const num = parseInt(normalizeHex(hex), 16);
  if (!Number.isFinite(num)) return { r: 139, g: 105, b: 20 };
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
}

/** روشن/تیره کردن رنگ؛ amount مثبت = روشن‌تر */
export function shiftColor(hex: string, amount: number): string {
  const { r, g, b } = channels(hex);
  const clamp = (value: number) => Math.max(0, Math.min(255, Math.round(value)));
  return `#${[clamp(r + amount), clamp(g + amount), clamp(b + amount)]
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')}`;
}

/** رنگ با شفافیت */
export function rgbaColor(hex: string, alpha: number): string {
  const { r, g, b } = channels(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/* -------------------------------------------------------------------------- */
/* ۴) سازندهٔ markup                                                          */
/* -------------------------------------------------------------------------- */

export interface BrowMarkupOptions {
  /** رنگ اصلی ابرو (hex) */
  color: string;
  /** پیشوند یکتا برای idهای داخلی (وقتی چند SVG در یک صفحه هستند) */
  uid: string;
}

/** `defs` (گرادیان/فیلتر/clipPath) + `body` (شکل ابرو) */
export function buildBrowMarkup(
  style: BrowStyleKey,
  { color, uid }: BrowMarkupOptions,
): { defs: string; body: string } {
  const outline = browOutlinePath();
  const darker = shiftColor(color, -52);
  const lighter = shiftColor(color, 46);

  const gradientId = `grad-${uid}`;
  const fadeId = `fade-${uid}`;
  const softId = `soft-${uid}`;
  const clipId = `clip-${uid}`;

  const defs = `
    <linearGradient id="${gradientId}" x1="0" y1="0.15" x2="1" y2="0.75">
      <stop offset="0%" stop-color="${color}" stop-opacity="0.18" />
      <stop offset="30%" stop-color="${color}" stop-opacity="0.62" />
      <stop offset="72%" stop-color="${darker}" stop-opacity="0.9" />
      <stop offset="100%" stop-color="${darker}" stop-opacity="0.95" />
    </linearGradient>
    <linearGradient id="${fadeId}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="${color}" stop-opacity="0.04" />
      <stop offset="40%" stop-color="${color}" stop-opacity="0.34" />
      <stop offset="100%" stop-color="${darker}" stop-opacity="0.66" />
    </linearGradient>
    <filter id="${softId}" x="-20%" y="-35%" width="140%" height="170%">
      <feGaussianBlur stdDeviation="1.15" />
    </filter>
    <clipPath id="${clipId}"><path d="${outline}" /></clipPath>`;

  /** تارها با clipPath درونی ابرو بریده می‌شوند */
  const strands = (inner: string, opacity: number): string =>
    inner
      ? `<g clip-path="url(#${clipId})" fill="none" stroke="${color}" stroke-linecap="round" opacity="${opacity}">${inner}</g>`
      : '';

  let body = '';
  switch (style) {
    // ۱) هایر استروک طبیعی — فقط تار مو، خیلی نازک و کشیده
    case 'hairstroke': {
      const strokes = strandGroup(`${uid}-hs`, 0.02, 0.96, 32, {
        width: 1.15,
        minLength: 0.45,
        maxLength: 0.72,
        minStart: 0.08,
        maxStart: 0.38,
        minAngle: 0.3,
        maxAngle: 0.62,
      });
      body = `
      <path d="${outline}" fill="${rgbaColor(color, 0.06)}" />
      <path d="${outline}" fill="none" stroke="${rgbaColor(color, 0.35)}" stroke-width="1.1" />
      ${strands(strokes, 0.9)}`;
      break;
    }

    // ۲) فدر براو — ابتدای محو و پرمانند، دم نازک و تیره‌تر
    case 'feather': {
      const strokes = strandGroup(`${uid}-fb`, 0.0, 0.98, 44, {
        width: 0.95,
        minLength: 0.4,
        maxLength: 0.68,
        minStart: 0.06,
        maxStart: 0.42,
        minAngle: 0.4,
        maxAngle: 0.78,
      });
      body = `
      <path d="${outline}" fill="url(#${fadeId})" />
      <g filter="url(#${softId})">${strands(strokes, 0.68)}</g>`;
      break;
    }

    // ۳) اومبره پودری — پودری و مخملی، ابتدای روشن و دم تیره، بدون تار مو
    case 'ombre':
      body = `
      <g filter="url(#${softId})">
        <path d="${outline}" fill="url(#${gradientId})" />
      </g>
      <path d="${outline}" fill="${rgbaColor(color, 0.1)}" />`;
      break;

    // ۴) کامبینیشن — تار مو در ابتدا + سایهٔ پودری پررنگ در دم
    case 'combination': {
      const strokes = strandGroup(`${uid}-cb`, 0.02, 0.54, 24, {
        width: 1.15,
        minLength: 0.42,
        maxLength: 0.66,
        minStart: 0.1,
        maxStart: 0.4,
        minAngle: 0.35,
        maxAngle: 0.7,
      });
      body = `
      <path d="${outline}" fill="url(#${gradientId})" opacity="0.5" />
      <g clip-path="url(#${clipId})" filter="url(#${softId})">
        <rect x="0" y="0" width="${BROW_VIEWBOX.width}" height="${BROW_VIEWBOX.height}" fill="url(#${gradientId})" opacity="0.55" />
      </g>
      ${strands(strokes, 0.92)}`;
      break;
    }
  }

  return { defs, body };
}

export interface BrowSvgOptions {
  /** رنگ اصلی ابرو (hex) — پیش‌فرض طلایی-قهوه‌ای */
  color?: string;
  /** شناسهٔ یکتا برای idهای داخلی */
  uid?: string;
}

/** تصویر SVG یک ابرو (پس‌زمینهٔ شفاف، فقط شکل ابرو) */
export function buildBrowSvg(style: BrowStyleKey, options: BrowSvgOptions = {}): string {
  const color = options.color ?? '#C7A76A';
  const uid = options.uid ?? style;
  const { defs, body } = buildBrowMarkup(style, { color, uid });

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${BROW_VIEWBOX.width} ${BROW_VIEWBOX.height}" width="${BROW_VIEWBOX.width}" height="${BROW_VIEWBOX.height}" role="img" aria-label="طرح ابرو">
  <defs>${defs}</defs>
  ${body}
</svg>`;
}

/** تبدیل SVG به data URI قابل استفاده در تگ img */
export function svgToDataUri(svg: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

/** تصویر پیش‌نمایش (placeholder) کارت یک سبک ابرو */
export function browPreviewUri(style: BrowStyleKey, color = '#C7A76A'): string {
  return svgToDataUri(buildBrowSvg(style, { color, uid: `card-${style}` }));
}

/**
 * SVG دوتایی (ابروی چپ و راست) برای «حالت نمایشی» محلی؛
 * روی عکس چهره کشیده می‌شود و نسبت عرض به ارتفاع حدود ۴.۷:۱ دارد.
 */
export function buildDemoOverlaySvg(style: BrowStyleKey, color: string): string {
  const { defs, body } = buildBrowMarkup(style, { color, uid: `demo-${style}` });
  const totalWidth = DEMO_OVERLAY_SIZE.width;
  const height = DEMO_OVERLAY_SIZE.height;

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${totalWidth} ${height}" width="${totalWidth}" height="${height}">
  <defs>${defs}</defs>
  <g id="brow-shape">${body}</g>
  <use href="#brow-shape" transform="translate(${totalWidth} 0) scale(-1 1)" />
</svg>`;
}
