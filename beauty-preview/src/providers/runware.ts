/**
 * src/providers/runware.ts
 * ---------------------------------------------------------------------------
 * پروایدر ۱ — Runware  (https://runware.ai/docs)
 *
 * نکتهٔ مهم: Runware با فرمت OpenAI کار نمی‌کند. ورودی همیشه یک «آرایهٔ
 * JSON» از تسک‌هاست و خروجی در `data` (آرایه) برمی‌گردد.
 *
 * فرایند دو مرحله‌ای:
 *   الف) taskType = "imageUpload"   → خروجی: imageUUID
 *   ب)  taskType = "imageInference" → ورودی: seedImage = imageUUID، خروجی: imageURL
 * ---------------------------------------------------------------------------
 */

import {
  ProviderError,
  extractApiError,
  timeoutFor,
  timeoutSignal,
} from './http';
import type { Provider, ProviderInput } from './types';

const DEFAULT_ENDPOINT = 'https://api.runware.ai/v1';
const DEFAULT_MODEL = 'bfl:flux-1-kontext-pro@1';

/** آدرس API (قابل تغییر با RUNWARE_API_URL برای پروکسی/تست) */
function endpoint(): string {
  return (process.env.RUNWARE_API_URL ?? '').trim() || DEFAULT_ENDPOINT;
}

/** مدل (قابل تغییر با RUNWARE_MODEL) */
function model(): string {
  return (process.env.RUNWARE_MODEL ?? '').trim() || DEFAULT_MODEL;
}

interface RunwareTask {
  taskType?: string;
  taskUUID?: string;
  imageUUID?: string;
  imageURL?: string;
  imageDataURI?: string;
  imageBase64Data?: string;
}

/** پاسخ Runware یا `{ data: [...] }` است یا مستقیماً آرایه */
function readTasks(payload: unknown): RunwareTask[] {
  if (Array.isArray(payload)) return payload as RunwareTask[];
  if (payload && typeof payload === 'object') {
    const data = (payload as Record<string, unknown>).data;
    if (Array.isArray(data)) return data as RunwareTask[];
  }
  return [];
}

async function callRunware(
  body: unknown[],
  apiKey: string,
  stage: string,
  timeoutMs: number,
): Promise<unknown> {
  const { signal, done } = timeoutSignal(timeoutMs);
  try {
    const res = await fetch(endpoint(), {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal,
      cache: 'no-store',
    });

    const raw = await res.text();
    let payload: unknown = null;
    try {
      payload = raw ? JSON.parse(raw) : null;
    } catch {
      payload = null;
    }

    if (!res.ok) {
      throw new ProviderError(
        `Runware ${stage} ناموفق بود (HTTP ${res.status})`,
        extractApiError(payload) || raw.slice(0, 300),
      );
    }

    const apiError = extractApiError(payload);
    if (apiError && readTasks(payload).length === 0) {
      throw new ProviderError(`Runware ${stage} خطا داد`, apiError);
    }

    return payload;
  } catch (error) {
    if (error instanceof ProviderError) throw error;
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ProviderError('Runware: زمان انتظار به پایان رسید');
    }
    throw new ProviderError(
      `Runware ${stage} ناموفق بود`,
      error instanceof Error ? error.message : String(error),
    );
  } finally {
    done();
  }
}

/** ساخت UUID v4 (بدون وابستگی اضافه) */
function uuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const rand = (Math.random() * 16) | 0;
    const value = char === 'x' ? rand : (rand & 0x3) | 0x8;
    return value.toString(16);
  });
}

export const runwareProvider: Provider = {
  id: 'runware',
  label: 'Runware',
  envKey: 'RUNWARE_API_KEY',

  async generate(input: ProviderInput): Promise<string> {
    const { prompt, image } = input;
    const timeoutMs = timeoutFor(input);
    const apiKey = (process.env.RUNWARE_API_KEY ?? '').trim();
    if (!apiKey) throw new ProviderError('Runware: کلید API تنظیم نشده است');

    const uploadTaskUUID = uuid();

    /* ---------- مرحلهٔ الف: آپلود تصویر ---------- */
    const uploadPayload = await callRunware(
      [
        {
          taskType: 'imageUpload',
          taskUUID: uploadTaskUUID,
          image: image.dataUri,
        },
      ],
      apiKey,
      'imageUpload',
      timeoutMs,
    );

    const uploadTasks = readTasks(uploadPayload);
    const uploaded =
      uploadTasks.find((task) => task?.taskType === 'imageUpload' && task?.imageUUID) ??
      uploadTasks.find((task) => Boolean(task?.imageUUID));

    const seedImage = uploaded?.imageUUID;
    if (!seedImage) {
      throw new ProviderError(
        'Runware: imageUUID دریافت نشد',
        JSON.stringify(uploadPayload).slice(0, 300),
      );
    }

    /* ---------- مرحلهٔ ب: تولید تصویر ---------- */
    const inferenceUUID = uuid();
    const inferencePayload = await callRunware(
      [
        {
          taskType: 'imageInference',
          taskUUID: inferenceUUID,
          model: model(),
          positivePrompt: prompt,
          seedImage,
          width: Number(process.env.RUNWARE_WIDTH ?? 1024),
          height: Number(process.env.RUNWARE_HEIGHT ?? 1024),
          outputType: 'URL',
          outputFormat: 'jpg',
          numberResults: 1,
        },
      ],
      apiKey,
      'imageInference',
      timeoutMs,
    );

    const inferenceTasks = readTasks(inferencePayload);
    const result =
      inferenceTasks.find((task) => task?.taskType === 'imageInference') ?? inferenceTasks[0];

    if (result?.imageURL) return result.imageURL;
    if (result?.imageDataURI) return result.imageDataURI;
    if (result?.imageBase64Data) return `data:image/jpeg;base64,${result.imageBase64Data}`;

    throw new ProviderError(
      'Runware: هیچ تصویری دریافت نشد',
      JSON.stringify(inferencePayload).slice(0, 300),
    );
  },
};

export const __runwareInternals = { readTasks, endpoint, model };
