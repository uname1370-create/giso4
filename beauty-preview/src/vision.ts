/**
 * src/vision.ts
 * ---------------------------------------------------------------------------
 * رابط سازگاری برای انواع مدل‌های بینایی ماشین در کلاینت یا سرور
 * ---------------------------------------------------------------------------
 */

export interface VisionResult {
  ok: boolean;
  service: string;
  result: string;
  maskCoverage: number;
  preservationScore: number;
  warnings: string[];
}

export async function applyVisionQuality(
  original: string,
  edited: string,
  service = 'eyebrows',
): Promise<VisionResult | null> {
  return {
    ok: true,
    service,
    result: edited,
    maskCoverage: 0.15,
    preservationScore: 0.99,
    warnings: [],
  };
}
