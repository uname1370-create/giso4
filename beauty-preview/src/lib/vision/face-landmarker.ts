'use client';

/**
 * src/lib/vision/face-landmarker.ts
 * ---------------------------------------------------------------------------
 * سینگلتون کلاینتی MediaPipe FaceLandmarker — اجرای ۱۰۰٪ در مرورگر کاربر
 * بدون مصرف رم/سی‌پی‌یو سرور. بارگذاری تنبل (lazy) و فقط در سمت کلاینت.
 * ---------------------------------------------------------------------------
 */

import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';

let landmarkerPromise: Promise<FaceLandmarker> | null = null;

/** ساخت (یک‌بار) و برگرداندن نمونه FaceLandmarker در حالت IMAGE. */
export function getFaceLandmarker(): Promise<FaceLandmarker> {
  if (!landmarkerPromise) {
    landmarkerPromise = (async () => {
      const vision = await FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm',
      );
      return await FaceLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath:
            'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
          delegate: 'GPU',
        },
        runningMode: 'IMAGE',
        numFaces: 1,
        minFaceDetectionConfidence: 0.4,
        minFacePresenceConfidence: 0.4,
        minTrackingConfidence: 0.4,
      });
    })();
  }
  return landmarkerPromise;
}
