// Buti AI — رفتار کوچک اختصاصی ماژول، بدون وابستگی به صفحات دیگر Giso.
(function () {
  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  ready(function () {
    var input = document.getElementById('btiEyebrowPhoto');
    var text = document.getElementById('btiUploadText');
    if (input && text) {
      input.addEventListener('change', function () {
        var file = input.files && input.files[0];
        text.textContent = file ? ('عکس انتخاب شد: ' + file.name) : 'انتخاب عکس واضح صورت';
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
      slider.addEventListener('pointerdown', function (event) {
        slider.setPointerCapture && slider.setPointerCapture(event.pointerId);
        setCompare(slider, valueFromPointer(slider, event));
      });
      slider.addEventListener('pointermove', function (event) {
        if (event.buttons) setCompare(slider, valueFromPointer(slider, event));
      });
    });
  });
})();
