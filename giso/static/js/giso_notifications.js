/* ═══════════════════════════════════════════════════════════════
   گیسو — نوتیفیکیشن درون‌سایتی (Bell + Toast) — بدون وابستگی خارجی
   - فقط برای کاربر لاگین‌شده فعال است (بلوک gisoSiteBellWrap رندر می‌شود)
   - هر ۳۰ ثانیه: /api/notifications/poll → badge + toast برای اعلان‌های جدید
   - flashهای صفحه (عملیات کاربر) به‌صورت toast نمایش داده می‌شوند
     (اگر JS خاموش باشد، alertهای inline قبلی دست‌نخورده می‌مانند)
   ═══════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  var wrap = document.getElementById("gisoSiteBellWrap");
  var toastWrap = document.getElementById("gisoToastWrap");
  if (!wrap || !toastWrap) return;

  var bell = document.getElementById("gisoSiteBell");
  var badge = document.getElementById("gisoSiteBellBadge");
  var drop = document.getElementById("gisoSiteBellDrop");
  var body = document.getElementById("gisoSiteBellBody");
  if (!bell || !badge || !drop || !body) return;

  var POLL_MS = 30000;      // polling هر ۳۰ ثانیه
  var TOAST_MS = 5000;      // محو خودکار بعد از ۵ ثانیه
  var MAX_TOASTS = 3;       // حداکثر toast هم‌زمان
  var SEEN_KEY = "giso_seen_notifs";
  var SEEN_MAX = 50;

  var FA = "0123456789", FA_FA = "۰۱۲۳۴۵۶۷۸۹";
  function faNum(n) {
    return String(n).replace(/[0-9]/g, function (d) { return FA_FA[FA.indexOf(d)]; });
  }
  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }
  var seen = {};
  try { seen = JSON.parse(sessionStorage.getItem(SEEN_KEY) || "{}") || {}; } catch (e) { seen = {}; }
  function saveSeen() {
    try {
      var keys = Object.keys(seen);
      if (keys.length > SEEN_MAX) {
        keys.sort().slice(0, keys.length - SEEN_MAX).forEach(function (k) { delete seen[k]; });
      }
      sessionStorage.setItem(SEEN_KEY, JSON.stringify(seen));
    } catch (e) { /* ignore */ }
  }

  /* ─── Toast ─── */
  function showToast(icon, title, message, url) {
    if (document.querySelectorAll("#gisoToastWrap .giso-toast").length >= MAX_TOASTS) return;
    var el = document.createElement("div");
    el.className = "giso-toast";
    el.setAttribute("role", "status");
    var ic = document.createElement("span");
    ic.className = "giso-toast-icon";
    ic.textContent = icon || "🔔";
    var tx = document.createElement("div");
    tx.className = "giso-toast-text";
    var st = document.createElement("strong");
    st.textContent = title || "اعلان";
    tx.appendChild(st);
    if (message) {
      var sp = document.createElement("span");
      sp.textContent = message;
      tx.appendChild(sp);
    }
    el.appendChild(ic);
    el.appendChild(tx);
    if (url) {
      el.style.cursor = "pointer";
      el.addEventListener("click", function () { window.location.href = url; });
    }
    toastWrap.appendChild(el);
    requestAnimationFrame(function () { el.classList.add("show"); });
    setTimeout(function () {
      el.classList.remove("show");
      setTimeout(function () { el.remove(); }, 400);
    }, TOAST_MS);
  }

  /* ─── Badge + Dropdown ─── */
  function renderBadge(n) {
    if (n > 0) {
      badge.hidden = false;
      badge.textContent = n > 99 ? "99+" : faNum(n);
      badge.classList.add("has-unread");
    } else {
      badge.hidden = true;
      badge.classList.remove("has-unread");
    }
  }
  function renderDrop(items) {
    body.innerHTML = "";
    if (!items || !items.length) {
      var p = document.createElement("p");
      p.className = "giso-bell-empty";
      p.textContent = "هنوز اعلانی ندارید 🌸";
      body.appendChild(p);
      return;
    }
    items.forEach(function (it) {
      var a = document.createElement("a");
      a.className = "giso-bell-item" + (it.unread ? " is-unread" : "");
      a.href = it.url || "#";
      var ic = document.createElement("span");
      ic.className = "giso-bell-icon";
      ic.textContent = it.icon || "🔔";
      var tx = document.createElement("span");
      tx.className = "giso-bell-text";
      var st = document.createElement("strong");
      st.textContent = it.title || "اعلان";
      tx.appendChild(st);
      if (it.message) {
        var sp = document.createElement("span");
        sp.textContent = it.message;
        tx.appendChild(sp);
      }
      a.appendChild(ic);
      a.appendChild(tx);
      body.appendChild(a);
    });
  }

  /* ─── Poll ─── */
  function poll() {
    return fetch("/api/notifications/poll", {
      headers: { "Accept": "application/json" },
      credentials: "same-origin"
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.ok) return;
        renderBadge(d.unread || 0);
        renderDrop(d.items || []);
        (d.items || []).forEach(function (it) {
          if (it.unread && it.id != null && !seen[it.id]) {
            seen[it.id] = 1;
            showToast(it.icon, it.title, it.message, it.url);
          }
        });
        saveSeen();
      })
      .catch(function () { /* شبکه قطع — تلاش بعدی */ });
  }

  /* ─── Dropdown open/close ─── */
  var dropOpen = false;
  function setDrop(open) {
    if (open === dropOpen) return;
    dropOpen = open;
    drop.hidden = !open;
    bell.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) poll();
  }
  bell.addEventListener("click", function (e) {
    e.stopPropagation();
    setDrop(!dropOpen);
  });
  document.addEventListener("click", function (e) {
    if (dropOpen && !wrap.contains(e.target)) setDrop(false);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") setDrop(false);
  });

  /* ─── Flashهای فعلی صفحه → toast (بدون تکرار با alert inline) ─── */
  var flashEl = document.getElementById("gisoFlashData");
  if (flashEl) {
    try {
      var flashes = JSON.parse(flashEl.textContent || "[]");
      if (flashes && flashes.length) {
        setTimeout(function () {
          flashes.forEach(function (f) {
            var cat = String(f[0] || "info").toLowerCase();
            var icon = { success: "✅", danger: "⚠️", warning: "⚠️", info: "ℹ️" }[cat] || "🔔";
            var title = { success: "انجام شد", danger: "خطا", warning: "توجه", info: "اطلاعیه" }[cat] || "اطلاعیه";
            showToast(icon, title, f[1]);
          });
          var inline = document.querySelector(".giso-flash-wrap");
          if (inline) inline.classList.add("giso-flash-toasted");
        }, 300);
      }
    } catch (e) { /* ignore */ }
  }

  /* ─── شروع: در تب مخفی هیچ درخواست شبکه‌ای ارسال نمی‌شود ─── */
  var pollTimer = null;
  function schedulePoll(delay) {
    clearTimeout(pollTimer);
    if (document.hidden) { pollTimer = null; return; }
    pollTimer = setTimeout(function () {
      Promise.resolve(poll()).finally(function () { schedulePoll(POLL_MS); });
    }, delay == null ? POLL_MS : delay);
  }
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { clearTimeout(pollTimer); pollTimer = null; }
    else schedulePoll(0);
  });
  poll();
  schedulePoll(POLL_MS);
})();
