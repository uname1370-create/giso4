/* یکسان‌سازی نمایش فارسی: تاریخ شمسی و رقم فارسی، بدون تغییر مقدار فنی فرم‌ها. */
(function(){'use strict';
 const digits=s=>String(s).replace(/[0-9]/g,d=>'۰۱۲۳۴۵۶۷۸۹'[d]);
 const dateFmt=new Intl.DateTimeFormat('fa-IR-u-ca-persian',{year:'numeric',month:'2-digit',day:'2-digit'});
 const dateTimeFmt=new Intl.DateTimeFormat('fa-IR-u-ca-persian',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
 const iso=/\b(20\d{2})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::\d{2})?)?\b/g;
 function localizeText(raw){
   raw=raw.replace(iso,(all,y,m,d,h,mi)=>{const dt=new Date(+y,+m-1,+d,+(h||0),+(mi||0));return h?dateTimeFmt.format(dt):dateFmt.format(dt)});
   return digits(raw);
 }
 function excluded(el){return !el||el.closest('code,pre,kbd,[dir="ltr"],input,textarea,select,[data-no-fa],.tracking-code,.giso-tracking-codes,.phone-ltr');}
 function run(root){const scope=root||document.body;const w=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode()){if(!excluded(n.parentElement)&&/[0-9]/.test(n.nodeValue))n.nodeValue=localizeText(n.nodeValue);}if(scope.matches&&scope.matches('time[datetime]')&&!excluded(scope)){const v=localizeText(scope.getAttribute('datetime'));if(scope.textContent!==v)scope.textContent=v;}if(scope.querySelectorAll)scope.querySelectorAll('time[datetime]').forEach(t=>{if(!excluded(t)&&t.getAttribute('datetime')){const v=localizeText(t.getAttribute('datetime'));if(t.textContent!==v)t.textContent=v;}});}
 window.gisoFaDisplay={digits,localizeText,run};
 function localizeNode(node){
   if(node.nodeType===Node.TEXT_NODE){if(!excluded(node.parentElement)&&/[0-9]/.test(node.nodeValue))node.nodeValue=localizeText(node.nodeValue);return;}
   if(node.nodeType===Node.ELEMENT_NODE)run(node);
 }
 function boot(){
   run();let timer,queue=[];
   new MutationObserver(records=>{records.forEach(r=>{if(r.type==='characterData')queue.push(r.target);else r.addedNodes.forEach(n=>queue.push(n));});clearTimeout(timer);timer=setTimeout(()=>{const batch=queue;queue=[];batch.forEach(localizeNode);},50);}).observe(document.body,{childList:true,subtree:true,characterData:true});
 }
 document.readyState==='loading'?document.addEventListener('DOMContentLoaded',boot):boot();
})();
