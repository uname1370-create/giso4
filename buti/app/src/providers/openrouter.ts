/**
 * Provider — OpenRouter Image API
 * Model: black-forest-labs/flux.2-klein-4b
 * Official image editing contract: POST /api/v1/images + input_references.
 */

import {
    ProviderError,
    extractApiError,
    readOpenAiImage,
    timeoutFor,
    timeoutSignal,
} from './http';
import type { Provider, ProviderInput } from './types';

const DEFAULT_ENDPOINT = 'https://openrouter.ai/api/v1/images';
const DEFAULT_MODEL = 'black-forest-labs/flux.2-klein-4b';

function endpoint(): string {
    return (process.env.OPENROUTER_API_URL ?? '').trim() || DEFAULT_ENDPOINT;
}

function model(): string {
    return (process.env.OPENROUTER_MODEL ?? '').trim() || DEFAULT_MODEL;
}

export const openrouterProvider: Provider = {
    id: 'openrouter',
    label: 'OpenRouter — FLUX.2 Klein 4B',
    envKey: 'OPENROUTER_API_KEY',

    async generate(input: ProviderInput): Promise<string> {
        const apiKey = (process.env.OPENROUTER_API_KEY ?? '').trim();
        if (!apiKey) throw new ProviderError('OpenRouter: کلید API تنظیم نشده است');

        const { signal, done } = timeoutSignal(timeoutFor(input));
        try {
            const res = await fetch(endpoint(), {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${apiKey}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    model: model(),
                    prompt: input.prompt,
                    input_references: [
                        {
                            type: 'image_url',
                            image_url: { url: input.image.dataUri },
                        },
                    ],
                }),
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
                    `OpenRouter ناموفق بود (HTTP ${res.status})`,
                    extractApiError(payload) || raw.slice(0, 500),
                );
            }

            const image = readOpenAiImage(payload);
            if (!image) {
                throw new ProviderError(
                    'OpenRouter: پاسخ موفق بود اما تصویر خروجی پیدا نشد',
                    extractApiError(payload) || raw.slice(0, 500),
                );
            }

            return image;
        } catch (error) {
            if (error instanceof ProviderError) throw error;
            if (error instanceof Error && error.name === 'AbortError') {
                throw new ProviderError('OpenRouter: زمان انتظار به پایان رسید');
            }
            throw new ProviderError(
                'OpenRouter ناموفق بود',
                error instanceof Error ? error.message : String(error),
            );
        } finally {
            done();
        }
    },
};