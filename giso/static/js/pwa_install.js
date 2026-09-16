(function () {
  const btn = document.getElementById('gisoPwaInstall');
  const hint = document.getElementById('gisoPwaHint');
  if (!btn) return;

  let deferred = null;
  const ua = navigator.userAgent || '';
  const isIOS = /iphone|ipad|ipod/i.test(ua);
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true;

  function showHint(text) {
    if (!hint) return;
    hint.hidden = false;
    hint.textContent = text;
  }

  if (isStandalone) {
    btn.disabled = true;
    btn.textContent = 'نصب شده روی گوشی';
    return;
  }

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferred = e;
  });

  btn.addEventListener('click', async function () {
    if (deferred && deferred.prompt) {
      deferred.prompt();
      try { await deferred.userChoice; } catch (e) {}
      deferred = null;
      return;
    }
    if (isIOS) {
      showHint('در سافاری دکمهٔ Share را بزن و گزینهٔ Add to Home Screen را انتخاب کن.');
      return;
    }
    showHint('از منوی مرورگر گزینهٔ «نصب برنامه» یا Add to Home screen را بزن.');
  });
})();
