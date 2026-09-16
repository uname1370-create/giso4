/* Persian amount-in-words helper for wallet/mission forms. */
(function () {
  'use strict';
  const faToEn = {'۰':'0','۱':'1','۲':'2','۳':'3','۴':'4','۵':'5','۶':'6','۷':'7','۸':'8','۹':'9','٠':'0','١':'1','٢':'2','٣':'3','٤':'4','٥':'5','٦':'6','٧':'7','٨':'8','٩':'9'};
  const ones = ['', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه'];
  const teens = ['ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده', 'شانزده', 'هفده', 'هجده', 'نوزده'];
  const tens = ['', '', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود'];
  const hundreds = ['', 'صد', 'دویست', 'سیصد', 'چهارصد', 'پانصد', 'ششصد', 'هفتصد', 'هشتصد', 'نهصد'];
  const scales = ['', 'هزار', 'میلیون', 'میلیارد', 'تریلیون', 'کوادریلیون', 'کوینتیلیون'];

  function normalize(value) {
    return String(value || '').replace(/[۰-۹٠-٩]/g, d => faToEn[d]).replace(/[,_\s]/g, '').replace(/[^0-9-]/g, '');
  }
  function triplet(n) {
    const parts = [];
    const h = Math.floor(n / 100);
    const r = n % 100;
    if (h) parts.push(hundreds[h]);
    if (r >= 10 && r < 20) parts.push(teens[r - 10]);
    else {
      const t = Math.floor(r / 10), o = r % 10;
      if (t) parts.push(tens[t]);
      if (o) parts.push(ones[o]);
    }
    return parts.join(' و ');
  }
  function toWords(value) {
    const clean = normalize(value);
    if (!clean || clean === '-') return '';
    let number;
    try { number = BigInt(clean); } catch (_) { return ''; }
    if (number === 0n) return 'صفر';
    const negative = number < 0n;
    if (negative) number = -number;
    const chunks = [];
    let index = 0;
    while (number > 0n && index < scales.length) {
      const chunk = Number(number % 1000n);
      if (chunk) chunks.unshift(triplet(chunk) + (scales[index] ? ' ' + scales[index] : ''));
      number /= 1000n;
      index += 1;
    }
    if (number > 0n) return 'مبلغ بسیار بزرگ';
    return (negative ? 'منفی ' : '') + chunks.join(' و ');
  }
  function bind(input) {
    const targetId = input.getAttribute('data-money-words');
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target) return;
    const render = function () {
      const words = toWords(input.value);
      target.textContent = words ? 'مبلغ به حروف: ' + words + ' تومان' : 'مبلغ به حروف: —';
    };
    input.addEventListener('input', render);
    render();
  }
  window.GisoMoneyFa = {toWords: toWords};
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-money-words]').forEach(bind);
  });
})();
