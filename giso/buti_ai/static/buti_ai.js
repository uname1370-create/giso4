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

    var styleOptions = Array.prototype.slice.call(document.querySelectorAll('.bti-style-option'));
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
