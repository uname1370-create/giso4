#!/usr/bin/env node
/**
 * scripts/test-admin.mjs
 * ---------------------------------------------------------------------------
 * تست خودکار پنل مدیریت (بدون نیاز به مرورگر):
 *
 *   ۱) یک نسخهٔ Next.js روی پورت تست بالا می‌آورد (با ADMIN_PASSWORD تستی)
 *   ۲) ورود، احراز هویت، آمار، ثبت بازدید/پیش‌نمایش و آپلود/حذف تصاویر را
 *      به‌صورت واقعی آزمایش می‌کند
 *   ۳) در پایان، `data/stats.json`، تصاویر آپلودشده و tsconfig.json را به حالت
 *      اول برمی‌گرداند تا آمار و تصاویر واقعی شما دست‌نخورده بماند
 *
 * اجرا:  npm run test:admin
 * ---------------------------------------------------------------------------
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(here, '..');
const PORT = Number(process.env.ADMIN_TEST_PORT ?? 3310);
const BASE = `http://127.0.0.1:${PORT}`;

/** پوشهٔ build مخصوص تست (جدا از `.next` سرور توسعه) */
const TEST_DIST_DIR = '.next-admin-test';

/** رمز عبور تستی — تا مطمئن شویم ADMIN_PASSWORD بر پیش‌فرض غلبه می‌کند */
const TEST_PASSWORD = 'test-admin-pass';

/** یک تصویر ۸×۸ واقعی (JPEG) برای تست آپلود — بدون وابستگی به کتابخانهٔ تصویر */
const TINY_JPEG_BASE64 =
  '/9j/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAAIAAgDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAABP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKEACY//2Q==';

/**
 * فایل‌هایی که تست تغییرشان می‌دهد و در پایان به حالت اول برمی‌گردند.
 * نکته: Next.js هنگام بالا آمدن با `distDir` غیرپیش‌فرض، مسیر تایپ‌های آن را
 * به `tsconfig.json` اضافه می‌کند؛ پس این فایل هم باید بازگردانده شود.
 */
const STAGES = [
  { path: 'data/stats.json' },
  { path: 'tsconfig.json' },
];

/** فایل‌های تصویری که تست می‌سازد و در پایان حذف/بازگردانی می‌شوند */
const IMAGE_ARTIFACTS = [
  'public/eyebrows/feather.png',
  'public/eyebrows/natural-hairstroke.png',
  'public/eyebrows/ombre-powder.png',
  'public/eyebrows/combination.png',
  'public/hero/hero.jpg',
  'public/hero/hero.png',
  'public/hero/hero.webp',
];

let pass = 0;
let fail = 0;

function check(name, ok, extra = '') {
  console.log(`${ok ? '✅' : '❌'} ${name}${extra ? ` — ${extra}` : ''}`);
  if (ok) pass += 1;
  else fail += 1;
}

const children = [];

