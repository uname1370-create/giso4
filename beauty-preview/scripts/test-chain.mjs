#!/usr/bin/env node
/**
 * scripts/test-chain.mjs
 * ---------------------------------------------------------------------------
 * تست خودکار «زنجیرهٔ جایگزین ۴ پروایدری» بدون نیاز به کلید واقعی:
 *
 *   ۱) سرور mock پروایدرها را بالا می‌آورد (scripts/mock-providers.mjs)
 *   ۲) یک نسخهٔ Next.js روی پورت تست با آدرس‌های mock اجرا می‌کند
 *   ۳) پنج سناریو را امتحان می‌کند:
 *        runware     → پروایدر اول موفق
 *        siliconflow → اولی خطا می‌دهد، دومی موفق
 *        aimlapi     → دو تای اول خطا، سومی موفق
 *        pollinations→ سه تای اول خطا، چهارمی موفق
 *        allfail     → همه خطا → پاسخ ۵۰۲ و پیام خطای فارسی
 *   ۴) در پایان هر دو پروسه را می‌بندد و خلاصه را چاپ می‌کند.
 *
 * اجرا:  npm run test:chain
 * ---------------------------------------------------------------------------
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(here, '..');

const MOCK_PORT = Number(process.env.MOCK_PORT ?? 4699);
const APP_PORT = Number(process.env.APP_PORT ?? 3210);
const MODE_FILE = path.join(os.tmpdir(), `beauty-preview-mock-mode-${process.pid}.txt`);

const TINY_JPEG_BASE64 =
  '/9j/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAAIAAgDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAABP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKEACY//2Q==';

const CASES = [
  { mode: 'runware', expected: 'runware' },
  { mode: 'siliconflow', expected: 'siliconflow' },
  { mode: 'aimlapi', expected: 'aimlapi' },
  { mode: 'pollinations', expected: 'pollinations' },
  { mode: 'allfail', expected: null },
];

const children = [];
let failures = 0;

function spawnProcess(command, args, options) {
  const child = spawn(command, args, { stdio: ['ignore', 'pipe', 'pipe'], ...options });
  child.stdout.on('data', () => {});
  child.stderr.on('data', () => {});
  children.push(child);
  return child;
}

function shutdown() {
  for (const child of children) {
    if (child.exitCode === null) {
      try {
        process.kill(-child.pid, 'SIGTERM');
      } catch {
        try {
          child.kill('SIGTERM');
        } catch {
          /* ignore */
        }
      }
    }
  }
}

async function waitFor(url, timeoutMs = 120_000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      /* هنوز بالا نیامده */
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return false;
}

function setMode(mode) {
  fs.writeFileSync(MODE_FILE, mode, 'utf8');
}

async function callGenerate() {
  const res = await fetch(`http://127.0.0.1:${APP_PORT}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      imageBase64: `data:image/jpeg;base64,${TINY_JPEG_BASE64}`,
      style: 'اومبره پودری',
      colorName: 'قهوه‌ای طبیعی',
      colorHex: '#8B6914',
    }),
  });
  return { status: res.status, data: await res.json() };
}

async function resetMock() {
  await fetch(`http://127.0.0.1:${MOCK_PORT}/__reset`).catch(() => {});
}

async function main() {
  console.log('— سرور mock پروایدرها …');
  spawnProcess('node', [path.join(here, 'mock-providers.mjs')], {
    cwd: appRoot,
    detached: true,
    env: { ...process.env, PORT: String(MOCK_PORT), MODE: 'runware', MOCK_MODE_FILE: MODE_FILE },
  });
  setMode('runware');

  if (!(await waitFor(`http://127.0.0.1:${MOCK_PORT}/__report`, 20_000))) {
    throw new Error('سرور mock بالا نیامد');
  }

  console.log('— اجرای Next.js روی پورت تست …');
  spawnProcess('npx', ['next', 'dev', '-H', '127.0.0.1', '-p', String(APP_PORT)], {
    cwd: appRoot,
    detached: true,
    env: {
      ...process.env,
      RUNWARE_API_KEY: 'test-key',
      RUNWARE_API_URL: `http://127.0.0.1:${MOCK_PORT}/rw`,
      SILICONFLOW_API_KEY: 'test-key',
      SILICONFLOW_BASE_URL: `http://127.0.0.1:${MOCK_PORT}/sf/v1`,
      AIMLAPI_API_KEY: 'test-key',
      AIMLAPI_API_URL: `http://127.0.0.1:${MOCK_PORT}/aiml/v1/images/generations`,
      POLLINATIONS_API_KEY: 'test-key',
      POLLINATIONS_BASE_URL: `http://127.0.0.1:${MOCK_PORT}/pl/v1`,
      DEMO_MODE: 'off',
      PROVIDER_TIMEOUT_MS: '20000',
    },
  });

  if (!(await waitFor(`http://127.0.0.1:${APP_PORT}/api/generate`, 180_000))) {
    throw new Error('اپ Next.js روی پورت تست بالا نیامد');
  }

  console.log('');

  for (const testCase of CASES) {
    setMode(testCase.mode);
    await resetMock();

    const { status, data } = await callGenerate();
    const attempts = (data.attempts ?? [])
      .map((attempt) => `${attempt.label}:${attempt.ok ? '✓' : '✕'}`)
      .join(' → ');

    let pass;
    if (testCase.expected === null) {
      pass = status === 502 && data.ok === false && typeof data.error === 'string';
    } else {
      pass = status === 200 && data.ok === true && data.provider === testCase.expected;
    }
    if (!pass) failures += 1;

    console.log(
      `${pass ? '✅' : '❌'} حالت «${testCase.mode}» → ` +
        (testCase.expected === null
          ? `انتظار ۵۰۲ با پیام خطا | دریافت: ${status}${data.error ? ` — ${data.error.slice(0, 60)}…` : ''}`
          : `انتظار ${testCase.expected} | دریافت: ${data.provider ?? '-'} (HTTP ${status})`) +
        (attempts ? `\n     تلاش‌ها: ${attempts}` : ''),
    );
  }

  console.log('');
  console.log(failures === 0 ? '🎉 همهٔ سناریوها موفق بودند' : `⚠️ ${failures} سناریو شکست خورد`);
  return failures;
}

main()
  .then((code) => {
    shutdown();
    setTimeout(() => process.exit(code === 0 ? 0 : 1), 300);
  })
  .catch((error) => {
    console.error('خطا در تست:', error.message);
    shutdown();
    setTimeout(() => process.exit(1), 300);
  });
