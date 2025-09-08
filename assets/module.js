// Shared module UI logic
(function(){
  function $(sel, root=document){ return root.querySelector(sel); }
  function esc(s){ return (s||'').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
  function slugFromPath(){
    const parts = location.pathname.replace(/\/+$/,'').split('/').filter(Boolean);
    let last = parts[parts.length-1] || '';
    if (last.endsWith('.html')) last = parts[parts.length-2] || last.replace(/\.html$/,'');
    return last;
  }
  function renderShell(app){
    app.innerHTML = `
      <div class="card">
        <h1 id="mod-title">Learning Module</h1>
        <p class="muted"><a id="pdf-link" href="#" target="_blank" rel="noopener">View PDF</a></p>
        <p class="muted"><a href="../">← Back to all modules</a></p>
        <div id="xp" class="xp-badge" aria-live="polite" style="margin-top:8px;display:inline-flex">⭐ <span id="xp-points">0</span> pts</div>
      </div>
      <div class="card">
        <div class="tabs">
          <button class="tab active" data-target="panel-flashcards">Flashcards</button>
          <button class="tab" data-target="panel-questions">Questions</button>
          <button class="tab" data-target="panel-scenarios">Scenarios</button>
          <button class="tab" data-target="panel-content">Content</button>
        </div>
      </div>
      <div id="panel-flashcards" class="card panel active">
        <div style="display:flex;align-items:center;gap:10px;justify-content:space-between">
          <h2 style="margin:0">Flashcards</h2>
          <div>
            <select id="fc-category" class="btn"><option value="">All Categories</option></select>
            <input id="fc-search" class="btn" placeholder="Search..." style="width:180px" />
          </div>
        </div>
        <div id="fc-card" class="flashcard" style="margin-top:12px">
          <div id="fc-term" class="flash-term"></div>
          <div id="fc-def" class="flash-def muted" style="display:none"></div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;margin-top:10px">
          <button id="fc-prev" class="btn">Prev</button>
          <button id="fc-reveal" class="btn">Reveal</button>
          <button id="fc-next" class="btn">Next</button>
          <button id="fc-shuffle" class="btn">Shuffle</button>
          <span id="fc-status" class="muted" style="margin-left:auto"></span>
        </div>
        <div id="fc-empty" class="muted" style="display:none;margin-top:8px">No flashcards found.</div>
      </div>
      <div id="panel-questions" class="card panel">
        <div style="display:flex;align-items:center;gap:10px;justify-content:space-between">
          <h2 style="margin:0">Questions</h2>
          <button id="revealAllQ" class="btn" title="Reveal answers for all questions">Reveal All</button>
        </div>
        <div id="qlist"></div>
        <div id="qempty" class="muted" style="display:none">No questions yet.</div>
      </div>
      <div id="panel-scenarios" class="card panel">
        <h2 style="margin:0 0 10px">Scenarios</h2>
        <div id="slist"></div>
        <div id="sempty" class="muted" style="display:none">No scenarios yet.</div>
      </div>
      <div id="panel-content" class="card panel">
        <h2 style="margin-top:0">Module Content</h2>
        <div id="toc" style="margin-bottom:12px"></div>
        <div id="sections"></div>
        <div id="empty" class="muted" style="display:none">No extracted content found.</div>
      </div>`;
  }

  function setupTabs(){
    const tabs = document.querySelectorAll('.tab');
    const panels = document.querySelectorAll('.panel');
    function activate(id){
      tabs.forEach(t=>t.classList.toggle('active', t.dataset.target===id));
      panels.forEach(p=>p.classList.toggle('active', p.id===id));
    }
    tabs.forEach(t=>t.addEventListener('click', ()=>activate(t.dataset.target)));
    activate('panel-flashcards');
  }

  function renderParagraph(p){
    const subHeads = ['Purpose','Definitions','Procedures','Policy','Scope'];
    const t = (p||'').trim();
    if (subHeads.includes(t)) return `<h4 style="margin:12px 0 6px">${t}</h4>`;
    const m = t.match(/^(Purpose|Definitions|Procedures|Policy|Scope)\s*:\s*(.+)$/);
    if (m) return `<h4 style="margin:12px 0 6px">${m[1]}</h4><p>${m[2]}</p>`;
    return `<p>${esc(p)}</p>`;
  }

  async function loadMeta(slug){
    try{
      const res = await fetch('./content/meta.json', { cache:'no-store' });
      if(!res.ok) return;
      const meta = await res.json();
      const title = meta.title || slug.replace(/-/g,' ');
      document.title = `${title}`;
      const el = $('#mod-title'); if (el) el.textContent = `${title}`;
  }catch{}
  }

  async function loadSections(){
    const toc = $('#toc'); const sec = $('#sections'); const empty=$('#empty');
    try{
      const res = await fetch('./content/sections.json', { cache:'no-store' });
      if(!res.ok) throw new Error('Missing');
      const sections = await res.json();
      if(!Array.isArray(sections)||!sections.length) throw new Error('Empty');
      toc.innerHTML = sections.map((s,i)=>`<a href="#sec-${i}" style="margin-right:10px">${esc(s.heading||('Section '+(i+1)))}</a>`).join(' ');
      sec.innerHTML = sections.map((s,i)=>{
        const paras = (s.paragraphs||[]).map(renderParagraph).join('\n');
        return `<section id="sec-${i}" style="margin:16px 0"><h3>${esc(s.heading||('Section '+(i+1)))}</h3>${paras}</section>`;
      }).join('\n');
    }catch(e){ if(empty) empty.style.display='block'; }
  }

  // Questions
  function renderQuestion(q, idx){
    const letters=['A','B','C','D'];
    const opts = letters.map(letter => {
      const v = q.options && q.options[letter] ? esc(q.options[letter]) : '';
      return `<label class="opt"><input type="radio" name="q_${idx}" value="${letter}"> <strong>${letter}.</strong> ${v}</label>`;
    }).join('');
    return `<div class="q" data-ans="${q.correct}">
      <h4>${esc(q.text)}</h4>
      <div class="muted" style="margin-bottom:6px">${esc(q.category||'')}</div>
      <div class="opts">${opts}</div>
      <button class="btn check">Check</button>
      <div class="ex muted" style="display:none"></div>
    </div>`;
  }
  async function loadQuestions(){
    const box = $('#qlist'); const empty=$('#qempty'); const reveal=$('#revealAllQ');
    const slug = slugFromPath();
    const storeKey = `ahls:progress:${slug}`;
    const xpEl = $('#xp-points');
    const progress = JSON.parse(localStorage.getItem(storeKey) || '{}');
    progress.points = progress.points || 0;
    progress.answered = progress.answered || {};
    try{
      const res = await fetch('./data/questions.json',{cache:'no-store'}); if(!res.ok) throw new Error('missing');
      const data = await res.json(); const qs = data.questions||[]; if(!qs.length) throw new Error('empty');
      box.innerHTML = qs.map((q,i)=>renderQuestion(q,i)).join('');
      box.querySelectorAll('.q').forEach((el, i)=>{
        const correct=(el.dataset.ans||'').trim(); const ex=el.querySelector('.ex');
        el.querySelector('.check').addEventListener('click',()=>{
          const choice=el.querySelector('input[type=radio]:checked');
          el.querySelectorAll('.opt').forEach(o=>o.classList.remove('correct','incorrect'));
          if(!choice){ ex.style.display='block'; ex.textContent=`Answer: ${correct}`; return; }
          const selected=choice.value; const labels=el.querySelectorAll('.opt');
          const map={A:0,B:1,C:2,D:3}; const idx=map[selected]; const cidx=map[correct];
          if(idx!==undefined) labels[idx].classList.add(selected===correct?'correct':'incorrect');
          if(cidx!==undefined) labels[cidx].classList.add('correct');
          ex.style.display='block'; ex.textContent=`Answer: ${correct}`;
          const qid = `q_${i}`;
          if (selected===correct && !progress.answered[qid]) {
            progress.answered[qid]=true; progress.points += 10; xpEl.textContent = String(progress.points); saveProgress(storeKey, progress); toast('Correct! +10 pts', 'success');
          } else if (selected!==correct) {
            toast('Not quite—try again', 'error');
          }
        });
      });
      if (reveal) reveal.addEventListener('click',()=>{
        box.querySelectorAll('.q').forEach(el=>{
          const c=(el.dataset.ans||'').trim(); const labels=el.querySelectorAll('.opt');
          const map={A:0,B:1,C:2,D:3}; labels.forEach(l=>l.classList.remove('correct','incorrect'));
          const cidx=map[c]; if(cidx!==undefined) labels[cidx].classList.add('correct');
          const ex=el.querySelector('.ex'); ex.style.display='block'; ex.textContent=`Answer: ${c}`;
        });
      });
    }catch(e){ if(empty) empty.style.display='block'; }
  }

  // Flashcards (from terms)
  async function loadFlashcards(){
    const catSel = $('#fc-category'); const search = $('#fc-search');
    const termEl = $('#fc-term'); const defEl = $('#fc-def'); const statusEl = $('#fc-status');
    const empty = $('#fc-empty'); const btnPrev=$('#fc-prev'); const btnNext=$('#fc-next');
    const btnReveal=$('#fc-reveal'); const btnShuffle=$('#fc-shuffle');
    let all = [];
    try{ const res=await fetch('./data/terms.json',{cache:'no-store'}); if(!res.ok) throw new Error('missing'); const data=await res.json(); all=data.terms||[]; }catch(e){ if(empty) empty.style.display='block'; return; }
    const cats = Array.from(new Set(all.map(t=>t.category).filter(Boolean))).sort();
    cats.forEach(c=>{ const o=document.createElement('option'); o.value=c; o.textContent=c; catSel.appendChild(o); });
    let deck=[]; let idx=0; let revealed=false;
    function applyFilters(){ const q=(search.value||'').toLowerCase(); const cat=catSel.value||'';
      deck=all.filter(t=>{ if(cat && t.category!==cat) return false; const blob=`${t.term} ${t.definition} ${t.category||''}`.toLowerCase(); return blob.includes(q); });
      idx=0; revealed=false; render(); }
    function render(){ if(deck.length===0){ if(empty) empty.style.display='block'; termEl.textContent=''; defEl.style.display='none'; defEl.textContent=''; statusEl.textContent='0 / 0'; return; }
      if(empty) empty.style.display='none'; const cur=deck[idx]; termEl.textContent=cur.term||''; defEl.textContent=cur.definition||''; defEl.style.display=revealed?'block':'none'; statusEl.textContent=`${idx+1} / ${deck.length}`; btnReveal.textContent=revealed?'Hide':'Reveal'; }
    function next(){ if(deck.length){ idx=(idx+1)%deck.length; revealed=false; render(); } }
    function prev(){ if(deck.length){ idx=(idx-1+deck.length)%deck.length; revealed=false; render(); } }
        function reveal(){ if(deck.length){
          revealed=!revealed; render();
          if (revealed) { const key=`ahls:progress:${slugFromPath()}`; const st=JSON.parse(localStorage.getItem(key)||'{}'); st.points=(st.points||0)+1; localStorage.setItem(key,JSON.stringify(st)); const xpEl=$('#xp-points'); if (xpEl) xpEl.textContent=String(st.points); toast('Revealed +1 pt','success'); }
        } }
    function shuffle(){ for(let i=deck.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [deck[i],deck[j]]=[deck[j],deck[i]]; } idx=0; revealed=false; render(); }
    btnNext.addEventListener('click', next); btnPrev.addEventListener('click', prev); btnReveal.addEventListener('click', reveal); btnShuffle.addEventListener('click', shuffle);
    catSel.addEventListener('change', applyFilters); search.addEventListener('input', applyFilters);
    applyFilters();
  }

  // Scenarios
  function renderScenario(s, idx){
    const letters=['A','B','C','D'];
    const opts = letters.map(letter => {
      const v = s.options && s.options[letter] ? esc(s.options[letter]) : '';
      return `<label class="opt"><input type="radio" name="s_${idx}" value="${letter}"> <strong>${letter}.</strong> ${v}</label>`;
    }).join('');
    return `<div class="q" data-ans="${s.correct}">
      <h4>${esc(s.title||'Scenario')}</h4>
      <div class="muted" style="margin-bottom:6px">${esc(s.description||'')}</div>
      <div class="opts">${opts}</div>
      <button class="btn check">Check</button>
      <div class="ex muted" style="display:none"></div>
    </div>`;
  }
  async function loadScenarios(){
    const box = $('#slist'); const empty=$('#sempty');
    const slug = slugFromPath(); const storeKey=`ahls:progress:${slug}`; const xpEl=$('#xp-points');
    const progress = JSON.parse(localStorage.getItem(storeKey) || '{}'); progress.points=progress.points||0; progress.scAnswered=progress.scAnswered||{};
    try{ const res=await fetch('./data/scenarios.json',{cache:'no-store'}); if(!res.ok) throw new Error('missing'); const data=await res.json(); const items=data.scenarios||[]; if(!items.length) throw new Error('empty');
      box.innerHTML = items.map((s,i)=>renderScenario(s,i)).join('');
      box.querySelectorAll('.q').forEach((el,i)=>{
        const correct=(el.dataset.ans||'').trim(); const ex=el.querySelector('.ex');
        el.querySelector('.check').addEventListener('click',()=>{
          const choice=el.querySelector('input[type=radio]:checked');
          el.querySelectorAll('.opt').forEach(o=>o.classList.remove('correct','incorrect'));
          if(!choice){ ex.style.display='block'; ex.textContent=`Answer: ${correct}`; return; }
          const selected=choice.value; const labels=el.querySelectorAll('.opt');
          const map={A:0,B:1,C:2,D:3}; const idx=map[selected]; const cidx=map[correct];
          if(idx!==undefined) labels[idx].classList.add(selected===correct?'correct':'incorrect');
          if(cidx!==undefined) labels[cidx].classList.add('correct');
          ex.style.display='block'; ex.textContent=`Answer: ${correct}`;
          const sid=`s_${i}`;
          if (selected===correct && !progress.scAnswered[sid]) { progress.scAnswered[sid]=true; progress.points+=5; xpEl.textContent=String(progress.points); localStorage.setItem(storeKey, JSON.stringify(progress)); toast('Nice! +5 pts', 'success'); }
          else if (selected!==correct) { toast('Not quite—try again', 'error'); }
        });
      });
    }catch(e){ if(empty) empty.style.display='block'; }
  }

  // Progress helpers & toasts
  function saveProgress(k, v){ try{ localStorage.setItem(k, JSON.stringify(v)); }catch(e){} }
  function toast(text, type){
    const t=document.createElement('div'); t.className='toast'+(type?` ${type}`:''); t.textContent=text; document.body.appendChild(t);
    setTimeout(()=>{ t.style.opacity='0'; setTimeout(()=>{ t.remove(); }, 300); }, 1200);
  }

  document.addEventListener('DOMContentLoaded', ()=>{
    const app = document.getElementById('app');
    if (!app) return;
    renderShell(app);
    setupTabs();
    const slug = slugFromPath();
    // Set PDF link href
    const pdfLink = document.getElementById('pdf-link');
    if (pdfLink) pdfLink.href = `./${slug}.pdf`;
    loadMeta(slug);
    loadSections();
    loadQuestions();
    loadScenarios();
    loadFlashcards();
    if ('serviceWorker' in navigator) { navigator.serviceWorker.register('/assets/sw.js').catch(()=>{}); }
  });
})();
