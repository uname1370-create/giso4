/**
 * scripts/mock-providers.mjs
 * ---------------------------------------------------------------------------
 * سرور شبیه‌ساز (mock) پروایدرها برای تست زنجیرهٔ جایگزین بدون مصرف اعتبار
 * واقعی. هر پروایدر مسیر اختصاصی خودش را دارد:
 *
 *   /rw        → Runware   (آرایهٔ JSON: imageUpload سپس imageInference)
 *   /sf/v1     → SiliconFlow
 *   /aiml/v1   → AIMLAPI
 *   /pl/v1     → Pollinations
 *
 * با متغیر MODE مشخص می‌کنید «از کدام پروایدر به بعد» پاسخ موفق بدهد:
 *   runware | siliconflow | aimlapi | pollinations | allfail
 * اگر فایل MOCK_MODE_FILE وجود داشته باشد، مقدارش در هر درخواست خوانده
 * می‌شود و می‌توان بدون ری‌استارت، حالت را تغییر داد.
 *
 * اجرا:  MODE=aimlapi PORT=4599 node scripts/mock-providers.mjs
 * ---------------------------------------------------------------------------
 */

import http from 'node:http';
import fs from 'node:fs';

const MODE = process.env.MODE ?? 'runware';
const PORT = Number(process.env.PORT ?? 4599);
const MODE_FILE = process.env.MOCK_MODE_FILE ?? '';

/** یک تصویر JPEG کوچک (کوچک‌ترین نمونهٔ ممکن برای تست) */
const TINY_JPEG_BASE64 =
  process.env.MOCK_IMAGE_BASE64 ??
  '/9j/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAAIAAgDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAABP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKEACY//2Q==';

const ORDER = ['runware', 'siliconflow', 'aimlapi', 'pollinations'];
const report = {};

function json(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

function logCalls(provider, entry) {
  report[provider] ??= { calls: [] };
  report[provider].calls.push(entry);
}

function currentMode() {
  if (MODE_FILE) {
    try {
      const fromFile = fs.readFileSync(MODE_FILE, 'utf8').trim();
      if (fromFile) return fromFile;
    } catch {
      /* فایل نیست → از MODE استفاده می‌شود */
    }
  }
  return MODE;
}

/** آیا این پروایدر باید موفق پاسخ بدهد؟ */
function shouldSucceed(provider) {
  const mode = currentMode();
  if (mode === 'allfail') return false;
  return ORDER.indexOf(provider) >= ORDER.indexOf(mode);
}

const server = http.createServer(async (req, res) => {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const body = Buffer.concat(chunks).toString('utf8');
  const url = req.url ?? '/';

  /* تصویر نتیجهٔ تست */
  if (url === '/result.jpg') {
    res.writeHead(200, { 'Content-Type': 'image/jpeg' });
    res.end(Buffer.from(TINY_JPEG_BASE64, 'base64'));
    return;
  }

  /* گزارش فراخوانی‌ها برای تست‌ها */
  if (url === '/__report') {
    return json(res, 200, { ...report, mode: currentMode() });
  }
  if (url === '/__reset') {
    for (const key of Object.keys(report)) delete report[key];
    return json(res, 200, { ok: true });
  }

  /* ------------------------------- Runware ------------------------------- */
  if (url.startsWith('/rw')) {
    let parsed = null;
    try {
      parsed = JSON.parse(body);
    } catch {
      /* ignore */
    }
    const task = Array.isArray(parsed) ? parsed[0] : null;
    logCalls('runware', task?.taskType);

    if (task?.taskType === 'imageUpload') {
      if (shouldSucceed('runware')) {
        return json(res, 200, {
          data: [
            {
              taskType: 'imageUpload',
              taskUUID: task.taskUUID,
              imageUUID: '11111111-2222-3333-4444-555555555555',
            },
          ],
        });
      }
      return json(res, 500, { errors: [{ code: 'mock', message: 'runware upload failed (mock)' }] });
    }

    if (task?.taskType === 'imageInference') {
      if (task.seedImage !== '11111111-2222-3333-4444-555555555555' && shouldSucceed('runware')) {
        return json(res, 400, { errors: [{ code: 'mock', message: 'seedImage missing' }] });
      }
      if (shouldSucceed('runware')) {
        return json(res, 200, {
          data: [
            {
              taskType: 'imageInference',
              taskUUID: task.taskUUID,
              imageURL: `http://127.0.0.1:${PORT}/result.jpg`,
            },
          ],
        });
      }
      return json(res, 500, { errors: [{ code: 'mock', message: 'runware inference failed (mock)' }] });
    }

    return json(res, 400, {
      errors: [{ code: 'mock', message: `unknown runware task ${task?.taskType}` }],
    });
  }

  /* ----------------------------- SiliconFlow ----------------------------- */
  if (url.startsWith('/sf/v1')) {
    logCalls('siliconflow', `${url} [${(req.headers['content-type'] ?? '').split(';')[0]}]`);
    if (shouldSucceed('siliconflow')) {
      return json(res, 200, {
        created: Date.now(),
        data: [{ url: `http://127.0.0.1:${PORT}/result.jpg` }],
      });
    }
    return json(res, 500, { error: { message: 'siliconflow failed (mock)' } });
  }

  /* ------------------------------- AIMLAPI ------------------------------- */
  if (url.startsWith('/aiml/v1')) {
    let parsed = null;
    try {
      parsed = JSON.parse(body);
    } catch {
      /* ignore */
    }
    logCalls('aimlapi', url);
    report.aimlapi.model = parsed?.model;
    report.aimlapi.hasDataUriImage = String(parsed?.image_url ?? '').startsWith('data:image/');
    report.aimlapi.imageSize = parsed?.image_size;

    if (shouldSucceed('aimlapi')) {
      // شکل مستندشدهٔ AIMLAPI: images[0].url (به‌همراه data[0].url)
      return json(res, 200, {
        images: [{ url: `http://127.0.0.1:${PORT}/result.jpg`, width: 1024, height: 1024 }],
        data: [{ url: `http://127.0.0.1:${PORT}/result.jpg` }],
      });
    }
    return json(res, 500, { error: { message: 'aimlapi failed (mock)' } });
  }

  /* ----------------------------- Pollinations ---------------------------- */
  if (url.startsWith('/pl/v1')) {
    logCalls('pollinations', url);
    if (shouldSucceed('pollinations')) {
      return json(res, 200, { created: Date.now(), data: [{ b64_json: TINY_JPEG_BASE64 }] });
    }
    return json(res, 500, { error: { message: 'pollinations failed (mock)' } });
  }

  json(res, 404, { error: { message: `no mock route for ${url}` } });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[mock] providers on http://127.0.0.1:${PORT} — MODE=${MODE}`);
});
