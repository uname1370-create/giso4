/**
 * src/providers/siliconflow.ts
 * ---------------------------------------------------------------------------
 * پروایدر ۲ — SiliconFlow   (https://api-docs.siliconflow.cn)
 *
 * ✅ پیاده‌سازی اصلاح‌شده — مطابق مستند رسمی:
 *      POST https://api.siliconflow.cn/v1/images/generations
 *      Content-Type: application/json
 *      { "model": "Qwen/Qwen-Image-Edit", "prompt": "...", "image": "data:image/jpeg;base64,..." }
 *      → { "images": [ { "url": "..." } ], "timings": {...}, "seed": 0 }
 *
 * ❌ چه چیزی در نسخهٔ قبلی غلط بود (هر دو خطای ۴۰۴ و ۴۰۱ از همین‌ها می‌آمد):
 *      ۱) نسخهٔ قبلی با SDK رسمی OpenAI مسیر multipart «POST /v1/images/edits» را
 *         صدا می‌زد. مستند SiliconFlow چنین مسیری ندارد؛ فقط «/v1/images/generations»
 *         با بدنهٔ JSON وجود دارد. پاسخ آن مسیر ناموجود «404 page not found» است —
 *         دقیقاً همان خطای ۴۰۴.
 *      ۲) پاسخ SiliconFlow با شکل OpenAI یکی نیست: تصویر در «images[0].url»
 *         برمی‌گردد، نه «data[0].url». نسخهٔ قبلی data[0] را می‌خواند و حتی با
 *         پاسخ سالم هم تصویری پیدا نمی‌کرد.
 *      ۳) مدل «Qwen/Qwen2.5-VL-72B-Instruct» یک مدل زبانی-تصویری (chat) است و
 *         تصویر تولید نمی‌کند؛ مدل‌های ویرایش تصویر «Qwen/Qwen-Image-Edit» و
 *         «Qwen/Qwen-Image-Edit-2509» هستند.
 *      خطای ۴۰۱ («Invalid token») ربطی به کد ندارد و معنایش کلید نامعتبر/خالی
 *      است؛ در انتهای همین فایل راهنمای بررسی کلید آمده است.
 *
 * نکات مستند:
 *      • فیلد «image_size» را مدل‌های Qwen-Image-Edit پشتیبانی نمی‌کنند و
 *        فرستاده نمی‌شود.
 *      • «image» هم URL و هم data URI را می‌پذیرد.
 *      • «num_inference_steps» پیش‌فرض ۲۰ است.
 * ---------------------------------------------------------------------------
 */

import {
  ProviderError,
  extractApiError,
  readAnyImage,
  timeoutFor,
  timeoutSignal,
} from './http';
import type { Provider, ProviderInput } from './types';

const DEFAULT_BASE_URL = 'https://api.siliconflow.cn/v1';

/**
 * مدل‌های تأییدشدهٔ ویرایش تصویر SiliconFlow (به ترتیب امتحان).
 * با متغیر محیطی SILICONFLOW_MODEL می‌توانید فقط یک مدل را دستی تعیین کنید.
 */
const DEFAULT_MODELS = ['Qwen/Qwen-Image-Edit', 'Qwen/Qwen-Image-Edit-2509'];

/** آدرس پایه (قابل تغییر با SILICONFLOW_BASE_URL برای پروکسی/میرور/تست) */
function baseUrl(): string {
  return (process.env.SILICONFLOW_BASE_URL ?? '').trim().replace(/\/+$/, '') || DEFAULT_BASE_URL;
}

/** فهرست مدل‌های کاندید (اگر SILICONFLOW_MODEL تنظیم شده باشد فقط همان) */
function models(): string[] {
  const custom = (process.env.SILICONFLOW_MODEL ?? '').trim();
  return custom ? [custom] : DEFAULT_MODELS;
}

/** آیا خطا مربوط به «نداشتن دسترسی به این مدل» است؟ (برای امتحان مدل بعدی) */
function looksLikeModelProblem(status: number, detail: string): boolean {
  if (status === 403) return true;
  if (status !== 400 && status !== 404) return false;
  return /model|not exist|not found|unsupported|no permission|does not exist/i.test(detail);
}

