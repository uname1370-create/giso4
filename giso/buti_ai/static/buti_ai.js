// Buti AI — رفتار کوچک اختصاصی ماژول، بدون وابستگی به صفحات دیگر Giso.
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

  function setCheckState(kind, message, checks, warnings) {
    var box = document.getElementById('btiUploadChecks');
    var status = document.getElementById('btiUploadCheckStatus');
    var list = document.getElementById('btiUploadCheckList');
    if (!box || !status || !list) return;
    box.hidden = false;
    box.classList.remove('is-ok', 'is-bad', 'is-loading', 'is-warn');
    box.classList.add(kind || 'is-loading');
    status.textContent = message || 'در حال بررسی اولیه عکس...';
    list.innerHTML = '';
    var labels = {
      face_visible: 'صورت مشخص باشد',
      eyebrows_visible: 'ابروها واضح باشند',
      lighting: 'نور مناسب باشد',
      angle: 'صورت روبه‌رو باشد',
      sharpness: 'عکس تار نباشد'
    };
    Object.keys(labels).forEach(function (key) {
      var value = checks && checks[key];
      if (value === undefined || value === null || value === '') return;
      var ok = value === true || value === 'good' || value === 'front' || value === 'yes' || value === 'clear';
      var item = document.createElement('span');
      item.className = ok ? 'pass' : 'info';
      item.textContent = (ok ? '✅ ' : '• ') + labels[key];
      list.appendChild(item);
    });
    (warnings || []).forEach(function (warning) {
      var item = document.createElement('span');
      item.className = 'warn';
      item.textContent = '⚠️ ' + warning;
      list.appendChild(item);
    });
  }

  async function validateEyebrowPhoto(file) {
    var tokenInput = document.querySelector('input[name="csrf_token"]');
    var formData = new FormData();
    formData.append('photo', file);
    setCheckState('is-loading', 'در حال بررسی اولیه عکس...', {}, []);
    setAnalyzeEnabled(false);
    try {
      var response = await fetch('/analysis/mirror/eyebrow/validate-photo', {
        method: 'POST',
        headers: { 'X-GISO-CSRF': tokenInput ? tokenInput.value : '' },
        body: formData
      });
      var result = await response.json();
      if (result.valid) {
        var kind = result.warnings && result.warnings.length ? 'is-warn' : 'is-ok';
        setCheckState(kind, result.message || 'عکس برای طراحی مناسب است.', result.checks || {}, result.warnings || []);
        setAnalyzeEnabled(true);
      } else {
        setCheckState('is-bad', result.message || 'این عکس برای طراحی مناسب نیست.', result.checks || {}, []);
        setAnalyzeEnabled(false);
      }
    } catch (error) {
      setCheckState('is-warn', 'بررسی اولیه کامل نشد؛ اگر عکس واضح است می‌توانی ادامه بدهی.', {}, []);
      setAnalyzeEnabled(true);
    }
  }

  ready(function () {
    var input = document.getElementById('btiEyebrowPhoto');
    var text = document.getElementById('btiUploadText');
    var preview = document.getElementById('btiUploadPreview');
    var form = input ? input.closest('form') : null;
    setAnalyzeEnabled(false);
    if (input && text) {
      input.addEventListener('change', function () {
        var file = input.files && input.files[0];
        if (!file) {
          text.textContent = 'انتخاب عکس';
          if (preview) { preview.hidden = true; preview.removeAttribute('src'); }
          setAnalyzeEnabled(false);
          return;
        }
        if (['image/jpeg', 'image/png', 'image/webp'].indexOf(file.type) === -1) {
          alert('فقط عکس واقعی JPG، PNG یا WebP پذیرفته می‌شود.');
          input.value = '';
          setAnalyzeEnabled(false);
          return;
        }
        if (file.size > 8 * 1024 * 1024) {
          alert('حجم عکس باید کمتر از ۸ مگابایت باشد.');
          input.value = '';
          setAnalyzeEnabled(false);
          return;
        }
        text.textContent = 'عکس انتخاب شد: ' + file.name;
        if (preview) {
          var url = URL.createObjectURL(file);
          preview.src = url;
          preview.hidden = false;
          preview.onload = function () { URL.revokeObjectURL(url); };
        }
        validateEyebrowPhoto(file);
      });
    }
    if (form) {
      form.addEventListener('submit', function (event) {
        var btn = document.getElementById('btiAnalyzeBtn');
        if (btn && btn.disabled) {
          event.preventDefault();
          alert('لطفاً اول یک عکس واضح انتخاب کن تا بررسی اولیه انجام شود.');
        }
      });
    }

    var styleOptions = Array.prototype.slice.call(document.querySelectorAll('.bti-style-option, .bti-style-row, .bti-style-choice'));
    styleOptions.forEach(function (option) {
      var radio = option.querySelector('input[type="radio"]');
      if (!radio) return;
      radio.addEventListener('change', function () {
        styleOptions.forEach(function (item) { item.classList.remove('is-selected'); });
        option.classList.add('is-selected');
      });
    });

    if (window.location.hash !== '#result') {
      var result = document.getElementById('result');
      if (result) {
        setTimeout(function () { result.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 150);
      }
    }
  });
})();

// Phase 5 — draggable before/after comparator for final eyebrow design
(function () {
  function setCompare(slider, rawValue) {
    var value = Math.max(2, Math.min(98, Number(rawValue) || 50));
    slider.style.setProperty('--bti-compare-pos', value + '%');
    slider.style.setProperty('--bti-compare-pos-num', String(value / 100));
    var range = slider.querySelector('.bti-compare-range');
    if (range) range.value = String(Math.round(value));
  }

  function valueFromPointer(slider, event) {
    var rect = slider.getBoundingClientRect();
    var x = event.clientX - rect.left;
    return (x / Math.max(1, rect.width)) * 100;
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-bti-compare]').forEach(function (slider) {
      var range = slider.querySelector('.bti-compare-range');
      setCompare(slider, range ? range.value : 50);
      if (range) {
        range.addEventListener('input', function () { setCompare(slider, range.value); });
      }
      var activePointer = null;
      slider.addEventListener('pointerdown', function (event) {
        activePointer = event.pointerId;
        slider.setPointerCapture && slider.setPointerCapture(event.pointerId);
        event.preventDefault && event.preventDefault();
        setCompare(slider, valueFromPointer(slider, event));
      });
      slider.addEventListener('pointermove', function (event) {
        if (activePointer === event.pointerId || event.buttons) {
          event.preventDefault && event.preventDefault();
          setCompare(slider, valueFromPointer(slider, event));
        }
      });
      slider.addEventListener('pointerup', function () { activePointer = null; });
      slider.addEventListener('pointercancel', function () { activePointer = null; });
    });
  });
})();
