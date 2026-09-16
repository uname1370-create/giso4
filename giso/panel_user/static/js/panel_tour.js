/* -*- coding: utf-8 -*-
 * giso/panel_user/static/js/panel_tour.js
 * راهنمای پنل کاربری گیسو — تور اسپات‌لایت سبک و بدون کتابخانه.
 *
 * - راهنمای «پیشخوان» (overview) در اولین ورود خودکار اجرا می‌شود.
 * - برای هر بخش، وقتی اولین‌بار وارد همان صفحه می‌شوی، راهنمای مخصوصِ همان بخش
 *   اجرا می‌شود (ذخیرهٔ «دیده‌شد» per-module در localStorage).
 * - «?tour=1» راهنمای مرتبِ کاملِ همهٔ بخش‌ها را به ترتیب سایدبار نشان می‌دهد.
 */
(function () {
    'use strict';

    var SEEN_PREFIX = 'giso_pu_tour_seen_';

    // ── راهنمای کاملِ پیشخوان ──────────────────────────────────────────
    var OVERVIEW_STEPS = [
        { icon: '🌸', title: 'به پنل اختصاصی گیسو خوش آمدی', sub: 'راهنمای کوتاه پنل کاربری',
          body: 'همه‌چیز همین‌جاست: <b>آنالیز مو و پوست</b>، <b>فروش مو</b>، <b>خرید از فروشگاه</b>، <b>کیف پول</b> و <b>گفتگو با کارشناس‌ها</b>.', target: null },
        { icon: '🪄', title: 'از کجا شروع کنم؟', sub: 'اقدام بعدی تو همین‌جاست',
          body: 'کارت <b>«اقدام بعدی»</b> همیشه یک قدم جلوی توست؛ مثلاً شروع آنالیز رایگان یا پیگیری فروش مو.', target: '.pu-next-action' },
        { icon: '🔬', title: 'آنالیزها و برنامه من', sub: 'دسترسی از منو و کارت‌های پایین',
          body: 'تحلیل <b>مو</b> و <b>پوست</b> و برنامه مراقبتی را از منوی کناری یا کارت آمار می‌بینی.', target: '.pu-kpis .pu-kpi:nth-child(1)' },
        { icon: '💇‍♀️', title: 'فروش مو و مدیریت مو', sub: 'گروه «مدیریت مو»',
          body: 'از گروه <b>مدیریت مو</b> می‌توانی به <b>فروش مو به گیسو</b>، <b>بازارچه مو</b> و <b>خریدار مو</b> بروی.', target: '.pu-kpis .pu-kpi:nth-child(3)' },
        { icon: '💰', title: 'کیف پول و اعتبار', sub: 'بالای صفحه همیشه پیداست',
          body: 'موجودی <b>نقدی</b> و <b>اعتبار مصرفی</b> این‌جاست؛ با مأموریت‌ها اعتبار هدیه بگیر.', target: '.pu-credit-chip' },
        { icon: '🔔', title: 'اعلان‌ها و پیام‌ها', sub: 'هیچ خبری را از دست نده',
          body: 'زنگ بالای صفحه برای اعلان‌ها و منوهای <b>پیام‌ها و پشتیبانی</b> برای گفتگو با کارشناس‌هاست.', target: '#puBellBtn' },
        { icon: '✨', title: 'حالا نوبت توست!', sub: 'پایان راهنما',
          body: 'برای دوباره دیدن راهنما از لینک <b>«راهنمای پنل ❔»</b> در پایین منو اجرا کن. موفق باشی 🌸', target: null, isFinal: true }
    ];

    // ── راهنمای هر بخش (per-module) ────────────────────────────────────
    var MODULE_STEPS = {
        overview: OVERVIEW_STEPS,
        hair_sale: [
            { icon: '💇‍♀️', title: 'فروش مو به گیسو', sub: 'قدم اول: ثبت درخواست',
              body: 'این بخش برای <b>فروش مو به گیسو</b> است؛ درخواستت را ثبت کن تا کارشناس قیمت بدهد. وضعیت/قیمت همین‌جا پیگیری می‌شود.', target: null },
            { icon: '🏪', title: 'بازارچه مو', sub: 'زیرمجموعهٔ مدیریت مو',
              body: 'آگهی‌های <b>قیمت‌گذاری‌شدهٔ</b> تو این‌جاست؛ پیشنهادها و گفتگوها را همین‌جا می‌بینی.', target: null, isFinal: true }
        ],
        marketplace: [
            { icon: '🏪', title: 'بازارچه مو', sub: 'آگهی و پیشنهاد',
              body: 'آگهی‌هایت، پیشنهادهای خریدار و گفتگوها این‌جاست؛ برای ثبت آگهی از «ثبت آگهی» استفاده کن.', target: null, isFinal: true }
        ],
        buyer_request: [
            { icon: '🧑‍💼', title: 'خریدار مو', sub: 'نیازت را ثبت کن',
              body: 'اگر دنبال خرید مو هستی، نیازت را ثبت کن تا فروشنده‌ها پیشنهاد بدهند.', target: null, isFinal: true }
        ],
        orders: [
            { icon: '🛍️', title: 'خریدهای من از فروشگاه', sub: 'وضعیت خرید و فاکتور',
              body: 'سفارش‌های فروشگاه، وضعیت ارسال و <b>ویرایش امن</b> سفارش این‌جاست؛ کد پیگیری را از همین‌جا می‌گیری.', target: null, isFinal: true }
        ],
        analyses: [
            { icon: '🔬', title: 'آنالیزها و برنامه من', sub: 'گزارش، برنامه و راهکار',
              body: 'تحلیل‌های مو و پوست، گزارش و برنامهٔ مراقبتی و چک‌لیست این‌جاست؛ برای تحلیل جدید به «انجام تحلیل» برو.', target: null, isFinal: true }
        ],
        wallet: [
            { icon: '💰', title: 'کیف پول و اعتبار', sub: 'موجودی نقدی و مصرفی',
              body: 'موجودی نقدی (قابل تسویه) و اعتبار مصرفی، <b>شارژ با رسید</b>، <b>تسویه</b> و <b>مأموریت‌ها</b> این‌جاست.', target: null, isFinal: true }
        ],
        chats: [   // پیام‌ها و پشتیبانی
            { icon: '💬', title: 'پیام‌ها و پشتیبانی', sub: 'تیکت و گزارش باگ',
              body: 'گفتگوها و تیکت‌های پشتیبانی این‌جاست؛ از «پشتیبانی» پیام بده و از «گزارش باگ» مشکل را اعلام کن.', target: null, isFinal: true }
        ],
        profile: [
            { icon: '👤', title: 'پروفایل', sub: 'نام، شهر و خلاصه فعالیت',
              body: 'نام، شهر و خلاصه فعالیتت این‌جاست؛ تغییر رمز و ویرایش اطلاعات از همین صفحه است.', target: null, isFinal: true }
        ],
        beauty_center: [
            { icon: '🏥', title: 'مرکز زیبایی من', sub: 'مدیریت مرکز',
              body: 'اطلاعات مرکز، آلبوم، تخفیف، ارتقا و تمدید و پیام‌ها این‌جاست؛ فقط اگر مرکز داشته باشی این منو می‌آید.', target: null, isFinal: true }
        ],
        reviews: [
            { icon: '⭐', title: 'نظرها و امتیازها', sub: 'بازخورد تو',
              body: 'نظرات و امتیازهای تو دربارهٔ خدمات و محصولات این‌جاست.', target: null, isFinal: true }
        ],
        notifications: [
            { icon: '📣', title: 'اعلان‌های من', sub: 'خبرهای مربوط به تو',
              body: 'اعلان‌های سفارش، تأیید و خبرهای تو این‌جاست.', target: null, isFinal: true }
        ],
        wishlist: [
            { icon: '❤️', title: 'علاقه‌مندی‌ها', sub: 'ذخیره‌شده‌ها',
              body: 'محصولات و مواردی که برای بعد ذخیره کردی این‌جاست.', target: null, isFinal: true }
        ],
        shop: [
            { icon: '🛒', title: 'فروشگاه من', sub: 'خرید از فروشگاه گیسو',
              body: 'کاتالوگ محصولات و خرید با پرداخت امن این‌جاست؛ سفارش‌هایت در «خریدهای من» پیگیری می‌شود.', target: null, isFinal: true }
        ],
        ai_assistant: [
            { icon: '🤖', title: 'دستیار هوشمند گیسو', sub: 'همراه گزارش‌محور تو در پنل',
              body: 'سؤال کوتاهت را بنویس یا یکی از <b>سؤال‌های پرکاربرد</b> را بزن تا بر اساس داده‌های خودت گزارش و پیشنهاد بگیری.', target: '.pu-assist-card' },
            { icon: '✨', title: 'فقط گزارش؛ بدون تغییر', sub: 'امن و فقط‌خواندنی',
              body: 'این دستیار فقط گزارش، تحلیل و پیشنهاد می‌دهد و هیچ تغییری روی داده‌هایت نمی‌دهد.', target: null, isFinal: true }
        ]
    };

    // ترتیب بخش‌ها برای راهنمای مرتبِ کامل (مطابق سایدبار)
    var FULL_ORDER = ['overview', 'hair_sale', 'marketplace', 'buyer_request',
                      'orders', 'analyses', 'wallet', 'chats', 'profile', 'beauty_center'];

    function isMobile() { return window.innerWidth <= 860; }

    function seenKey(module) { return SEEN_PREFIX + (module || 'overview') + '_v1'; }
    function seenBefore(module) {
        try { return localStorage.getItem(seenKey(module)) === '1'; } catch (e) { return false; }
    }
    function markSeen(module) {
        try { localStorage.setItem(seenKey(module), '1'); } catch (e) {}
    }

    function moduleOf() {
        try {
            var b = document.body;
            return (b && b.getAttribute('data-pu-module')) || 'overview';
        } catch (e) { return 'overview'; }
    }

    function stepsFor(module) {
        return MODULE_STEPS[module] || [{
            icon: '🧭', title: 'این بخش از پنل کاربری', sub: 'راهنمای سریع',
            body: 'این صفحه بخشی از پنل کاربری گیسوست؛ از منوی کناری می‌توانی به بقیهٔ بخش‌ها بروی.',
            target: null, isFinal: true
        }];
    }

    // state
    var layer = null, dim = null, ring = null, card = null, index = 0, auto = false, queue = [], currentModule = 'overview';

    function build() {
        if (layer) return;
        layer = document.createElement('div');
        layer.className = 'pu-tour-layer';
        layer.setAttribute('role', 'dialog');
        layer.setAttribute('aria-modal', 'true');
        layer.setAttribute('aria-label', 'راهنمای پنل کاربری');
        dim = document.createElement('div'); dim.className = 'pu-tour-dim';
        ring = document.createElement('div'); ring.className = 'pu-tour-ring';
        card = document.createElement('div'); card.className = 'pu-tour-card';
        layer.appendChild(dim); layer.appendChild(ring); layer.appendChild(card);
        document.body.appendChild(layer);
        dim.addEventListener('click', finish);
        card.addEventListener('click', function (e) {
            var btn = e.target.closest ? e.target.closest('[data-act]') : null;
            if (!btn) return;
            if (btn.getAttribute('data-act') === 'next') next();
            else finish();
        });
    }

    function dotsHtml() {
        var out = '';
        for (var i = 0; i < queue.length; i++) {
            out += '<i class="' + (i === index ? 'is-on' : '') + '"></i>';
        }
        return '<div class="pu-tour-dots">' + out + '</div>';
    }

    function placeRing(el) {
        if (!el || isMobile()) { ring.style.display = 'none'; return; }
        try { el.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' }); } catch (e) {}
        var rect = el.getBoundingClientRect();
        if (!rect || (rect.width === 0 && rect.height === 0)) { ring.style.display = 'none'; return; }
        var pad = 6;
        ring.style.display = 'block';
        ring.style.top = (rect.top - pad) + 'px';
        ring.style.left = (rect.left - pad) + 'px';
        ring.style.width = (rect.width + pad * 2) + 'px';
        ring.style.height = (rect.height + pad * 2) + 'px';
    }

    function render() {
        var s = queue[index];
        var isLast = index === queue.length - 1;
        card.innerHTML =
            '<div class="pu-tour-head">' +
                '<span class="pu-tour-ico">' + s.icon + '</span>' +
                '<div><strong>' + s.title + '</strong>' +
                (s.sub ? '<small>' + s.sub + '</small>' : '') + '</div>' +
            '</div>' +
            '<div class="pu-tour-body">' + s.body + '</div>' +
            dotsHtml() +
            '<div class="pu-tour-foot">' +
                '<button type="button" class="pu-tour-btn pu-tour-skip" data-act="skip">رد کردن ✕</button>' +
                '<button type="button" class="pu-tour-btn pu-tour-next" data-act="next">' +
                    (isLast ? 'شروع کن! 🚀' : 'بعدی ←') +
                '</button>' +
            '</div>';
        placeRing(resolveTarget(s));
    }

    function resolveTarget(step) {
        if (!step || !step.target) return null;
        try { return document.querySelector(step.target); } catch (e) { return null; }
    }

    function next() {
        if (index < queue.length - 1) {
            index++;
            render();
        } else {
            finish();
        }
    }

    function open(module, steps, startAuto) {
        build();
        index = 0;
        auto = !!startAuto;
        currentModule = module;
        queue = steps.slice();
        layer.classList.add('is-open');
        document.body.style.overflow = 'hidden';
        render();
    }

    function finish() {
        if (!layer) return;
        layer.classList.remove('is-open');
        ring.style.display = 'none';
        document.body.style.overflow = '';
        if (auto) markSeen(currentModule);
    }

    window.PuTour = { start: function () {
        // راهنمای مرتبِ کاملِ همهٔ بخش‌ها
        var m = moduleOf();
        var full = [];
        FULL_ORDER.forEach(function (mod) {
            stepsFor(mod).forEach(function (s) { full.push(s); });
        });
        open('overview', full, false);
    } };

    document.addEventListener('DOMContentLoaded', function () {
        try {
            var forced = /[?&]tour=1/.test(window.location.search || '');
            if (forced) { window.PuTour.start(); return; }
            var m = moduleOf();
            if (!seenBefore(m)) {
                setTimeout(function () { open(m, stepsFor(m), true); }, 700);
            }
        } catch (e) { /* راهنما نباید جریان پنل را بشکند */ }
    });
})();