/** آیا خطا مربوط به پارامتر ناشناس/پشتیبانی‌نشده است؟ (برای بدنهٔ ساده‌تر) */
function looksLikeParameterProblem(status: number, detail: string): boolean {
  if (status !== 400) return false;
  return /param|num_inference_steps|cfg|guidance|invalid.*field|unknown field|extra field/i.test(
    detail,
  );
}

/** هشدار کمکی دربارهٔ شکل کلید — خود کلید هرگز نمایش/لاگ نمی‌شود */
function keyHint(apiKey: string): string {
  if (!apiKey.startsWith('sk-')) {
    return ' کلید SILICONFLOW_API_KEY باید با «sk-» شروع شود؛ مقدار فعلی این‌طور نیست.';
  }
  if (apiKey.length < 20) {
    return ' کلید SILICONFLOW_API_KEY بسیار کوتاه است؛ احتمالاً ناقص کپی شده است.';
  }
  return '';
}

async function readJson(res: Response): Promise<{ payload: unknown; raw: string }> {
  const raw = await res.text();
  let payload: unknown = null;
  try {
    payload = raw ? JSON.parse(raw) : null;
  } catch {
    payload = null;
  }
  return { payload, raw };
}

/** پاسخ خطای SiliconFlow ممکن است متن ساده باشد («Invalid token») یا JSON */
function errorDetail(payload: unknown, raw: string): string {
  const fromJson = extractApiError(payload);
  if (fromJson) return fromJson;
  return (raw ?? '').replace(/^"|"$/g, '').trim().slice(0, 300);
}

/**
 * مسیر اصلی و مستندشده:
 *   POST /images/generations  با بدنهٔ JSON و فیلد «image» به‌صورت data URI
 */
async function viaGenerations(
  apiKey: string,
  model: string,
  input: ProviderInput,
): Promise<{ image: string } | { retryModel: true } | { retryBody: true } | { notFound: true }> {
  const { signal, done } = timeoutSignal(timeoutFor(input));
  try {
    // بدنهٔ کامل، و در صورت ایراد گرفتن سرور به پارامترها، بدنهٔ سادهٔ بدون آن‌ها
    const bodies: Array<Record<string, unknown>> = [
      {
        model,
        prompt: input.prompt,
        image: input.image.dataUri,
        num_inference_steps: 20,
      },
      { model, prompt: input.prompt, image: input.image.dataUri },
    ];

    let lastError: ProviderError | null = null;

    for (const body of bodies) {
      const res = await fetch(`${baseUrl()}/images/generations`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
          Accept: 'application/json',
          // واترمارک صریح «AI-generated» برای تصویر نهایی لازم نیست؛ پردازش
          // بعدی روی تصویر انجام می‌شود (خودِ سرویس واترمارک غیرصریح را می‌زند).
          'X-Enable-Watermark': '0',
        },
        body: JSON.stringify(body),
        signal,
        cache: 'no-store',
      });

      const { payload, raw } = await readJson(res);

      if (res.ok) {
        const image = readAnyImage(payload);
        if (!image) {
          throw new ProviderError(
            'SiliconFlow: پاسخ بدون تصویر بود',
            errorDetail(payload, raw) || raw.slice(0, 300),
          );
        }
        return { image };
      }

      const detail = errorDetail(payload, raw);

      // کلید نامعتبر — با تلاش مجدد درست نمی‌شود، پس صریح و راهنما خطا می‌دهیم
      if (res.status === 401) {
        throw new ProviderError(
          'SiliconFlow: کلید API نامعتبر است (401)',
          `${detail || 'Invalid token'}.${keyHint(apiKey)}`,
        );
      }

      // مسیر وجود ندارد (مثلاً آدرس پایه اشتباه است) → مسیر جایگزین را امتحان کن
      if (res.status === 404 && !looksLikeModelProblem(res.status, detail)) {
        return { notFound: true };
      }

      // مدل در دسترس نیست → مدل بعدی
      if (looksLikeModelProblem(res.status, detail)) {
        return { retryModel: true };
      }

      // پارامتر پشتیبانی‌نشده → همان مدل با بدنهٔ ساده‌تر
      if (body !== bodies[bodies.length - 1] && looksLikeParameterProblem(res.status, detail)) {
        lastError = new ProviderError(
          `SiliconFlow ناموفق بود (HTTP ${res.status})`,
          detail || raw.slice(0, 300),
        );
        continue;
      }

      throw new ProviderError(
        `SiliconFlow ناموفق بود (HTTP ${res.status})`,
        detail || raw.slice(0, 300),
      );
    }

    throw lastError ?? new ProviderError('SiliconFlow ناموفق بود');
  } catch (error) {
    if (error instanceof ProviderError) throw error;
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ProviderError('SiliconFlow: زمان انتظار به پایان رسید');
    }
    throw new ProviderError(
      'SiliconFlow ناموفق بود',
      error instanceof Error ? error.message : String(error),
    );
  } finally {
    done();
  }
}

