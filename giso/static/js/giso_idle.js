/* ⏳ خروج خودکار از حساب بعد از چند دقیقه عدم فعالیت (امنیت پنل کاربری گیسو)
   پیش‌فرض: ۱۰ دقیقه؛ ۶۰ ثانیه آخر هشدار با دکمه «هنوز اینجام» نمایش داده می‌شود.
   قابل تنظیم با data-idle-minutes روی <body>. */
(function(){
  var body=document.body;
  if(!body) return;
  var LIMIT_MIN=parseInt(body.getAttribute('data-idle-minutes')||'10',10);
  if(!(LIMIT_MIN>0)) return;
  var WARN_SEC=60;
  var LOGOUT_URL='/logout?reason=idle';
  var last=Date.now();
  var warned=false;
  var toast=null;
  var ticker=0;
  var moveLast=0;

  function resetTimer(){
    if(!warned) last=Date.now();
  }
  ['click','keydown','touchstart'].forEach(function(ev){
    document.addEventListener(ev, resetTimer, {passive:true});
  });
  function onLightActivity(){
    var n=Date.now();
    if(n-moveLast>15000){ moveLast=n; resetTimer(); }
  }
  document.addEventListener('mousemove', onLightActivity, {passive:true});
  document.addEventListener('scroll', onLightActivity, {passive:true});

  function remaining(){
    return Math.max(0, (LIMIT_MIN*60) - Math.floor((Date.now()-last)/1000));
  }
  function removeToast(){
    if(ticker){ clearInterval(ticker); ticker=0; }
    if(toast && toast.parentNode){ toast.parentNode.removeChild(toast); }
    toast=null;
  }
  function goLogout(){
    removeToast();
    window.location.href=LOGOUT_URL;
  }
  function showWarn(){
    if(warned) return;
    warned=true;
    toast=document.createElement('div');
    toast.setAttribute('role','alert');
    toast.style.cssText='position:fixed;bottom:18px;left:18px;z-index:2100;max-width:330px;'
      +'background:linear-gradient(135deg,#fff9f2,#fdf1e3);border:1.5px solid #e8c98f;border-radius:16px;'
      +'box-shadow:0 12px 34px rgba(90,62,27,.22);padding:14px 16px;font-family:Vazirmatn,sans-serif;'
      +'direction:rtl;color:#5a3e1b;font-size:13px;line-height:2';
    toast.innerHTML='<b style="color:#8b5a2b">⏳ پایان نشست نزدیک است</b><br>'
      +'به دلیل چند دقیقه عدم فعالیت، <span class="giso-idle-count" style="font-weight:700;color:#b8941f">'+remaining()+'</span> ثانیه دیگر از حسابت خارج می‌شوی.'
      +'<br><button type="button" class="giso-idle-stay" style="margin-top:8px;background:linear-gradient(135deg,#D4AF37,#b89128);color:#fff;border:none;border-radius:10px;padding:7px 16px;font-family:inherit;font-size:13px;font-weight:700;cursor:pointer">هنوز اینجام 🌸</button>';
    document.body.appendChild(toast);
    toast.querySelector('.giso-idle-stay').addEventListener('click', function(){
      warned=false;
      last=Date.now();
      removeToast();
    });
    ticker=setInterval(function(){
      var r=remaining();
      var el=toast && toast.querySelector('.giso-idle-count');
      if(el){ el.textContent=r; }
      if(r<=0){ goLogout(); }
    }, 1000);
  }
  setInterval(function(){
    var r=remaining();
    if(r<=WARN_SEC && !warned){ showWarn(); }
    if(r<=0){ goLogout(); }
  }, 4000);
})();
