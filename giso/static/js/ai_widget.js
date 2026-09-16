(function(){
  const root=document.getElementById('gisoAiWidget');
  if(!root) return;
  const fab=document.getElementById('gisoAiWidgetFab');
  const panel=document.getElementById('gisoAiWidgetPanel');
  const closeBtn=document.getElementById('gisoAiWidgetClose');
  const title=document.getElementById('gisoAiWidgetTitle');
  const roleEl=document.getElementById('gisoAiWidgetRole');
  const contextEl=document.getElementById('gisoAiWidgetContext');
  const summary=document.getElementById('gisoAiWidgetSummary');
  const messages=document.getElementById('gisoAiWidgetMessages');
  const typing=document.getElementById('gisoAiWidgetTyping');
  const actions=document.getElementById('gisoAiWidgetActions');
  const input=document.getElementById('gisoAiWidgetInput');
  const send=document.getElementById('gisoAiWidgetSend');
  const badge=document.getElementById('gisoAiWidgetBadge');
  const bubble=document.getElementById('gisoAiWidgetBubble');
  const bubbleText=document.getElementById('gisoAiWidgetBubbleText');
  const bubbleClose=document.getElementById('gisoAiWidgetBubbleClose');
  const hint=document.getElementById('gisoAiWidgetHint');
  const storageKey='giso_ai_widget_open';
  let initData=null;
  let csrf='';
  let loading=false;
  let initialized=false;

  /* 🌸 نوتفیکیشن حبابی: متن شخصی وضعیت (سفارش/درخواست) یا خوش‌آمد اولین بازدید */
  const bubbleKey='giso_ai_widget_bubble_off';
  let welcomeNotifText='';
  let attnShowTimer=null, attnHideTimer=null, attnTypeTimer=null;
  let attnSeenFn=null;
  function _attnClear(){
    [attnShowTimer,attnHideTimer,attnTypeTimer].forEach(t=>t&&clearTimeout(t));
    attnShowTimer=attnHideTimer=attnTypeTimer=null;
  }
  function _strHash(s){ let h=5381; for(let i=0;i<s.length;i++){ h=((h<<5)+h+s.charCodeAt(i))|0; } return (h>>>0).toString(36); }
  const WELCOME_NOTIF='سلام ✨\nمن مشاور هوشمند گیسوم 🌸\nهر سؤالی داری، همین‌جا بپرس 💬';
  function typeBubbleText(msg){
    if(!bubbleText) return;
    bubbleText.textContent='';
    bubbleText.classList.add('is-typing');
    let i=0;
    const step=()=>{
      if(i>=msg.length){ bubbleText.classList.remove('is-typing'); return; }
      const ch=msg[i++];
      if(ch==='\n'){ bubbleText.appendChild(document.createElement('br')); }
      else { bubbleText.appendChild(document.createTextNode(ch)); }
      attnTypeTimer=setTimeout(step,32);
    };
    step();
  }
  function startAttention(){
    if(!bubble) return;
    const notice=((initData&&initData.notice_text)||'').trim();
    let text=''; let markSeen=null;
    if(notice){
      /* اطلاعیه شخصی (وضعیت سفارش/درخواست‌ها یا گزارش مدیریتی) — هر بار نسخه جدیدش، یک‌بار نمایش داده می‌شود */
      const key='n'+_strHash(notice);
      try{ if(sessionStorage.getItem('giso_ai_notice_hash')===key) return; }catch(e){}
      markSeen=()=>{ try{sessionStorage.setItem('giso_ai_notice_hash',key);}catch(e){} };
      text=notice;
    } else {
      /* خوش‌آمد فقط برای اولین بازدید */
      if(localStorage.getItem(bubbleKey)==='1') return;
      markSeen=()=>{ try{localStorage.setItem(bubbleKey,'1');}catch(e){} };
      text=welcomeNotifText||WELCOME_NOTIF;
    }
    _attnClear();
    attnSeenFn=markSeen;
    attnShowTimer=setTimeout(()=>{
      if(!bubble || !panel.hidden){ return; }
      bubble.classList.remove('is-hidden','is-fading','is-thinking');
      typeBubbleText(text);
      attnHideTimer=setTimeout(()=>{
        if(!bubble) return;
        bubble.classList.add('is-fading');
        if(attnSeenFn){ attnSeenFn(); attnSeenFn=null; }
        attnTypeTimer=setTimeout(()=>{ bubble.classList.add('is-hidden'); }, 500);
      }, notice ? 9000 : 7000);
    }, 1300);
  }
  function stopAttention(permanent){
    if(!bubble) return;
    _attnClear();
    bubble.classList.add('is-hidden');
    bubble.classList.remove('is-fading','is-thinking');
    if(permanent && attnSeenFn){ attnSeenFn(); attnSeenFn=null; }
  }
  function setOpen(open){
    try{ localStorage.setItem(storageKey, open ? '1' : '0'); }catch(e){}
    panel.hidden=!open;
    root.classList.toggle('panel-open', open);
    if(open){ stopAttention(true); badge.classList.add('is-hidden'); }
    else if(initData){ updateBadge(initData); }
  }
  function roleLabel(role){ return ({guest:'🌸 مهمان',user:'عضو گیسو',admin:'ادمین',super:'👑 سوپرادمین'})[role]||'مشاور'; }
  function escapeHtml(s){ return String(s||'').replace(/[&<>\"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
  function autosize(){
    input.style.height='auto';
    input.style.height=Math.min(input.scrollHeight, 120)+'px';
  }
  function setBusy(flag){
    loading=!!flag;
    typing.hidden=!flag;
    send.disabled=!!flag;
    input.disabled=!!flag;
    root.classList.toggle('is-loading', !!flag);
    if(flag) messages.scrollTop=messages.scrollHeight;
  }
  function addMsg(role,text){
    const div=document.createElement('div');
    div.className='giso-aiw-msg '+(role==='user'?'user':'ai');
    div.innerHTML=escapeHtml(text).replace(/\n/g,'<br>');
    messages.appendChild(div);
    messages.scrollTop=messages.scrollHeight;
  }
  function renderHistory(history){
    messages.querySelectorAll('.giso-aiw-msg').forEach(n=>n.remove());
    (history||[]).forEach(m=>addMsg(m.role==='user'?'user':'ai', m.content||''));
    messages.scrollTop=messages.scrollHeight;
  }
  function renderActions(items){
    actions.innerHTML='';
    (items||[]).slice(0,4).forEach(item=>{
      if(!item || !item.url) return;
      const a=document.createElement('a');
      a.href=item.url;
      a.innerHTML='<span>'+escapeHtml(item.label||item.url)+'</span><b>↗</b>';
      actions.appendChild(a);
    });
  }
  function renderContext(data, show){
    input.placeholder=(data&&data.input_placeholder) || 'پیامت را بنویس...';
    if(!show){
      contextEl.textContent='';
      contextEl.hidden=true;
      autosize();
      return;
    }
    const parts=[];
    if(data.page_title) parts.push(data.page_title);
    if(data.state_label) parts.push(data.state_label);
    if(data.focus_label) parts.push(data.focus_label);
    contextEl.textContent=parts.join(' • ');
    contextEl.hidden=!parts.length;
    autosize();
  }
  function updateBadge(data){
    const hasPrompt=!!(data&&data.notice_text) && !(data&&data.history&&data.history.length);
    if(!panel.hidden || !hasPrompt){
      badge.classList.add('is-hidden');
      return;
    }
    badge.classList.remove('is-hidden');
  }
  function applyData(data){
    if(!data) return;
    title.textContent=data.display_name||'مشاور هوشمند گیسو';
    roleEl.textContent=roleLabel(data.role);
    const isStaff=(data.role==='admin'||data.role==='super');
    const hasHistory=((data.history||[]).length>0);
    // خلاصه/آمار فقط برای داشبورد جیبی ادمین‌ها؛ برای کاربر و مهمان چیزی رسم نمی‌شود
    summary.textContent=isStaff ? (data.summary||'') : '';
    summary.hidden=!(isStaff && data.summary);
    renderContext(data, isStaff);
    // راهنمای نقش: مهمان ← ورود؛ ادمین تأییدنشده ← فعال‌سازی حالت مدیریتی
    if(data.role_hint==='admin_unverified'){
      hint.textContent='🔐 برای گزارش‌های مدیریتی، حالت مدیر را فعال کن';
      hint.href='/admin/verify';
      hint.hidden=false;
    } else if(data.role==='guest'){
      hint.textContent='ورود / ثبت‌نام برای تجربه شخصی‌تر';
      hint.href='/login';
      hint.hidden=false;
    } else {
      hint.hidden=true;
      hint.textContent='';
    }
    // هیچ چیپ پیشنهادی یا امتیازدهی در ویجت نمایش داده نمی‌شود.
    renderActions([]);
    updateBadge(data);
  }
  async function loadInit(){
    if(initialized) return;
    const resp=await fetch('/api/ai-widget/init?page='+encodeURIComponent(location.pathname));
    const data=await resp.json();
    if(!data.ok || !data.enabled){ root.classList.add('is-hidden'); return; }
    initData=data; csrf=data.csrf_token||''; initialized=true;
    welcomeNotifText=(data.welcome||'').trim();
    root.classList.remove('is-hidden');
    root.className='giso-aiw '+(data.position||'right-bottom');
    root.style.setProperty('--aiw-color', data.primary_color||'#e89090');
    applyData(data);
    renderHistory(data.history||[]);
    // نوتفیکیشن: اگر اطلاعیه شخصی/مدیریتی هست همان، وگرنه خوش‌آمد اولین بازدید
    startAttention();
  }
  // مورد ۱۱ help2: خط کوچک نرخ/مصرف/مانده — فقط وقتی کسر اعتبار فعال باشد نمایش داده می‌شود
  function faNum(n){ return String(n).replace(/\d/g, d=>'۰۱۲۳۴۵۶۷۸۹'[d]); }
  function appendCreditLine(c){
    if(!c) return;
    const row=document.createElement('div');
    row.style.cssText='font-size:11px;opacity:.72;text-align:left;padding:2px 14px 8px;';
    row.textContent='نرخ هر پیام: '+faNum(c.cost)+' تومان • مصرف شما: '+faNum(c.used)+' • مانده: '+faNum(c.balance)+' تومان';
    messages.appendChild(row);
  }
  async function sendMessage(forced){
    const text=(typeof forced==='string' ? forced : input.value).trim();
    if(!text || loading) return;
    addMsg('user', text);
    input.value='';
    autosize();
    setBusy(true);
    try{
      const resp=await fetch('/api/ai-widget/chat',{
        method:'POST', headers:{'Content-Type':'application/json','X-AI-Widget-CSRF':csrf},
        body:JSON.stringify({message:text,page:location.pathname})
      });
      const data=await resp.json();
      if(data.ok){
        initData=data;
        renderHistory(data.history||[]);
        applyData(data);
        if(data.ai_credit) appendCreditLine(data.ai_credit);
      } else {
        addMsg('ai', data.error||'فعلاً پاسخ در دسترس نیست.');
      }
    }catch(e){
      addMsg('ai','در ارتباط با سرور وقفه افتاد؛ چند لحظه بعد دوباره امتحان کن.');
    }
    setBusy(false);
    messages.scrollTop=messages.scrollHeight;
  }
  async function openWidget(){
    try{
      await loadInit();
      setOpen(true);
      if(input){ input.focus(); autosize(); }
    }catch(e){
      console.error(e);
    }
  }
  window.gisoOpenAiWidget = openWidget;
  fab.addEventListener('click', openWidget);
  document.addEventListener('click', (e)=>{
    const t = e.target && e.target.closest && e.target.closest('[data-giso-open-widget]');
    if(!t) return;
    e.preventDefault();
    openWidget();
  });

  closeBtn.addEventListener('click', ()=>setOpen(false));
  if(bubbleClose){ bubbleClose.addEventListener('click', ()=>stopAttention(true)); }
  send.addEventListener('click', ()=>sendMessage());
  input.addEventListener('input', autosize);
  input.addEventListener('keydown', e=>{
    if(e.key==='Enter' && !e.shiftKey){
      e.preventDefault();
      sendMessage();
    }
  });

  const boot = () => loadInit().catch(e => console.error(e));

  if('requestIdleCallback' in window){
    requestIdleCallback(boot, { timeout: 1200 });
  } else {
    setTimeout(boot, 120);
  }

})();
