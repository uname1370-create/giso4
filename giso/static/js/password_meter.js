/* نمایشگر قدرت رمز جدید — فقط فیلدهای ساخت/تغییر (class=giso-pw-new). ورود را لمس نمی‌کند. */
(function () {
    "use strict";

    var LABELS = { weak: "ضعیف", medium: "متوسط", strong: "قوی" };
    var COLORS = { weak: "#dc2626", medium: "#d97706", strong: "#16a34a" };
    var WIDTHS = { weak: "33%", medium: "66%", strong: "100%" };

    function strength(pw) {
        pw = String(pw || "");
        var n = pw.length;
        var hasLetter = /[A-Za-z\u0600-\u06FF]/.test(pw);
        var hasDigit = /[0-9\u06F0-\u06F9\u0660-\u0669]/.test(pw);
        var hasUpper = /[A-Z]/.test(pw);
        var hasLower = /[a-z]/.test(pw);
        var hasSpecial = /[^A-Za-z0-9\u0600-\u06FF\u06F0-\u06F9\u0660-\u0669]/.test(pw);
        if (n > 8 && hasUpper && hasLower && hasDigit && hasSpecial) return "strong";
        if (hasLetter && hasDigit && n >= 6) return "medium";
        return "weak";
    }

    function attach(input) {
        if (!input || input.dataset.gisoPwMeter === "1") return;
        input.dataset.gisoPwMeter = "1";
        var wrap = document.createElement("div");
        wrap.className = "giso-pw-meter";
        wrap.style.marginTop = "6px";
        var bar = document.createElement("span");
        bar.style.display = "block";
        bar.style.height = "6px";
        bar.style.borderRadius = "99px";
        bar.style.background = "#e5e7eb";
        bar.style.overflow = "hidden";
        var fill = document.createElement("i");
        fill.style.display = "block";
        fill.style.height = "100%";
        fill.style.width = "0";
        fill.style.transition = "width .2s, background .2s";
        bar.appendChild(fill);
        var label = document.createElement("small");
        label.style.fontSize = "12px";
        label.style.display = "block";
        label.style.marginTop = "4px";
        wrap.appendChild(bar);
        wrap.appendChild(label);
        input.insertAdjacentElement("afterend", wrap);

        function paint() {
            var v = input.value || "";
            if (!v) {
                fill.style.width = "0";
                label.textContent = "";
                return;
            }
            var s = strength(v);
            fill.style.width = WIDTHS[s];
            fill.style.background = COLORS[s];
            label.textContent = "قدرت رمز: " + LABELS[s];
            label.style.color = COLORS[s];
        }
        input.addEventListener("input", paint);
        paint();
    }

    function boot() {
        document.querySelectorAll("input.giso-pw-new").forEach(attach);
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
    window.gisoPasswordStrength = strength;
})();
