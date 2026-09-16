// ═══ متغیرهای گلوبال ═══
let consultantAnalysisId = null;
let consultantMessageCount = 0;
let consultantIsSending = false;

// ═══ راه‌اندازی مشاور ═══
function initConsultant(analysisId) {
    consultantAnalysisId = analysisId;
    loadConsultantHistory();
}

// ═══ بارگذاری تاریخچه ═══
async function loadConsultantHistory() {
    try {
        const response = await fetch('/api/consultant-chat/history/' + consultantAnalysisId);
        const data = await response.json();

        if (data.ok && data.history) {
            const chatBody = document.getElementById('consultantChatBody');
            chatBody.innerHTML = '';

            data.history.forEach(msg => {
                appendMessage(msg.role, msg.content, false);
            });

            consultantMessageCount = data.history.length;

            // اگر تاریخچه خالی بود، پیام خوش‌آمد بفرست
            if (data.history.length === 0) {
                setTimeout(() => sendInitialGreeting(), 500);
            }

            // نمایش امتیازدهی بعد از ۶ پیام
            if (data.history.length >= 6) {
                showRating();
            }
        }
    } catch (e) {
        console.error('خطا در بارگذاری تاریخچه:', e);
    }
}

// ═══ پیام خوش‌آمد اولیه ═══
function sendInitialGreeting() {
    showTyping();

    // شبیه‌سازی تایپ کردن (بدون درخواست به سرور)
    setTimeout(() => {
        hideTyping();
        const greeting = window.CONSULTANT_GREETING ||
            'سلام دوست عزیز 🌸\n\nمن مشاور هوشمند صادقی هستم. گزارش تحلیل شما رو دیدم. چطور می‌تونم کمکتون کنم؟';
        appendMessage('assistant', greeting, true);
    }, 1500);
}

// ═══ ارسال پیام ═══
async function sendConsultantMessage() {
    if (consultantIsSending) return;

    const input = document.getElementById('consultantInput');
    const message = input.value.trim();

    if (!message) return;

    consultantIsSending = true;

    // نمایش پیام کاربر
    appendMessage('user', message, true);
    input.value = '';
    input.style.height = 'auto';

    // مخفی کردن suggestions بعد از اولین پیام
    document.getElementById('consultantSuggestions').style.display = 'none';

    // نمایش typing
    showTyping();

    try {
        const response = await fetch('/api/consultant-chat/message', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-GISO-CSRF': document.querySelector('meta[name="csrf-token"]')?.content || ''},
            body: JSON.stringify({
                analysis_id: consultantAnalysisId,
                message: message
            })
        });

        const data = await response.json();

        hideTyping();

        if (data.ok) {
            // نمایش پاسخ با انیمیشن تایپ
            appendMessage('assistant', data.response, true);
            renderConsultantCards(data.product_cards, data.nutrition_items);
            consultantMessageCount = data.message_count;

            // بعد از ۶ پیام، امتیازدهی نشون بده
            if (consultantMessageCount >= 6) {
                setTimeout(() => showRating(), 2000);
            }
        } else {
            appendMessage('assistant',
                data.error || 'متأسفم، در حال حاضر مشکلی پیش اومد. لطفاً چند لحظه دیگر تلاش کنید.',
                true);
        }
    } catch (e) {
        hideTyping();
        appendMessage('assistant',
            'متأسفم، خطای شبکه پیش اومد. لطفاً دوباره تلاش کنید.',
            true);
    }

    consultantIsSending = false;
}

// ═══ ارسال پیام پیشنهادی ═══
function sendSuggestedMessage(text) {
    const input = document.getElementById('consultantInput');
    if (input) input.value = text;
    sendConsultantMessage();
}

// ═══ Enter برای ارسال ═══
function handleConsultantEnter(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendConsultantMessage();
    }
}

// ═══ اضافه کردن پیام ═══
function appendMessage(role, content, animate) {
    const chatBody = document.getElementById('consultantChatBody');
    if (!chatBody) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message ' + role;

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';

    const time = new Date().toLocaleTimeString('fa-IR', {
        hour: '2-digit',
        minute: '2-digit'
    });

    if (animate && role === 'assistant') {
        // رندر متن در یک span جدا تا کارت‌های محصول بعد از تایپ سالم بمانند
        const textSpan = document.createElement('span');
        textSpan.className = 'con-text';
        bubble.appendChild(textSpan);
        messageDiv.appendChild(bubble);
        chatBody.appendChild(messageDiv);
        typeAnimation(textSpan, content, 20);
    } else {
        bubble.innerHTML = escapeHtml(content).replace(/\n/g, '<br>');
        messageDiv.appendChild(bubble);
        chatBody.appendChild(messageDiv);
    }

    const timestamp = document.createElement('div');
    timestamp.className = 'chat-timestamp';
    timestamp.textContent = time;
    messageDiv.appendChild(timestamp);

    // اسکرول به پایین
    setTimeout(() => {
        chatBody.scrollTop = chatBody.scrollHeight;
    }, 100);
}

