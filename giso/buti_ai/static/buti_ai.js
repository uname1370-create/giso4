// Buti AI — preview local, validate same-origin, then explicit user confirmation.
(function () {
  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  function setAnalyzeEnabled(enabled) {
    var btn = document.getElementById('btiAnalyzeBtn');
    if (!btn) return;
    btn.disabled = !enabled;
    btn.classList.toggle('is-disabled', !enabled);
  }

  function showFinalLoading() { return; }

  function openImageLightbox(src) {
    if (!src) return;
    var old = document.querySelector('.bti-image-lightbox');
    if (old) old.remove();
    var box = document.createElement('div');
    box.className = 'bti-image-lightbox';
    var closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', 'بستن');
    closeButton.textContent = '×';
    var image = document.createElement('img');
    image.src = src;
    image.alt = 'بزرگنمایی طراحی';
    box.appendChild(closeButton);
    box.appendChild(image);
    function close() { box.remove(); document.removeEventListener('keydown', onKey); }
    function onKey(e) { if (e.key === 'Escape') close(); }
    box.addEventListener('click', function (event) { if (event.target === box || event.target === closeButton) close(); });
    document.addEventListener('keydown', onKey);
    document.body.appendChild(box);
    requestAnimationFrame(function () { box.classList.add('is-visible'); });
  }

  function appendText(parent, tag, text, className) {
    var element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = String(text || '');
    parent.appendChild(element);
    return element;
  }

  function checkLabel(key, value) {
    var labels = {
      face_visible: 'صورت مشخص است', eyebrows_visible: 'ابروها مشخص‌اند',
      lips_visible: 'لب‌ها مشخص‌اند', upper_lip_visible: 'لب بالا مشخص است',
      lower_lip_visible: 'لب پایین مشخص است', lighting: 'نور', angle: 'زاویه', sharpness: 'وضوح'
    };
    if (value === true) return (labels[key] || key) + ': مناسب';
    if (value === false) return (labels[key] || key) + ': نیاز به عکس بهتر';
    if (value === null || value === undefined || value === '') return '';
    return (labels[key] || key) + ': ' + String(value);
  }

  function renderChecks(data, loading) {
    var box = document.getElementById('btiUploadChecks');
    var status = document.getElementById('btiUploadCheckStatus');
    var list = document.getElementById('btiUploadCheckList');
    if (!box || !status || !list) return;
    box.hidden = false;
    list.replaceChildren();
    status.textContent = loading ? 'در حال بررسی عکس و تحلیل هوشمند...' : (data.message || 'بررسی عکس انجام شد.');
    if (loading) return;
    var checks = data.checks || {};
    Object.keys(checks).forEach(function (key) {
      var text = checkLabel(key, checks[key]);
      if (text) appendText(list, 'span', text);
    });
    (data.warnings || []).forEach(function (warning) { appendText(list, 'span', warning, 'is-warning'); });
  }

  function renderPreliminaryRecommendation(data) {
    var target = document.getElementById('btiUploadRecommendation');
    if (!target) return;
    target.replaceChildren();
    target.hidden = false;
    var recommendation = data.recommendation || {};
    var isAi = recommendation.status === 'ai_analyzed';
    var heading = appendText(target, 'b', isAi ? 'پیشنهاد گیسو آماده است' : 'انتخاب دستی همچنان فعال است');
    heading.className = isAi ? 'is-ai' : 'is-unavailable';
    appendText(target, 'p', (isAi ? 'پیشنهاد گیسو: ' : 'مدل قابل ادامه: ') + (recommendation.label || 'مدل انتخابی'));
    appendText(target, 'small', recommendation.reason || 'پس از ثبت عکس، انتخاب نهایی را تأیید می‌کنی.');
    var alternatives = recommendation.alternatives || [];
    if (alternatives.length) appendText(target, 'small', 'گزینه‌های جایگزین: ' + alternatives.join('، '));
  }

  async function validateEyebrowPhoto(file, form) {
    var validateUrl = form && form.getAttribute('data-bti-validate-url');
    if (!validateUrl) return { valid: true, status: 'not_configured', recommendation: {} };
    var formData = new FormData();
    formData.append('photo', file, file.name || 'photo.jpg');
    var csrf = form.querySelector('input[name="csrf_token"]');
    if (csrf && csrf.value) formData.append('csrf_token', csrf.value);
    var response = await fetch(validateUrl, {
      method: 'POST', credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' }, body: formData
    });
    var data = await response.json().catch(function () { return { valid: false, message: 'پاسخ بررسی عکس قابل خواندن نیست.' }; });
    data.httpOk = response.ok;
    return data;
  }

  ready(function () {
    var input = document.getElementById('btiEyebrowPhoto');
    var text = document.getElementById('btiUploadText');
    var fileName = document.getElementById('btiUploadFileName');
    var preview = document.getElementById('btiUploadPreview');
    var previewFrame = document.getElementById('btiUploadPreviewFrame');
    var placeholder = document.getElementById('btiUploadPlaceholder');
    var changeBtn = document.getElementById('btiChangePhotoBtn');
    var zone = document.getElementById('btiUploadZone');
    var form = input ? input.closest('form') : null;
    if (input) setAnalyzeEnabled(false);

    if (changeBtn && input) changeBtn.addEventListener('click', function () { input.click(); });

    if (input && text && form) {
      input.addEventListener('change', async function () {
        var file = input.files && input.files[0];
        var recommendation = document.getElementById('btiUploadRecommendation');
        if (!file) {
          text.textContent = 'انتخاب عکس';
          if (fileName) fileName.textContent = 'عکسی انتخاب نشده';
          if (preview) preview.removeAttribute('src');
          if (previewFrame) previewFrame.hidden = true;
          if (placeholder) placeholder.hidden = false;
          if (changeBtn) changeBtn.hidden = true;
          if (zone) zone.classList.remove('has-preview', 'is-analyzing');
          if (recommendation) { recommendation.hidden = true; recommendation.replaceChildren(); }
          setAnalyzeEnabled(false);
          return;
        }
        var lowerName = (file.name || '').toLowerCase();
        var typeOk = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'].indexOf(file.type) !== -1;
        var extOk = /\.(jpe?g|png|webp)$/.test(lowerName);
        if (!typeOk && !extOk) {
          alert('فقط عکس واقعی JPG، PNG یا WebP پذیرفته می‌شود.');
          input.value = ''; setAnalyzeEnabled(false); return;
        }
        if (file.size > 8 * 1024 * 1024) {
          alert('حجم عکس باید کمتر از ۸ مگابایت باشد.');
          input.value = ''; setAnalyzeEnabled(false); return;
        }
        text.textContent = 'عکس انتخاب شد';
        if (fileName) fileName.textContent = file.name;
        if (preview) { var reader = new FileReader(); reader.onload = function (ev) { preview.src = ev.target.result; }; reader.readAsDataURL(file); preview.style.display = 'block'; preview.removeAttribute('hidden'); }
        if (previewFrame) { previewFrame.hidden = false; previewFrame.style.display = 'block'; previewFrame.removeAttribute('hidden'); }
        if (placeholder) { placeholder.hidden = true; placeholder.style.display = 'none'; }
        if (changeBtn) changeBtn.hidden = false;
        if (zone) { zone.classList.add('has-preview', 'is-analyzing'); }
        setAnalyzeEnabled(false);
        renderChecks({}, true);
        try {
          var data = await validateEyebrowPhoto(file, form);
          renderChecks(data, false);
          renderPreliminaryRecommendation(data);
          // A temporary endpoint failure does not erase the user's manual choice.
          setAnalyzeEnabled(data.valid !== false);
        } catch (error) {
          var fallback = {
            valid: true,
            message: 'تحلیل هوشمند در دسترس نبود؛ می‌توانی مدل انتخابی خودت را ادامه بدهی.',
            warnings: ['ارتباط با سرویس تحلیل برقرار نشد.'],
            recommendation: { status: 'ai_unavailable', label: 'مدل انتخابی من', reason: 'پس از ثبت عکس، انتخاب دستی را تأیید کن.' }
          };
          renderChecks(fallback, false);
          renderPreliminaryRecommendation(fallback);
          setAnalyzeEnabled(true);
        } finally {
          if (zone) zone.classList.remove('is-analyzing');
        }
      });
    }

    if (form) {
      form.addEventListener('submit', function (event) {
        var btn = document.getElementById('btiAnalyzeBtn');
        if (btn && btn.disabled) { event.preventDefault(); alert('لطفاً اول یک عکس واضح انتخاب کن.'); return; }
        showFinalLoading();
      });
    }

    document.querySelectorAll('[data-bti-final-style]').forEach(function (choice) {
      choice.addEventListener('change', function () {
        var target = document.getElementById('btiFinalStyle');
        if (target) target.value = choice.getAttribute('data-bti-final-style') || '';
        document.querySelectorAll('.bti-recommendation-option').forEach(function (item) { item.classList.remove('is-selected'); });
        var option = choice.closest('.bti-recommendation-option');
        if (option) option.classList.add('is-selected');
      });
    });

    document.querySelectorAll('[data-bti-lightbox-image]').forEach(function (btn) { btn.addEventListener('click', function () { openImageLightbox(btn.getAttribute('data-bti-lightbox-image')); }); });
    var styleOptions = Array.prototype.slice.call(document.querySelectorAll('.bti-style-option, .bti-style-row, .bti-style-choice'));
    styleOptions.forEach(function (option) {
      var radio = option.querySelector('input[type="radio"]');
      if (!radio) return;
      radio.addEventListener('change', function () { styleOptions.forEach(function (item) { item.classList.remove('is-selected'); }); option.classList.add('is-selected'); });
    });
  });
})();

