(() => {
  'use strict';

  document.querySelectorAll('.bc-card-media img,.bc-detail-image img,.bc-carousel-slide img').forEach((image) => {
    const fail = () => image.parentElement?.classList.add('is-missing');
    image.addEventListener('error', fail, { once: true });
    if (image.complete && image.naturalWidth === 0) fail();
  });

  // فرم دسته/نوع/خدمت؛ فقط در صفحات ثبت و ویرایش اجرا می‌شود.
  const category = document.getElementById('bcCategory');
  const type = document.getElementById('bcCenterType');
  const services = document.getElementById('bcServices');
  if (category && type && services) {
    const applyCategory = () => {
      const selectedCategory = category.value;
      let firstType = '';
      let selectedTypeIsValid = false;
      type.querySelectorAll('option[data-category]').forEach((option) => {
        const visible = option.dataset.category === selectedCategory;
        option.hidden = !visible;
        option.disabled = !visible;
        if (visible && !firstType) firstType = option.value;
        if (visible && option.selected) selectedTypeIsValid = true;
      });
      if (!selectedTypeIsValid) type.value = firstType;
      services.querySelectorAll('label[data-category]').forEach((label) => {
        const visible = label.dataset.category === selectedCategory;
        const input = label.querySelector('input');
        label.hidden = !visible;
        if (input) {
          input.disabled = !visible;
          if (!visible) input.checked = false;
        }
      });
    };
    category.addEventListener('change', applyCategory);
    applyCategory();
  }

  // شمارنده نمایشی روزهای باقی‌مانده؛ اعتبار واقعی همچنان در Backend کنترل می‌شود.
  document.querySelectorAll('[data-center-expires]').forEach((box) => {
    const raw = String(box.dataset.centerExpires || '').trim();
    const date = new Date(raw.replace(' ', 'T'));
    const label = box.querySelector('span');
    if (!label || Number.isNaN(date.getTime())) {
      if (label) label.textContent = 'تاریخ پایان اعتبار ثبت نشده است.';
      return;
    }
    const days = Math.max(0, Math.ceil((date.getTime() - Date.now()) / 86400000));
    if (days <= 0) {
      box.classList.add('is-expired');
      label.textContent = 'اعتبار نمایش آگهی پایان یافته است.';
    } else {
      if (days <= 7) box.classList.add('is-urgent');
      label.textContent = `${days.toLocaleString('fa-IR')} روز تا پایان اعتبار آگهی`;
    }
  });

  // اسلایدر سبک، لمسی و بدون کتابخانه خارجی — RTL-safe.
  // به‌جای محاسبه‌ی دستی scrollLeft (که در RTL و مرورگرهای مختلف رفتار متفاوت دارد)،
  // مستقیماً خود اسلاید با scrollIntoView در جایگاه اسنپ قرار می‌گیرد و اسلاید فعال
  // با کمترین فاصله تا لبه‌ی track تشخیص داده می‌شود؛ این روش هم برای LTR و هم RTL
  // (فایرفاکس/کروم/سافاری و لمس) یکسان کار می‌کند.
  document.querySelectorAll('[data-center-carousel]').forEach((carousel) => {
    const track = carousel.querySelector('.bc-carousel-track');
    const slides = [...carousel.querySelectorAll('.bc-carousel-slide')];
    const dots = [...carousel.querySelectorAll('.bc-carousel-dots i')];
    if (!track || !slides.length) return;

    const setDots = (activeIndex) => {
      dots.forEach((dot, i) => dot.classList.toggle('active', i === activeIndex));
    };
    // اسلایدی که بیشترین هم‌پوشانی را با ناحیه‌ی قابل‌مشاهده‌ی track دارد.
    const currentIndex = () => {
      const view = track.getBoundingClientRect();
      let best = 0;
      let bestOverlap = -Infinity;
      slides.forEach((slide, i) => {
        const r = slide.getBoundingClientRect();
        const overlap = Math.min(r.right, view.right) - Math.max(r.left, view.left);
        if (overlap > bestOverlap) { bestOverlap = overlap; best = i; }
      });
      return best;
    };
    const go = (next) => {
      const target = (next + slides.length) % slides.length;
      // inline:'start' در RTL خودکار به سمت درست اسنپ می‌شود؛ block برای جلوگیری از
      // پرش عمودی صفحه روی 'nearest' است.
      slides[target].scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
      setDots(target);
    };
    carousel.querySelector('[data-carousel-prev]')?.addEventListener('click', () => go(currentIndex() - 1));
    carousel.querySelector('[data-carousel-next]')?.addEventListener('click', () => go(currentIndex() + 1));

    let scrollTimer = null;
    track.addEventListener('scroll', () => {
      window.clearTimeout(scrollTimer);
      scrollTimer = window.setTimeout(() => setDots(currentIndex()), 90);
    }, { passive: true });
    // نقطه‌ها هم مستقیماً قابل کلیک باشند (دسترسی‌پذیری).
    dots.forEach((dot, i) => dot.addEventListener('click', () => go(i)));
    setDots(0);
  });

  // دکمهٔ ذخیرهٔ فرم ویرایش مرکز: فقط وقتی چیزی تغییر کرده باشد فعال می‌شود (مأموریت 36).
  const editForm = document.querySelector('.bc-owner-edit-form');
  if (editForm) {
    const saveBtn = editForm.querySelector('#bcSaveBtn');
    const saveHint = document.getElementById('bcSaveHint');
    const IDLE_HINT = 'برای فعال‌شدن دکمه، یکی از اطلاعات را تغییر دهید؛ هر ویرایش روزی یک‌بار و نیازمند بررسی دوبارهٔ مدیریت است.';
    const DIRTY_HINT = 'تغییرها ذخیره نشده‌اند؛ برای ثبت نهایی دکمهٔ «ذخیره تغییرات مرکز» را بزنید.';
    if (saveBtn) {
      const snap = () => [...new FormData(editForm).entries()].map((e) => e.join('=')).sort().join('|');
      const baseline = snap();
      const check = () => {
        const dirty = snap() !== baseline;
        saveBtn.disabled = !dirty;
        if (saveHint) saveHint.textContent = dirty ? DIRTY_HINT : IDLE_HINT;
      };
      editForm.addEventListener('input', check);
      editForm.addEventListener('change', check);
    }
  }

  // Lightbox داخلی صفحه.
  const lightbox = document.getElementById('bcCenterLightbox');
  const lightboxImage = lightbox?.querySelector('img');
  const closeLightbox = () => {
    if (!lightbox) return;
    lightbox.hidden = true;
    document.body.style.overflow = '';
    if (lightboxImage) lightboxImage.src = '';
  };
  document.querySelectorAll('[data-lightbox-src]').forEach((button) => {
    button.addEventListener('click', () => {
      if (!lightbox || !lightboxImage) return;
      lightboxImage.src = button.dataset.lightboxSrc || '';
      lightbox.hidden = false;
      document.body.style.overflow = 'hidden';
      lightbox.querySelector('.bc-lightbox-close')?.focus();
    });
  });
  lightbox?.querySelector('.bc-lightbox-close')?.addEventListener('click', closeLightbox);
  lightbox?.addEventListener('click', (event) => { if (event.target === lightbox) closeLightbox(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && lightbox && !lightbox.hidden) closeLightbox(); });
})();
