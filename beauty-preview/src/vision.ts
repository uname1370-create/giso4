import { ProviderError, timeoutSignal } from './providers/http';

const DEFAULT_TIMEOUT_MS = 45_000;

function enabled(): boolean {
  const raw = (process.env.VISION_ENGINE_ENABLED ?? '').trim().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'on';
}

function url(): string {
  return (process.env.VISION_ENGINE_URL ?? 'http://127.0.0.1:8010').trim().replace(/\/$/, '');
}

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
  if (!enabled()) return null;
  const { signal, done } = timeoutSignal(
    Number(process.env.VISION_ENGINE_TIMEOUT_MS) > 1000
      ? Number(process.env.VISION_ENGINE_TIMEOUT_MS)
      : DEFAULT_TIMEOUT_MS,
  );
  try {
    const response = await fetch(url() + '/v1/process', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ service, original, edited }),
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
          : raw.slice(0, 300);
      throw new ProviderError('Vision Engine failed', detail);
    }
    if (!payload || typeof payload !== 'object' || typeof (payload as Record<string, unknown>).result !== 'string') {
      throw new ProviderError('Vision Engine returned an invalid result');
    }
    return payload as VisionResult;
  } catch (error) {
    if (error instanceof ProviderError) throw error;
    if (error instanceof Error && error.name === 'AbortError') throw new ProviderError('Vision Engine timeout');
    throw new ProviderError('Vision Engine connection failed', error instanceof Error ? error.message : String(error));
  } finally {
    done();
  }
}
