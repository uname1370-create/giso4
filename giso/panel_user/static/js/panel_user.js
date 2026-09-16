/* -*- coding: utf-8 -*-
 * giso/panel_user/static/js/panel_user.js — ناوبری پنل کاربر ماژولار (سبک)
 */
(function () {
    'use strict';
    document.addEventListener('DOMContentLoaded', function () {
        var sidebar = document.getElementById('puSidebar');
        var overlay = document.getElementById('puOverlay');
        var burger = document.getElementById('puBurger');
        var closeBtn = document.getElementById('puSidebarClose');

        function openNav() {
            if (!sidebar) return;
            sidebar.classList.add('open');
            if (overlay) overlay.classList.add('show');
        }
        function closeNav() {
            if (!sidebar) return;
            sidebar.classList.remove('open');
            if (overlay) overlay.classList.remove('show');
        }
        if (burger) burger.addEventListener('click', openNav);
        if (closeBtn) closeBtn.addEventListener('click', closeNav);
        if (overlay) overlay.addEventListener('click', closeNav);

        // جلوگیری از باز شدن دو صفحه هنگام کلیک/دابل‌کلیک روی تب‌های کیف پول و
        // سایر لینک‌های ناوبری پنل (رفع باگ «تسویه دو تا پنجره باز می‌کند»):
        // با اولین کلیک ناوبری می‌کنیم و تا بارگذاری صفحه، کلیک‌های بعدی نادیده می‌مانند.
        var navGuard = false;
        document.addEventListener('click', function (e) {
            var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
            if (!a) return;
            // فقط لینک‌های داخلیِ ناوبری (نه خروج، فایل، یا لینک خارجی جدید)
            var href = a.getAttribute('href') || '';
            if (!href || href.charAt(0) === '#' || a.target === '_blank' ||
                href.indexOf('javascript:') === 0 || /^(https?:)?\/\//i.test(href)) {
                return;
            }
            if (navGuard) { e.preventDefault(); e.stopPropagation(); return; }
            navGuard = true;
            setTimeout(function () { navGuard = false; }, 1500);
        }, true);

        // کپی کد/لینک معرفی
        window.copyPuText = function (inputId, btn) {
            var el = document.getElementById(inputId);
            if (!el) return;
            var done = function () {
                var old = btn.textContent;
                btn.textContent = '✓ کپی شد';
                setTimeout(function () { btn.textContent = old; }, 1600);
            };
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(el.value).then(done).catch(function () {
                    el.select();
                    try { document.execCommand('copy'); } catch (e) {}
                    done();
                });
            } else {
                el.select();
                try { document.execCommand('copy'); } catch (e) {}
                done();
            }
        };
    });
})();
