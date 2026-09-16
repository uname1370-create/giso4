function showCelebration(opts){
  opts = opts || {};
  const old = document.getElementById('celebrationOverlay');
  if(old) old.remove();
  const overlay = document.createElement('div');
  overlay.id = 'celebrationOverlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(15,23,42,.55);backdrop-filter:blur(4px);opacity:0;transition:.25s;pointer-events:none;padding:20px;';
  const card = document.createElement('div');
  card.style.cssText = 'width:min(92vw,420px);border-radius:28px;background:linear-gradient(135deg,#ffffff,#ecfeff);box-shadow:0 30px 90px rgba(0,0,0,.35);text-align:center;padding:34px 24px;transform:scale(.85);transition:.28s;font-family:inherit;position:relative;overflow:hidden;';
  const xp = document.createElement('div');
  xp.textContent = '+' + (opts.xp || 10) + ' XP';
  xp.style.cssText = 'font-size:46px;font-weight:950;color:#059669;text-shadow:0 0 28px rgba(16,185,129,.28);margin-bottom:12px;';
  const badge = document.createElement('div');
  badge.textContent = opts.badge ? '🏅 ' + opts.badge : '✨ قدم عالی';
  badge.style.cssText = 'display:inline-flex;background:#fef3c7;color:#92400e;border-radius:999px;padding:8px 16px;font-weight:900;margin-bottom:14px;';
  const msg = document.createElement('p');
  msg.textContent = opts.message || 'آفرین! یک قدم دیگر جلو رفتی.';
  msg.style.cssText = 'color:#334155;line-height:1.9;margin:0;font-weight:800;';
  for(let i=0;i<18;i++){
    const s=document.createElement('span');
    s.textContent=['✨','🎉','⭐','💫'][i%4];
    s.style.cssText='position:absolute;left:'+(Math.random()*100)+'%;top:'+(Math.random()*100)+'%;font-size:'+(14+Math.random()*16)+'px;animation:celebrationFloat 2.4s ease-out forwards;opacity:.9;';
    card.appendChild(s);
  }
  card.appendChild(xp); card.appendChild(badge); card.appendChild(msg); overlay.appendChild(card); document.body.appendChild(overlay);
  if(!document.getElementById('celebrationStyle')){
    const style=document.createElement('style'); style.id='celebrationStyle';
    style.textContent='@keyframes celebrationFloat{0%{transform:translateY(30px) scale(.7);opacity:0}35%{opacity:1}100%{transform:translateY(-90px) scale(1.2);opacity:0}}';
    document.head.appendChild(style);
  }
  requestAnimationFrame(()=>{overlay.style.opacity='1'; card.style.transform='scale(1)';});
  setTimeout(()=>{overlay.style.opacity='0'; card.style.transform='scale(.92)'; setTimeout(()=>overlay.remove(),280);}, opts.duration || 2600);
}
