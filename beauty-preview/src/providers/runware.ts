/**
 * src/providers/runware.ts
 * ---------------------------------------------------------------------------
 * Provider 1 — Runware
 *
 * Runware image editing uses one imageInference task with
 * inputs.referenceImages. The provider tries models from cheapest to
 * most expensive and moves to the next model only when the current one
 * fails. This keeps the existing provider-level fallback architecture intact.
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

/**
 * Ordered by current Runware reference-to-image example cost:
 * Qwen-Image-Edit  ~$0.0045
 * P-Image-Edit     ~$0.0088
 * FLUX.1 Kontext Dev ~$0.013
 * FLUX.1 Kontext Pro $0.04
 */
const DEFAULT_MODELS = [
  'runware:108@20',
  'prunaai:2@1',
  'runware:106@1',
  'bfl:3@1',
] as const;

function endpoint(): string {
  return (process.env.RUNWARE_API_URL ?? '').trim() || DEFAULT_ENDPOINT;
}

function models(): string[] {
  const configured = (process.env.RUNWARE_MODELS ?? '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);

  return configured.length > 0 ? configured : [...DEFAULT_MODELS];
}

interface RunwareTask {
  taskType?: string;
  taskUUID?: string;
  imageUUID?: string;
  imageURL?: string;
  imageDataURI?: string;
  imageBase64Data?: string;
}

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

async function uploadReferenceImage(
  input: ProviderInput,
  apiKey: string,
  timeoutMs: number,
): Promise<string> {
  const uploadPayload = await callRunware(
    [
      {
        taskType: 'imageUpload',
        taskUUID: uuid(),
        image: input.image.dataUri,
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

  if (!uploaded?.imageUUID) {
    throw new ProviderError(
      'Runware: imageUUID دریافت نشد',
      JSON.stringify(uploadPayload).slice(0, 500),
    );
  }

  return uploaded.imageUUID;
}

async function generateWithModel(
  input: ProviderInput,
  apiKey: string,
  selectedModel: string,
  referenceImageUUID: string,
  timeoutMs: number,
): Promise<string> {
  const inferencePayload = await callRunware(
    [
      {
        taskType: 'imageInference',
        taskUUID: uuid(),
        model: selectedModel,
        positivePrompt: input.prompt,
        inputs: {
          referenceImages: [referenceImageUUID],
        },
        width: Number(process.env.RUNWARE_WIDTH ?? 1024),
        height: Number(process.env.RUNWARE_HEIGHT ?? 1024),
        outputType: 'URL',
        outputFormat: 'JPG',
        numberResults: 1,
        includeCost: true,
      },
    ],
    apiKey,
    `imageInference model=${selectedModel}`,
    timeoutMs,
  );

  const inferenceTasks = readTasks(inferencePayload);
  const result =
    inferenceTasks.find((task) => task?.taskType === 'imageInference') ??
    inferenceTasks[0];

  if (result?.imageURL) return result.imageURL;
  if (result?.imageDataURI) return result.imageDataURI;
  if (result?.imageBase64Data) {
    return `data:image/jpeg;base64,${result.imageBase64Data}`;
  }

  throw new ProviderError(
    `Runware: مدل ${selectedModel} تصویری برنگرداند`,
    JSON.stringify(inferencePayload).slice(0, 300),
  );
}

export const runwareProvider: Provider = {
  id: 'runware',
  label: 'Runware',
  envKey: 'RUNWARE_API_KEY',

  async generate(input: ProviderInput): Promise<string> {
    const timeoutMs = timeoutFor(input);
    const apiKey = (process.env.RUNWARE_API_KEY ?? '').trim();

    if (!apiKey) {
      throw new ProviderError('Runware: کلید API تنظیم نشده است');
    }

    const referenceImageUUID = await uploadReferenceImage(input, apiKey, timeoutMs);
    const failures: string[] = [];

    for (const selectedModel of models()) {
      try {
        return await generateWithModel(
          input,
          apiKey,
          selectedModel,
          referenceImageUUID,
          timeoutMs,
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        failures.push(`${selectedModel}: ${message}`);
      }
    }

    throw new ProviderError(
      'Runware: همه مدل‌های ویرایش تصویر ناموفق بودند',
      failures.join(' | ').slice(0, 1200),
    );
  },
};

export const __runwareInternals = { readTasks, endpoint, models };
