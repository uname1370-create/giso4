/* -*- coding: utf-8 -*-
 * giso/panel_user/static/js/ai_assistant.js
 * دستیار هوشمند گیسو — چت درون‌صفحه‌ای پنل کاربری.
 *
 * از همان backend ویجت سایت استفاده می‌کند (/api/ai-widget/init و /api/ai-widget/chat)
 * تا رفتار و دسترسیِ «گزارش‌محور» آن یکپارچه بماند.
 */
(function () {
    'use strict';

    var el = {
        card: document.getElementById('puAssistCard'),
        body: document.getElementById('puAssistBody'),
        form: document.getElementById('puAssistForm'),
        input: document.getElementById('puAssistInput'),
        send: document.getElementById('puAssistSend'),
        chips: document.querySelectorAll('.pu-assist-chip'),
        name: document.getElementById('puAssistName'),
        sub: document.getElementById('puAssistSub'),
    };

    if (!el.body || !el.form) {
        // اگر عناصر چت روی صفحه نبود، هیچ کاری نکن.
        return;
    }

    var csrf = '';
    var busy = false;
    var pagePath = '/dashboard/assistant';

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function linkify(s) {
        return esc(s).replace(/(https?:\/\/[^\s<]+|tel:[^\s<]+)/g, function (m) {
            return '<a href="' + m + '" target="_blank" rel="noopener">' + m + '</a>';
        });
    }

    function addMsg(text, who) {
        var d = document.createElement('div');
        d.className = 'pu-msg pu-msg-' + (who || 'bot');
        d.innerHTML = linkify(text);
        el.body.appendChild(d);
        el.body.scrollTop = el.body.scrollHeight;
        return d;
    }

    function addNote(text) {
        var d = document.createElement('div');
        d.className = 'pu-msg pu-msg-note';
        d.textContent = text;
        el.body.appendChild(d);
        el.body.scrollTop = el.body.scrollHeight;
        return d;
    }

    function setTyping(on) {
        var tp = document.getElementById('puAssistTyping');
        if (on) {
            if (!tp) {
                tp = document.createElement('div');
                tp.id = 'puAssistTyping';
                tp.className = 'pu-assist-typing';
                tp.innerHTML = '<i></i><i></i><i></i>';
                el.body.appendChild(tp);
            }
            el.body.scrollTop = el.body.scrollHeight;
        } else if (tp) {
            tp.remove();
        }
    }

    function setSend(disabled) {
        if (el.send) el.send.disabled = disabled;
        if (el.input) el.input.disabled = disabled;
    }

    function renderHistory(history) {
        (history || []).forEach(function (m) {
            if (!m || typeof m.content !== 'string') return;
            addMsg(m.content, m.role === 'user' ? 'user' : 'bot');
        });
    }

    function send(text) {
        text = (text || '').trim();
        if (!text || busy) return;
        busy = true;
        setSend(true);
        addMsg(text, 'user');
        el.input.value = '';
        setTyping(true);

        fetch('/api/ai-widget/chat?page=' + encodeURIComponent(pagePath), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-AI-Widget-CSRF': csrf },
            body: JSON.stringify({ message: text, page: pagePath })
        }).then(function (r) {
            return r.json().then(function (data) { return { status: r.status, data: data }; });
        }).then(function (res) {
            setTyping(false);
            if (res.status === 402 || res.status === 429) {
                addNote((res.data && res.data.error) || 'سهمیه گفتگو امروز تکمیل شده است.');
                return;
            }
            if (res.status === 403) {
                addNote('نشست گفتگو منقضی شده است؛ صفحه را نوسازی کن و دوباره تلاش کن.');
                return;
            }
            if (res.status === 503) {
                addNote((res.data && res.data.error) || 'مشاور هوشمند سایت فعلاً غیرفعال است.');
                return;
            }
            if (!res.data || !res.data.ok) {
                addNote((res.data && res.data.error) || 'پاسخی آماده نشد؛ کمی بعد دوباره بپرس.');
                return;
            }
            addMsg(res.data.response || 'پاسخی نرسید.', 'bot');
        }).catch(function () {
            setTyping(false);
            addNote('ارتباط برقرار نشد؛ اتصال اینترنت و دوباره تلاش کن.');
        }).finally(function () {
            busy = false;
            setSend(false);
            el.input.focus();
        });
    }

    function init() {
        fetch('/api/ai-widget/init?page=' + encodeURIComponent(pagePath))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data && data.csrf_token) csrf = data.csrf_token;
                if (el.name && data && data.display_name) el.name.textContent = data.display_name;
                if (el.sub && data && data.role) {
                    el.sub.textContent = 'همراه گزارش‌محور در پنل کاربری';
                }
                if (data && data.welcome) addMsg(data.welcome, 'bot');
                renderHistory(data && data.history);
                if (data && data.summary) addNote('خلاصه تو از گیسو: ' + data.summary);
            })
            .catch(function () {
                addNote('دستیار در دسترس نیست؛ فعلاً از منوی کناری به بخش‌ها برو.');
            });
    }

    el.form.addEventListener('submit', function (e) {
        e.preventDefault();
        send(el.input ? el.input.value : '');
    });
    if (el.input) {
        el.input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send(el.input.value);
            }
        });
        el.input.addEventListener('input', function () {
            el.input.style.height = 'auto';
            el.input.style.height = Math.min(el.input.scrollHeight, 120) + 'px';
        });
    }

    Array.prototype.forEach.call(el.chips, function (chip) {
        chip.addEventListener('click', function () {
            var q = chip.getAttribute('data-q') || chip.textContent.trim();
            if (el.input) el.input.value = q;
            send(q);
        });
    });

    init();
})();