// Draggable before/after comparator for final designs.
(function () {
  function setCompare(slider, rawValue) {
    var value = Math.max(2, Math.min(98, Number(rawValue) || 50));
    slider.style.setProperty('--bti-compare-pos', value + '%');
    slider.style.setProperty('--bti-compare-pos-num', String(value / 100));
    var range = slider.querySelector('.bti-compare-range');
    if (range) range.value = String(Math.round(value));
  }
  function valueFromPointer(slider, event) { var rect = slider.getBoundingClientRect(); return ((event.clientX - rect.left) / Math.max(1, rect.width)) * 100; }
  ready(function () {
    document.querySelectorAll('[data-bti-compare]').forEach(function (slider) {
      var range = slider.querySelector('.bti-compare-range');
      setCompare(slider, range ? range.value : 50);
      if (range) range.addEventListener('input', function () { setCompare(slider, range.value); });
      var activePointer = null;
      slider.addEventListener('pointerdown', function (event) { activePointer = event.pointerId; if (slider.setPointerCapture) slider.setPointerCapture(event.pointerId); event.preventDefault(); setCompare(slider, valueFromPointer(slider, event)); });
      slider.addEventListener('pointermove', function (event) { if (activePointer === event.pointerId || event.buttons) { event.preventDefault(); setCompare(slider, valueFromPointer(slider, event)); } });
      slider.addEventListener('pointerup', function () { activePointer = null; });
      slider.addEventListener('pointercancel', function () { activePointer = null; });
    });
  });
})();
