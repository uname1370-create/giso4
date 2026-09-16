/**
 * Cloudflare Worker — پروکسی Gemini برای گیسو
 * =================================================
 * آدرس زنده: https://sadeghiai.uname1370.workers.dev
 *
 * کار: هر درخواست را با همان مسیر/متد/هدرها/بدنه به
 *      https://generativelanguage.googleapis.com
 * ارسال می‌کند. چون edge کلودفلر از ایران قابل دسترسی است،
 * سرور داخل ایران بدون VPN/پروکسی به Gemini می‌رسد.
 *
 * امنیت:
 *  - هیچ کلیدی در این Worker ذخیره نمی‌شود؛ کلید API همان
 *    `x-goog-api-key` یا `Authorization: Bearer` است که اپ گیسو
 *    در هدر می‌فرستد (Worker فقط عبور می‌دهد).
 *  - فقط مسیرهای /v1beta/* مجازند (جلوگیری از abuse به‌عنوان پروکسی باز).
 *
 * استقرار:
 *   1) داشبورد Cloudflare → Workers & Pages → Create Worker → ویرایشگر →
 *      همین کد را Paste و Deploy کنید. (یا: `npx wrangler deploy cloudflare-gemini-worker.js`)
 *   2) در سرور گیسو، داخل /etc/giso/web.env:
 *        GEMINI_BASE_URL=https://sadeghiai.uname1370.workers.dev
 *      و `sudo systemctl restart giso-web giso-bot`
 *
 * مسیرهایی که گیسو می‌زند:
 *   - OpenAI-compatible chat : {worker}/v1beta/openai/chat/completions   (ai_brain.py)
 *   - فهرست مدل‌ها           : {worker}/v1beta/openai/models             (ai_brain.py)
 *   - تست سلامت/ویژن پروکسی  : {worker}/v1beta/models[/{model}:generateContent]  (gemini_proxy_manager.py)
 */

const UPSTREAM = "https://generativelanguage.googleapis.com";

export default {
  async fetch(request) {
    const url = new URL(request.url);

    // فقط مسیرهای Gemini — وگرنه ۴۰۴ (جلوگیری از پروکسی باز)
    if (!url.pathname.startsWith("/v1beta/")) {
      return new Response(
        JSON.stringify({ error: "Only /v1beta/* (Gemini API) is proxied." }),
        { status: 404, headers: { "Content-Type": "application/json" } }
      );
    }

    //health-check ساده برای عیب‌یابی از سمت سرور
    if (url.pathname === "/v1beta/__health") {
      return new Response("ok", { status: 200 });
    }

    // ارسال همان درخواست به گوگل — متد، هدرها (شامل کلید API) و بدنه دست‌نخورده
    const upstreamUrl = UPSTREAM + url.pathname + url.search;
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers: request.headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "follow",
    });

    // پاسخ عیناً برمی‌گردد (stream بدون بافر — برای پاسخ‌های stream چت مهم است)
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: upstream.headers,
    });
  },
};
