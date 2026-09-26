/**
 * src/lib/vision/landmarks-extractor.ts
 * ---------------------------------------------------------------------------
 * استخراج نواحی معنادار چهره (ابروها، لب، خط مژه) از مش ۴۷۸ نقطه‌ای
 * MediaPipe و نرمال‌سازی به مختصات پیکسلی تصویر مبدا.
 * ---------------------------------------------------------------------------
 */

import type { NormalizedLandmark } from '@mediapipe/tasks-vision';

export interface Point2D {
  x: number;
  y: number;
}

export interface FeatureLandmarks {
  leftEyebrow: Point2D[];
  rightEyebrow: Point2D[];
  lipsOuter: Point2D[];
  lipsInner: Point2D[];
  leftEyeUpper: Point2D[];
  rightEyeUpper: Point2D[];
}

/** ایندکس‌های استاندارد FaceMesh برای هر ناحیه. */
const LEFT_EYEBROW = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46];
const RIGHT_EYEBROW = [296, 334, 293, 300, 276, 283, 282, 295, 285, 336];
const LIPS_OUTER = [
  61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95,
];
const LIPS_INNER = [
  78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95,
];
const LEFT_EYE_UPPER = [246, 161, 160, 159, 158, 157, 173];
const RIGHT_EYE_UPPER = [466, 388, 387, 386, 385, 384, 398];

function toPixels(
  indices: number[],
  landmarks: NormalizedLandmark[],
  width: number,
  height: number,
): Point2D[] {
  return indices
    .filter((i) => i >= 0 && i < landmarks.length)
    .map((i) => ({ x: landmarks[i].x * width, y: landmarks[i].y * height }));
}

/** تبدیل لندمارک‌های نرمال‌شده به مختصات پیکسلی قابل استفاده در Canvas. */
export function extractFeatureLandmarks(
  landmarks: NormalizedLandmark[],
  width: number,
  height: number,
): FeatureLandmarks {
  return {
    leftEyebrow: toPixels(LEFT_EYEBROW, landmarks, width, height),
    rightEyebrow: toPixels(RIGHT_EYEBROW, landmarks, width, height),
    lipsOuter: toPixels(LIPS_OUTER, landmarks, width, height),
    lipsInner: toPixels(LIPS_INNER, landmarks, width, height),
    leftEyeUpper: toPixels(LEFT_EYE_UPPER, landmarks, width, height),
    rightEyeUpper: toPixels(RIGHT_EYE_UPPER, landmarks, width, height),
  };
}
