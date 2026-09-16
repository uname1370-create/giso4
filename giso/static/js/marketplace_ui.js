/* Phase 4 final: dependency-free marketplace UI helpers. */
(() => {
  'use strict';

  const persianDigits = '۰۱۲۳۴۵۶۷۸۹';
  const toEnglishDigits = (value) => String(value || '')
    .replace(/[۰-۹]/g, (char) => String(persianDigits.indexOf(char)))
    .replace(/[٠-٩]/g, (char) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(char)));
  const toPersianDigits = (value) => String(value || '').replace(/[0-9]/g, (char) => persianDigits[Number(char)]);
  const formatAmount = (value) => {
    const digits = toEnglishDigits(value).replace(/\D/g, '').slice(0, 15);
    return digits ? toPersianDigits(Number(digits).toString()) : '';
  };
  const toDate = (value) => {
    if (!value) return null;
    const normalized = String(value).trim().replace(' ', 'T');
    const parsed = new Date(normalized);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  };
  const relativeTime = (date) => {
    const seconds = Math.round((date.getTime() - Date.now()) / 1000);
    const ranges = [
      ['year', 31536000], ['month', 2592000], ['week', 604800],
      ['day', 86400], ['hour', 3600], ['minute', 60],
    ];
    const formatter = new Intl.RelativeTimeFormat('fa-IR', { numeric: 'auto' });
    for (const [unit, size] of ranges) {
      if (Math.abs(seconds) >= size) return formatter.format(Math.round(seconds / size), unit);
    }
    return formatter.format(seconds, 'second');
  };

  document.querySelectorAll('.giso-market-page img, .pu-marketplace-page img, .pnl-marketplace-page img').forEach((image) => {
    image.loading = 'lazy';
  });

  document.querySelectorAll('.js-market-image').forEach((image) => {
    const markMissing = () => image.closest('.giso-market-image-frame')?.classList.add('is-missing');
    image.addEventListener('error', markMissing, { once: true });
    if (image.complete && image.naturalWidth === 0) markMissing();
  });

  document.querySelectorAll('.js-market-time[datetime]').forEach((node) => {
    const date = toDate(node.getAttribute('datetime'));
    if (!date) return;
    node.title = new Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
    node.textContent = relativeTime(date);
  });

  document.querySelectorAll('input[data-market-amount], .giso-market-offer-form input[inputmode="numeric"], .giso-market-counter-form input[inputmode="numeric"]').forEach((input) => {
    const format = () => { input.value = formatAmount(input.value); };
    input.addEventListener('input', format);
    if (input.value) format();
  });

  document.querySelectorAll('form[data-market-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.marketConfirm || 'ادامه می‌دهید؟')) event.preventDefault();
    });
  });

  const messages = document.querySelector('.giso-market-messages');
  if (messages) messages.scrollTop = messages.scrollHeight;

  const lightbox = document.querySelector('[data-market-lightbox]');
  if (lightbox) {
    const image = lightbox.querySelector('img');
    const close = lightbox.querySelector('[data-market-lightbox-close]');
    const closeLightbox = () => {
      lightbox.hidden = true;
      document.body.classList.remove('giso-market-lightbox-open');
      if (image) image.src = '';
    };
    document.querySelectorAll('[data-market-lightbox-src]').forEach((trigger) => {
      trigger.addEventListener('click', () => {
        if (!image) return;
        image.src = trigger.dataset.marketLightboxSrc || '';
        lightbox.hidden = false;
        document.body.classList.add('giso-market-lightbox-open');
        close?.focus();
      });
    });
    close?.addEventListener('click', closeLightbox);
    lightbox.addEventListener('click', (event) => {
      if (event.target === lightbox) closeLightbox();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !lightbox.hidden) closeLightbox();
    });
  }
})();
