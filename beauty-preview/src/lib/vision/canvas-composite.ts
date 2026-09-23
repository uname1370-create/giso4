/**
 * src/lib/vision/canvas-composite.ts
 * ---------------------------------------------------------------------------
 * کامپوزیت عکاسی (Hard Composite) در مرورگر: ساخت ماسک دو مرحله‌ای Feathered
 * از روی لندمارک‌ها و ترکیب ناحیه‌ای تصویر AI روی عکس اصلی با Canvas/GPU.
 * ---------------------------------------------------------------------------
 */

import { FeatureLandmarks, Point2D } from './landmarks-extractor';

export type ServiceTarget = 'eyebrows' | 'lips' | 'eyeliner' | 'removal';

export interface CompositeOptions {
  featherRadius?: number;
  opacity?: number;
  blendMode?: GlobalCompositeOperation;
  watermarkEnabled?: boolean;
}

export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load image: ${src.substring(0, 50)}...`));
    img.src = src;
  });
}

function drawPolygon(ctx: CanvasRenderingContext2D, points: Point2D[]) {
  if (points.length < 3) return;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i++) {
    ctx.lineTo(points[i].x, points[i].y);
  }
  ctx.closePath();
}

/** ماسک دو مرحله‌ای: لایه بیرونی نرم + هسته داخلی شارپ برای لبه طبیعی. */
export function createDualStageFeatheredMask(
  width: number,
  height: number,
  features: FeatureLandmarks,
  target: ServiceTarget,
  options: { featherRadius?: number } = {},
): HTMLCanvasElement {
  const baseDim = Math.max(width, height);
  const scaleRatio = Math.max(0.6, baseDim / 1024);
  const defaultRadius = target === 'eyeliner' ? 3 * scaleRatio : 9 * scaleRatio;
  const featherRadius = Math.round(options.featherRadius ?? defaultRadius);

  const coreCanvas = document.createElement('canvas');
  coreCanvas.width = width;
  coreCanvas.height = height;
  const coreCtx = coreCanvas.getContext('2d');
  if (!coreCtx) throw new Error('Could not get core canvas context');

  coreCtx.fillStyle = '#FFFFFF';

  if (target === 'eyebrows') {
    drawPolygon(coreCtx, features.leftEyebrow);
    coreCtx.fill();
    drawPolygon(coreCtx, features.rightEyebrow);
    coreCtx.fill();
  } else if (target === 'lips') {
    drawPolygon(coreCtx, features.lipsOuter);
    coreCtx.fill();

    if (features.lipsInner.length >= 3) {
      coreCtx.globalCompositeOperation = 'destination-out';
      drawPolygon(coreCtx, features.lipsInner);
      coreCtx.fill();
      coreCtx.globalCompositeOperation = 'source-over';
    }
  } else if (target === 'eyeliner') {
    coreCtx.lineWidth = Math.max(4, Math.round(5 * scaleRatio));
    coreCtx.strokeStyle = '#FFFFFF';
    coreCtx.lineCap = 'round';
    coreCtx.lineJoin = 'round';

    const drawLine = (pts: Point2D[]) => {
      if (pts.length < 2) return;
      coreCtx.beginPath();
      coreCtx.moveTo(pts[0].x, pts[0].y);
      for (let i = 1; i < pts.length; i++) {
        coreCtx.lineTo(pts[i].x, pts[i].y);
      }
      coreCtx.stroke();
    };

    drawLine(features.leftEyeUpper);
    drawLine(features.rightEyeUpper);
  }

  const finalMask = document.createElement('canvas');
  finalMask.width = width;
  finalMask.height = height;
  const fCtx = finalMask.getContext('2d');
  if (!fCtx) throw new Error('Could not get final mask context');

  fCtx.filter = `blur(${featherRadius * 1.5}px)`;
  fCtx.globalAlpha = 0.45;
  fCtx.drawImage(coreCanvas, 0, 0);

  fCtx.filter = `blur(${Math.max(2, Math.round(featherRadius * 0.6))}px)`;
  fCtx.globalAlpha = 0.85;
  fCtx.drawImage(coreCanvas, 0, 0);

  fCtx.filter = 'none';
  fCtx.globalAlpha = 1.0;

  return finalMask;
}

/** ترکیب نهایی: بافت پوست (soft-light) + پیگمنت (source-over) + واترمارک. */
export function applyPhotorealisticHardComposite(
  baseImage: HTMLImageElement | HTMLCanvasElement,
  generatedImage: HTMLImageElement | HTMLCanvasElement,
  maskCanvas: HTMLCanvasElement,
  _features: FeatureLandmarks,
  options: CompositeOptions = {},
): HTMLCanvasElement {
  const width = baseImage.width;
  const height = baseImage.height;

  const outputCanvas = document.createElement('canvas');
  outputCanvas.width = width;
  outputCanvas.height = height;
  const ctx = outputCanvas.getContext('2d');
  if (!ctx) throw new Error('Could not get output canvas context');

  ctx.drawImage(baseImage, 0, 0, width, height);

  const isolatedOverlay = document.createElement('canvas');
  isolatedOverlay.width = width;
  isolatedOverlay.height = height;
  const oCtx = isolatedOverlay.getContext('2d');
  if (!oCtx) throw new Error('Could not get overlay context');

  oCtx.drawImage(generatedImage, 0, 0, width, height);
  oCtx.globalCompositeOperation = 'destination-in';
  oCtx.drawImage(maskCanvas, 0, 0, width, height);

  ctx.save();
  ctx.globalCompositeOperation = 'soft-light';
  ctx.globalAlpha = 0.55;
  ctx.drawImage(isolatedOverlay, 0, 0, width, height);
  ctx.restore();

  ctx.save();
  ctx.globalCompositeOperation = options.blendMode ?? 'source-over';
  ctx.globalAlpha = options.opacity ?? 0.88;
  ctx.drawImage(isolatedOverlay, 0, 0, width, height);
  ctx.restore();

  if (options.watermarkEnabled) {
    ctx.save();
    const fontSize = Math.max(12, Math.round(width * 0.024));
    ctx.font = `600 ${fontSize}px sans-serif`;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.45)';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
    ctx.shadowColor = 'rgba(0, 0, 0, 0.7)';
    ctx.shadowBlur = 4;
    ctx.fillText('Powered by Giso AI', 16, height - 16);
    ctx.restore();
  }

  return outputCanvas;
}

/** نقطه ورود یک‌مرحله‌ای: لود تصاویر ← ماسک ← کامپوزیت ← خروجی data URI. */
export async function executeClientComposite(
  baseSrc: string,
  generatedSrc: string,
  features: FeatureLandmarks,
  serviceTarget: ServiceTarget,
  options?: CompositeOptions,
): Promise<string> {
  const [baseImg, genImg] = await Promise.all([loadImage(baseSrc), loadImage(generatedSrc)]);

  const mask = createDualStageFeatheredMask(baseImg.width, baseImg.height, features, serviceTarget, {
    featherRadius: options?.featherRadius,
  });

  const resultCanvas = applyPhotorealisticHardComposite(baseImg, genImg, mask, features, options);

  return resultCanvas.toDataURL('image/jpeg', 0.94);
}