function cleanupTestBuild() {
  for (const target of [TEST_DIST_DIR, '.tmp-admin-stats.json']) {
    try {
      fs.rmSync(path.join(appRoot, target), { recursive: true, force: true });
    } catch {
      /* پاک‌سازی اختیاری است */
    }
  }
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

async function waitFor(url, timeoutMs = 180_000) {
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

/** رمز پیش‌فرض پنل (اگر ADMIN_PASSWORD تنظیم نشده باشد) */
const FALLBACK_PASSWORD = '1234';

async function main() {
  /* --- پشتیبان‌گیری از تصاویر فعلی تا در پایان بازگردانده شوند --- */
  const imageBackups = IMAGE_ARTIFACTS.map((relative) => {
    const absolute = path.join(appRoot, relative);
    return {
      absolute,
      content: fs.existsSync(absolute) ? fs.readFileSync(absolute) : null,
    };
  });

  /* --- پشتیبان‌گیری از فایل‌های داده تا در پایان بازگردانده شوند --- */
  const backups = STAGES.map((stage) => {
    const absolute = path.join(appRoot, stage.path);
    return {
      absolute,
      existed: fs.existsSync(absolute),
      content: fs.existsSync(absolute) ? fs.readFileSync(absolute) : null,
    };
  });

  console.log('— اجرای Next.js روی پورت تست (با ADMIN_PASSWORD تستی) …');
  const child = spawn('npx', ['next', 'dev', '-H', '127.0.0.1', '-p', String(PORT)], {
    cwd: appRoot,
    detached: true,
    env: {
      ...process.env,
      ADMIN_PASSWORD: TEST_PASSWORD,
      DEMO_MODE: 'auto',
      // پوشهٔ build جداگانه تا `.next` سرور توسعهٔ در حال اجرای شما خراب نشود
      NEXT_DIST_DIR: TEST_DIST_DIR,
      // آمار در فایل موقت نوشته می‌شود تا آمار واقعی هرگز تغییر نکند
      STATS_PATH: path.join(appRoot, '.tmp-admin-stats.json'),
    },
    stdio: ['ignore', 'ignore', 'ignore'],
  });
  children.push(child);

  // توجه: منتظر صفحهٔ ورود می‌مانیم (روت‌های /api/admin بدون توکن ۴۰۱ می‌دهند)
  if (!(await waitFor(`${BASE}/admin`))) {
    throw new Error('اپ روی پورت تست بالا نیامد');
  }

  console.log('');

  /* ---------------------------- صفحهٔ ورود ---------------------------- */
  const loginPage = await fetch(`${BASE}/admin`);
  const loginHtml = await loginPage.text();
  check('GET /admin → 200', loginPage.status === 200, `HTTP ${loginPage.status}`);
  check(
    'عنوان «عسل رجبی | پنل مدیریت»',
    loginHtml.includes('عسل رجبی') && loginHtml.includes('پنل مدیریت'),
  );
  check('ورودی رمز عبور (type=password)', /type="password"/.test(loginHtml));
  check('دکمهٔ ورود', loginHtml.includes('ورود'));

  /* ------------------------------- ورود ------------------------------- */
  const wrong = await fetch(`${BASE}/api/admin/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: 'definitely-wrong' }),
  });
  const wrongData = await wrong.json();
  check('رمز اشتباه → 401', wrong.status === 401, `HTTP ${wrong.status}`);
  check('پیام فارسی «رمز عبور اشتباه است»', wrongData.error === 'رمز عبور اشتباه است');

  const fallbackTry = await fetch(`${BASE}/api/admin/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: FALLBACK_PASSWORD }),
  });
  check('رمز پیش‌فرض وقتی ADMIN_PASSWORD تنظیم شده → رد می‌شود', fallbackTry.status === 401);

  const login = await fetch(`${BASE}/api/admin/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: TEST_PASSWORD }),
  });
  const loginData = await login.json();
  const token = loginData.token;
  check('رمز درست (ADMIN_PASSWORD) → 200 + توکن', login.status === 200 && Boolean(token));

  const auth = { Authorization: `Bearer ${token}` };

  /* ---------------------------- داشبورد ---------------------------- */
  const dashboard = await fetch(`${BASE}/admin/dashboard`);
  check('GET /admin/dashboard → 200', dashboard.status === 200, `HTTP ${dashboard.status}`);

  check('آمار بدون توکن → 401', (await fetch(`${BASE}/api/admin/stats`)).status === 401);
  check(
    'آمار با توکن جعلی → 401',
    (await fetch(`${BASE}/api/admin/stats`, { headers: { Authorization: 'Bearer 1.bad' } }))
      .status === 401,
  );

  const stats0 = await (await fetch(`${BASE}/api/admin/stats`, { headers: auth })).json();
  check('آمار با توکن درست → 200', stats0.ok === true, `visits=${stats0.visits}`);
  check(
    'فیلدهای امروز (todayVisits/todayPreviews) موجود است',
    typeof stats0.todayVisits === 'number' && typeof stats0.todayPreviews === 'number',
  );

  /* --------------------------- ثبت رویدادها --------------------------- */
  const beforeVisits = stats0.visits;
  const visit = await (
    await fetch(`${BASE}/api/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'visit' }),
    })
  ).json();
  const stats1 = await (await fetch(`${BASE}/api/admin/stats`, { headers: auth })).json();
  check('ثبت بازدید → visits +۱', visit.counted === true && stats1.visits === beforeVisits + 1);

  const visitAgain = await (
    await fetch(`${BASE}/api/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'visit' }),
    })
  ).json();
  const stats2 = await (await fetch(`${BASE}/api/admin/stats`, { headers: auth })).json();
  check('بازدید تکراری در همان ۶ ساعت شمرده نمی‌شود', visitAgain.counted === false);

  const generated = await fetch(`${BASE}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      imageBase64: `data:image/jpeg;base64,${TINY_JPEG_BASE64}`,
      style: 'فدر براو',
      colorName: 'بلوند',
      colorHex: '#C4A265',
    }),
  });
  const stats3 = await (await fetch(`${BASE}/api/admin/stats`, { headers: auth })).json();
  check(
    'ساخت پیش‌نمایش → previews +۱',
    generated.status === 200 && stats3.previews === stats2.previews + 1,
  );
  check(
    'رویداد preview با کلید سبک ذخیره می‌شود',
    stats3.history[0]?.type === 'preview' && stats3.history[0]?.style === 'feather',
    JSON.stringify(stats3.history[0] ?? {}),
  );

  /* ------------------------ آپلود تصاویر ابرو ------------------------ */
  // تصویر ابرو باید PNG باشد — یک PNG کوچک واقعی (۱×۱ پیکسل) می‌سازیم
  const TINY_PNG = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==',
    'base64',
  );

  const browForm = new FormData();
  browForm.append('styleName', 'فدر براو'); // آزمون پذیرش نام فارسی مدل
  browForm.append('file', new Blob([TINY_PNG], { type: 'image/png' }), 'feather.png');
  const browUpload = await fetch(`${BASE}/api/admin/upload-brow`, {
    method: 'POST',
    headers: auth,
    body: browForm,
  });
  const browData = await browUpload.json();
  check('آپلود تصویر ابرو → 200', browUpload.status === 200 && browData.ok === true, browData.url);
  check(
    'فایل با نام ثابت ذخیره شد — /eyebrows/feather.png',
    browData.publicPath === '/eyebrows/feather.png' &&
      fs.existsSync(path.join(appRoot, 'public', 'eyebrows', 'feather.png')),
    browData.publicPath,
  );
  check(
    'پاسخ، آدرس روت /api/site-image را برمی‌گرداند',
    browData.url === '/api/site-image/eyebrows/feather.png',
    browData.url,
  );
  const served = await fetch(`${BASE}${browData.url}`);
  check(
    'تصویر از روت /api/site-image سرو می‌شود',
    served.status === 200 && served.headers.get('content-type') === 'image/png',
    `${served.status} ${served.headers.get('content-type')}`,
  );
  check(
    'مسیرهای نامعتبر → 404',
    (await fetch(`${BASE}/api/site-image/hero/nope.jpg`)).status === 404 &&
      (await fetch(`${BASE}/api/site-image/other/x.jpg`)).status === 404 &&
      (await fetch(`${BASE}/api/site-image/eyebrows/unknown.png`)).status === 404,
  );

  // فایل غیر PNG (هم با MIME دروغین) باید رد شود
  const jpegAsBrow = new FormData();
  jpegAsBrow.append('styleName', 'feather');
  jpegAsBrow.append(
    'file',
    new Blob([Buffer.from(TINY_JPEG_BASE64, 'base64')], { type: 'image/png' }),
    'fake.png',
  );
  const jpegAsBrowRes = await fetch(`${BASE}/api/admin/upload-brow`, {
    method: 'POST',
    headers: auth,
    body: jpegAsBrow,
  });
  check('فایل JPG با پسوند PNG رد می‌شود → 400', jpegAsBrowRes.status === 400);

  const textForm = new FormData();
  textForm.append('styleName', 'feather');
  textForm.append('file', new Blob([Buffer.from('hello')], { type: 'text/plain' }), 'x.txt');
  check(
    'فایل غیرتصویری رد می‌شود → 400',
    (await fetch(`${BASE}/api/admin/upload-brow`, { method: 'POST', headers: auth, body: textForm }))
      .status === 400,
  );

  const badStyleForm = new FormData();
  badStyleForm.append('styleName', 'unknown-style');
  badStyleForm.append('file', new Blob([TINY_PNG], { type: 'image/png' }), 'x.png');
  check(
    'مدل ابروی نامعتبر رد می‌شود → 400',
    (
      await fetch(`${BASE}/api/admin/upload-brow`, {
        method: 'POST',
        headers: auth,
        body: badStyleForm,
      })
    ).status === 400,
  );

  const noAuthForm = new FormData();
  noAuthForm.append('styleName', 'feather');
  noAuthForm.append('file', new Blob([TINY_PNG], { type: 'image/png' }), 'x.png');
  check(
    'آپلود بدون توکن → 401',
    (await fetch(`${BASE}/api/admin/upload-brow`, { method: 'POST', body: noAuthForm })).status ===
      401,
  );
  check(
    'آپلود با هدر x-admin-password (روش سادهٔ سند) → 200',
    (
      await fetch(`${BASE}/api/admin/upload-brow`, {
        method: 'POST',
        headers: { 'x-admin-password': TEST_PASSWORD },
        body: noAuthForm,
      })
    ).status === 200,
  );
  check(
    'هدر x-admin-password اشتباه → 401',
    (
      await fetch(`${BASE}/api/admin/stats`, {
        headers: { 'x-admin-password': 'wrong-password' },
      })
    ).status === 401,
  );

  /* -------------------------- تصویر هیرو -------------------------- */
  const heroForm = new FormData();
  heroForm.append('file', new Blob([TINY_PNG], { type: 'image/png' }), 'hero.png');
  const heroUpload = await fetch(`${BASE}/api/admin/upload-hero`, {
    method: 'POST',
    headers: auth,
    body: heroForm,
  });
  const heroData = await heroUpload.json();
  check('آپلود تصویر هیرو → 200', heroUpload.status === 200 && heroData.ok === true, heroData.url);
  check(
    'تصویر هیرو با نام hero.png ذخیره شد',
    heroData.publicPath === '/hero/hero.png' &&
      fs.existsSync(path.join(appRoot, 'public', 'hero', 'hero.png')),
    heroData.publicPath,
  );
  check(
    'آدرس هیرو پایدار است (بدون پسوند)',
    heroData.url === '/api/site-image/hero/hero',
    heroData.url,
  );
  const heroServed = await fetch(`${BASE}${heroData.url}`);
  check('تصویر هیرو از روت سرو می‌شود', heroServed.status === 200, `HTTP ${heroServed.status}`);

  // آپلود JPG روی PNG قبلی: فرمت قبلی باید پاک شود
  const heroJpgForm = new FormData();
  heroJpgForm.append(
    'file',
    new Blob([Buffer.from(TINY_JPEG_BASE64, 'base64')], { type: 'image/jpeg' }),
    'hero.jpg',
  );
  const heroJpgUpload = await fetch(`${BASE}/api/admin/upload-hero`, {
    method: 'POST',
    headers: auth,
    body: heroJpgForm,
  });
  check(
    'آپلود JPG روی PNG → فقط hero.jpg می‌ماند',
    heroJpgUpload.status === 200 &&
      fs.existsSync(path.join(appRoot, 'public', 'hero', 'hero.jpg')) &&
      !fs.existsSync(path.join(appRoot, 'public', 'hero', 'hero.png')),
  );
  const heroAfter = await fetch(`${BASE}${heroData.url}`);
  check(
    'آدرس پایدار هنوز تصویر می‌دهد (حالا JPG)',
    heroAfter.status === 200 && heroAfter.headers.get('content-type') === 'image/jpeg',
    `${heroAfter.status} ${heroAfter.headers.get('content-type')}`,
  );

  /* ----------------------------- حذف‌ها ----------------------------- */
  const deleteBrow = await fetch(`${BASE}/api/admin/upload-brow?style=feather`, {
    method: 'DELETE',
    headers: auth,
  });
  const deleteBrowData = await deleteBrow.json();
  check('حذف تصویر ابرو → 200', deleteBrow.status === 200 && deleteBrowData.removed === true);
  check(
    'فایل ابرو از دیسک پاک شد',
    !fs.existsSync(path.join(appRoot, 'public', 'eyebrows', 'feather.png')),
  );
  check(
    'بعد از حذف، صفحهٔ اصلی به SVG برمی‌گردد (۴۰۴)',
    (await fetch(`${BASE}/api/site-image/eyebrows/feather.png`)).status === 404,
  );

  const deleteHero = await fetch(`${BASE}/api/admin/upload-hero`, { method: 'DELETE', headers: auth });
  const deleteHeroData = await deleteHero.json();
  check('حذف تصویر هیرو → 200', deleteHero.status === 200 && deleteHeroData.removed === true);
  check(
    'فایل هیرو از دیسک پاک شد',
    !fs.existsSync(path.join(appRoot, 'public', 'hero', 'hero.jpg')),
  );
  check(
    'بعد از حذف، هیرو ۴۰۴ می‌دهد (پس‌زمینهٔ گرادیانی)',
    (await fetch(`${BASE}/api/site-image/hero/hero`)).status === 404,
  );

  /* --- بازگرداندن تصاویر به حالت اول --- */
  for (const backup of imageBackups) {
    try {
      if (backup.content) fs.writeFileSync(backup.absolute, backup.content);
      else if (fs.existsSync(backup.absolute)) fs.unlinkSync(backup.absolute);
    } catch {
      /* بازگردانی اختیاری است */
    }
  }

  /* --- بازگرداندن فایل‌های داده به حالت اول --- */
  for (const backup of backups) {
    if (backup.existed && backup.content) fs.writeFileSync(backup.absolute, backup.content);
  }
  console.log('\nℹ️  فایل‌های داده (آمار، تصاویر، tsconfig) به حالت قبل برگردانده شدند.');

  console.log(`\n${fail === 0 ? '🎉' : '⚠️'} ${pass} تست موفق، ${fail} ناموفق`);
  return fail;
}

main()
  .then((code) => {
    shutdown();
    // کمی صبر تا پروسه‌های فرزند کامل بسته شوند، بعد پاک‌سازی
    setTimeout(() => {
      cleanupTestBuild();
      process.exit(code === 0 ? 0 : 1);
    }, 1500);
  })
  .catch((error) => {
    console.error('خطا در تست:', error.message);
    shutdown();
    setTimeout(() => {
      cleanupTestBuild();
      process.exit(1);
    }, 1500);
  });