// ═══ رندر کارت محصول فشرده داخل حباب مشاور (قابلیت C) ═══
function renderConsultantCards(productCards, nutritionItems) {
    const chatBody = document.getElementById('consultantChatBody');
    if (!chatBody) return;
    const cards = (productCards || []).slice(0, 3);
    const foods = (nutritionItems || []).slice(0, 3);
    if (!cards.length && !foods.length) return;

    // آخرین حباب مشاور را پیدا کن تا کارت داخل آن اضافه شود
    const msgs = chatBody.querySelectorAll('.chat-message.assistant');
    const last = msgs.length ? msgs[msgs.length - 1] : null;
    const bubble = last ? last.querySelector('.chat-bubble') : null;
    if (!bubble) return;

    const wrap = document.createElement('div');
    wrap.className = 'consultant-cards';

    cards.forEach(card => {
        const row = document.createElement('div');
        row.className = 'consultant-card' + (card.is_special_order ? ' is-food' : '');
        row.innerHTML =
            (card.image_url
                ? '<img src="' + escapeHtml(card.image_url) + '" alt="">'
                : '<span class="con-card-ph">🖼</span>') +
            '<div class="con-card-body">' +
                '<div class="con-card-name">' + escapeHtml(card.name || '') + '</div>' +
                (card.reason ? '<div class="con-card-reason">' + escapeHtml(card.reason) + '</div>' : '') +
                '<div class="con-card-foot">' +
                    '<span class="con-card-price">' + formatNumberFa(card.price) + ' تومان</span>' +
                    '<a class="con-card-btn" href="' + escapeHtml(card.sell_url || '/shop') + '">' +
                        (card.is_special_order ? '📦 سفارش خاص' : 'مشاهده و خرید') +
                    '</a>' +
                '</div>' +
            '</div>';
        wrap.appendChild(row);
    });

    foods.forEach(item => {
        const row = document.createElement('div');
        row.className = 'consultant-card is-food';
        row.innerHTML =
            '<span class="con-card-ph">🥗</span>' +
            '<div class="con-card-body">' +
                '<div class="con-card-name">' + escapeHtml(item.name || '') + '</div>' +
                (item.reason ? '<div class="con-card-reason">' + escapeHtml(item.reason) + '</div>' : '') +
                (item.price ? '<div class="con-card-reason">' + formatNumberFa(item.price) + ' تومان</div>' : '') +
                '<div class="con-card-foot">' +
                    '<a class="con-card-btn" href="' + escapeHtml(item.order_url || '/analysis/plan') + '">📦 سفارش</a>' +
                '</div>' +
            '</div>';
        wrap.appendChild(row);
    });

    bubble.appendChild(wrap);
    setTimeout(() => { chatBody.scrollTop = chatBody.scrollHeight; }, 100);
}

// ═══ فرمت عدد تومانی ═══
function formatNumberFa(value) {
    const n = Number(value || 0);
    if (isNaN(n)) return '0';
    return String(Math.round(n)).replace(/[0-9]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
}

// ═══ انیمیشن تایپ ═══
function typeAnimation(element, text, speed) {
    let index = 0;
    const cleanText = escapeHtml(text);

    function type() {
        if (index < cleanText.length) {
            const char = cleanText[index];
            if (char === '\n') {
                element.innerHTML += '<br>';
            } else {
                element.innerHTML += char;
            }
            index++;

            // اسکرول
            const chatBody = document.getElementById('consultantChatBody');
            if (chatBody) chatBody.scrollTop = chatBody.scrollHeight;

            setTimeout(type, speed);
        }
    }

    type();
}

// ═══ escape HTML ═══
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ═══ نمایش/مخفی typing ═══
function showTyping() {
    const typing = document.getElementById('consultantTyping');
    if (typing) typing.style.display = 'flex';
    const chatBody = document.getElementById('consultantChatBody');
    if (chatBody) chatBody.scrollTop = chatBody.scrollHeight;
}

function hideTyping() {
    const typing = document.getElementById('consultantTyping');
    if (typing) typing.style.display = 'none';
}

// ═══ نمایش امتیازدهی ═══
function showRating() {
    const rating = document.getElementById('consultantRating');
    if (rating && rating.style.display !== 'block') {
        rating.style.display = 'block';
        rating.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    }
}

// ═══ ثبت امتیاز ═══
async function rateConsultant(rating) {
    try {
        // نمایش انتخاب
        document.querySelectorAll('.rating-stars .star').forEach((star, index) => {
            if (index < rating) {
                star.classList.add('selected');
            }
        });
        const ratingBox = document.getElementById('consultantRating');
        if (ratingBox) ratingBox.classList.add('rated');

        // ارسال به سرور
        await fetch('/api/consultant-chat/rate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-GISO-CSRF': document.querySelector('meta[name="csrf-token"]')?.content || ''},
            body: JSON.stringify({
                analysis_id: consultantAnalysisId,
                rating: rating
            })
        });

        // پیام تشکر
        setTimeout(() => {
            if (ratingBox) {
                ratingBox.innerHTML =
                    '<p>🌸 ممنون از نظرت! نظر شما به ما کمک می‌کنه بهتر بشیم.</p>';
            }
        }, 800);
    } catch (e) {
        console.error('خطا در ثبت امتیاز:', e);
    }
}

// ═══ Auto-resize textarea ═══
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('consultantInput');
    if (input) {
        input.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 100) + 'px';
        });
    }
});
