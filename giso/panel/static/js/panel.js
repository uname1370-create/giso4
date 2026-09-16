/* -*- coding: utf-8 -*-
 * giso/panel/static/js/panel.js — ناوبری پنل ادمین ماژولار (سبک)
 * - سوییچ drawer در موبایل
 * - هایلایت آیتم فعال منو
 */
(function () {
    'use strict';
    document.addEventListener('DOMContentLoaded', function () {
        var sidebar = document.getElementById('pnlSidebar');
        var overlay = document.getElementById('pnlOverlay');
        var burger = document.getElementById('pnlBurger');
        var closeBtn = document.getElementById('pnlSidebarClose');

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

        // بستن خودکار جزئیات‌ها در باز شدن یکی دیگر
        document.querySelectorAll('.pnl-details').forEach(function (d) {
            d.addEventListener('toggle', function () {
                if (d.open) {
                    document.querySelectorAll('.pnl-details[open]').forEach(function (o) {
                        if (o !== d) o.removeAttribute('open');
                    });
                }
            });
        });
    });
})();

// ─── فاز 4.9: پیشخوان تعاملی — کلیک روی کارت → نمایش لیست همان بخش ───
(function () {
    var kpis = document.getElementById('pnlKpis');
    if (!kpis) return;
    kpis.addEventListener('click', function (e) {
        var btn = e.target.closest('.pnl-kpi[data-list]');
        if (!btn) return;
        var key = btn.getAttribute('data-list');
        // مخفی کردن همه لیست‌ها
        document.querySelectorAll('.pnl-dash-list').forEach(function (el) { el.hidden = true; });
        var target = document.getElementById('list-' + key);
        if (target) {
            target.hidden = false;
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        // هایلایت کارت فعال
        document.querySelectorAll('#pnlKpis .pnl-kpi').forEach(function (k) { k.classList.remove('active'); });
        btn.classList.add('active');
    });
})();

// ─── فاز اصلاح: 🔔 Bell اعلان‌ها — dropdown + داده زنده از /admin/notifications/data ───
(function () {
    'use strict';
    var bell = document.getElementById('pnlBell');
    if (!bell) return;
    var btn = document.getElementById('pnlBellBtn');
    var drop = document.getElementById('pnlBellDrop');
    var body = document.getElementById('pnlBellDropBody');
    var count = document.getElementById('pnlBellCount');

    function setCount(n) {
        n = parseInt(n, 10) || 0;
        if (!count) return;
        if (n > 0) {
            count.textContent = String(n);
            count.style.display = '';
            if (btn) btn.classList.add('has-unread');
        } else {
            count.style.display = 'none';
            if (btn) btn.classList.remove('has-unread');
        }
    }

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function loadData() {
        if (!body) return;
        body.innerHTML = '<div class="pnl-bell-loading">در حال دریافت…</div>';
        try {
            fetch('/admin/notifications/data', { headers: { 'Accept': 'application/json' } })
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    if (!d || !d.ok) { body.innerHTML = '<div class="pnl-bell-empty">خطا در دریافت اعلان‌ها.</div>'; return; }
                    setCount(d.unread || 0);
                    if (!d.items || !d.items.length) {
                        body.innerHTML = '<div class="pnl-bell-empty"><i class="fas fa-bell-slash"></i> اعلانی وجود ندارد.</div>';
                        return;
                    }
                    var html = '';
                    d.items.forEach(function (n) {
                        var un = n.status === 'unread' ? ' pnl-bell-unread' : '';
                        var inner = '<span class="pnl-bell-item-ico">' + esc(n.icon || '🔔') + '</span>'
                            + '<div class="pnl-bell-item-body">'
                            + '<strong>' + esc(n.title) + '</strong>'
                            + (n.cat_fa ? '<span class="pnl-bell-cat">' + esc(n.cat_fa) + '</span> ' : '')
                            + '<small>' + esc((n.message || '').slice(0, 90)) + '</small>'
                            + '<small dir="ltr" style="display:block;opacity:.7;">' + esc(n.created_at || '') + '</small>'
                            + '</div>';
                        if (n.url) {
                            html += '<div class="pnl-bell-item' + un + '"><a href="' + esc(n.url) + '">' + inner + '</a></div>';
                        } else {
                            html += '<div class="pnl-bell-item' + un + '">' + inner + '</div>';
                        }
                    });
                    body.innerHTML = html;
                })
                .catch(function () { body.innerHTML = '<div class="pnl-bell-empty">خطا در دریافت اعلان‌ها.</div>'; });
        } catch (e) {
            body.innerHTML = '<div class="pnl-bell-empty">خطا در دریافت اعلان‌ها.</div>';
        }
    }

    function toggle() {
        if (!drop) return;
        var hidden = drop.hasAttribute('hidden');
        if (hidden) {
            drop.removeAttribute('hidden');
            loadData();
        } else {
            drop.setAttribute('hidden', '');
        }
    }
    if (btn) btn.addEventListener('click', function (e) { e.stopPropagation(); toggle(); });
    document.addEventListener('click', function (e) {
        if (bell && !bell.contains(e.target) && drop) drop.setAttribute('hidden', '');
    });
    // مقداردهی اولیه از data-unread (بدون fetch تا وقتی باز نشده)
    setCount(parseInt(bell.getAttribute('data-unread') || '0', 10));
})();

// ─── فاز جامع UX: سیستم تب برای ماژول‌های پنل ──────────────────────────
// ساختار قالب: <div class="pnl-tabs" data-tabs><span class="pnl-tab" data-pane="key">…</span></div>
// و سکشن‌ها: <section class="pnl-pane" id="pane-key">…</section>
// رفتار: کلیک → فقط همان تب نمایان شود؛ انتخاب در location.hash ذخیره می‌شود؛
//        در همه فرم‌های داخل پین فیلد مخفی _back_tab تزریق می‌شود تا بعد از POST به همین تب برگردیم.
(function () {
    'use strict';
    function activate(bar, key) {
        bar.querySelectorAll('.pnl-tab').forEach(function (t) {
            t.classList.toggle('active', t.getAttribute('data-pane') === key);
        });
        var section = bar.closest('.pnl-page') || document;
        document.querySelectorAll('.pnl-pane').forEach(function (p) {
            p.classList.toggle('show', p.id === 'pane-' + key);
        });
        // تزریق فیلد برگشت به تب برای همه فرم‌ها
        document.querySelectorAll('form').forEach(function (f) {
            if (!f.method || f.method.toLowerCase() !== 'post') return;
            var existing = f.querySelector('input[name="_back_tab"]');
            if (existing) { existing.value = key; return; }
            var h = document.createElement('input');
            h.type = 'hidden'; h.name = '_back_tab'; h.value = key;
            f.appendChild(h);
        });
    }
    document.querySelectorAll('.pnl-tabs[data-tabs]').forEach(function (bar) {
        var initial = (location.hash || '').replace(/^#pane-|^#/, '');
        var first = bar.querySelector('.pnl-tab');
        var keys = Array.prototype.map.call(bar.querySelectorAll('.pnl-tab'), function (t) { return t.getAttribute('data-pane'); });
        if (keys.indexOf(initial) < 0) initial = first ? first.getAttribute('data-pane') : '';
        bar.addEventListener('click', function (e) {
            var t = e.target.closest('.pnl-tab');
            if (!t) return;
            var key = t.getAttribute('data-pane');
            activate(bar, key);
            try { history.replaceState(null, '', '#pane-' + key); } catch (err) {}
        });
        if (initial) activate(bar, initial);
    });
})();