/**
 * مسیر پشتیبان (فقط اگر مسیر اصلی ۴۰۴ بدهد):
 * فرمت multipart سبک OpenAI — بعضی گیت‌وی‌ها این را هم می‌پذیرند.
 */
async function viaEdits(
  apiKey: string,
  model: string,
  input: ProviderInput,
): Promise<string> {
  const { signal, done } = timeoutSignal(timeoutFor(input));
  try {
    const form = new FormData();
    form.append('model', model);
    form.append('prompt', input.prompt);
    form.append(
      'image',
      new Blob([new Uint8Array(input.image.bytes)], { type: input.image.mime }),
      `image.${input.image.extension}`,
    );

    const res = await fetch(`${baseUrl()}/images/edits`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        // توجه: Content-Type دستی ست نمی‌شود تا FormData مرز (boundary) را بگذارد
        'X-Enable-Watermark': '0',
      },
      body: form,
      signal,
      cache: 'no-store',
    });

    const { payload, raw } = await readJson(res);
    if (!res.ok) {
      throw new ProviderError(
        `SiliconFlow (images/edits) ناموفق بود (HTTP ${res.status})`,
        errorDetail(payload, raw) || raw.slice(0, 300),
      );
    }

    const image = readAnyImage(payload);
    if (!image) {
      throw new ProviderError('SiliconFlow: هیچ تصویری دریافت نشد');
    }
    return image;
  } catch (error) {
    if (error instanceof ProviderError) throw error;
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ProviderError('SiliconFlow: زمان انتظار به پایان رسید');
    }
    throw new ProviderError(
      'SiliconFlow ناموفق بود',
      error instanceof Error ? error.message : String(error),
    );
  } finally {
    done();
  }
}

export const siliconflowProvider: Provider = {
  id: 'siliconflow',
  label: 'SiliconFlow',
  envKey: 'SILICONFLOW_API_KEY',

  async generate(input: ProviderInput): Promise<string> {
    const apiKey = (process.env.SILICONFLOW_API_KEY ?? '').trim();
    if (!apiKey) throw new ProviderError('SiliconFlow: کلید API تنظیم نشده است');

    const candidates = models();
    const failures: string[] = [];
    /** اگر مسیر مستندشده ۴۰۴ داد، مسیر جایگزین را امتحان می‌کنیم */
    let endpointMissing = false;

    /* --------------------- مسیر اصلی: images/generations --------------------- */
    for (const model of candidates) {
      try {
        const result = await viaGenerations(apiKey, model, input);
        if ('image' in result) return result.image;
        if ('notFound' in result) {
          endpointMissing = true;
          break;
        }
        // retryModel یا retryBody → مدل بعدی
        failures.push(`${model}: پاسخ قابل استفاده نبود`);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const detail = error instanceof ProviderError ? error.detail : undefined;
        failures.push(`${model}: ${message}${detail ? ` — ${detail}` : ''}`);

        // خطای کلید/شبکه: امتحان مدل بعدی بی‌فایده است
        if (/کلید API|نامعتبر|زمان انتظار/.test(message)) break;
      }
    }

    /* --------------- مسیر پشتیبان: images/edits (multipart) --------------- */
    if (endpointMissing) {
      try {
        return await viaEdits(apiKey, candidates[0], input);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const detail = error instanceof ProviderError ? error.detail : undefined;
        failures.push(`images/edits: ${message}${detail ? ` — ${detail}` : ''}`);
      }
    }

    throw new ProviderError('SiliconFlow ناموفق بود', failures.join(' | ').slice(0, 500));
  },
};
