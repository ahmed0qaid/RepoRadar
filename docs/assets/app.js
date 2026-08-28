let all=[];
let issues=[];
let activeCategory='';

const fmt=n=>new Intl.NumberFormat('en',{notation:Math.abs(n)>999?'compact':'standard',maximumFractionDigits:1}).format(n||0);
const pct=n=>`${Number(n||0).toFixed(1)}%`;
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

function categoryLabel(key){
 return ({trending_now:'Trending now',rising_fast:'Rising fast',hidden_gem:'Hidden gem',best_to_contribute:'Best to contribute',watchlist:'Watchlist'})[key]||key;
}

function render(){
 const q=document.querySelector('#search').value.toLowerCase().trim();
 const lang=document.querySelector('#language').value;
 const sort=document.querySelector('#sort').value;
 const rows=all
  .filter(r=>!activeCategory||(r.categories||[]).includes(activeCategory))
  .filter(r=>!lang||r.language===lang)
  .filter(r=>`${r.full_name} ${r.description} ${r.language} ${(r.topics||[]).join(' ')}`.toLowerCase().includes(q))
  .sort((a,b)=>(Number(b[sort])||0)-(Number(a[sort])||0));

 const grid=document.querySelector('#grid');
 grid.innerHTML='';
 document.querySelector('#empty').hidden=rows.length>0;
 document.querySelector('#sectionTitle').textContent=activeCategory?categoryLabel(activeCategory):'Repository radar';

 for(const r of rows){
  const [owner,name]=r.full_name.split('/');
  const tags=[r.language,...(r.topics||[]).slice(0,3)].filter(Boolean);
  const labels=(r.categories||[]).filter(x=>x!=='watchlist').slice(0,2);
  const historyState=r.has_24h_history?'measured':'warming up';
  grid.insertAdjacentHTML('beforeend',`
   <article class="card">
    <div class="top">
      <div>
       <div class="signal-badges">${labels.map(x=>`<span class="signal-badge ${esc(x)}">${esc(categoryLabel(x))}</span>`).join('')}</div>
       <a class="repo" href="${esc(r.url)}" target="_blank" rel="noreferrer"><span class="owner">${esc(owner)}/</span>${esc(name)} ↗</a>
      </div>
      <div class="score"><strong>${Number(r.viral_score||r.rising_score||0).toFixed(1)}</strong><span>Viral</span></div>
    </div>
    <p class="desc">${esc(r.description)}</p>
    <div class="tags">${tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>
    <div class="growth-row">
      <div><span>6h</span><strong>+${fmt(r.growth_6h)}</strong></div>
      <div><span>24h</span><strong>+${fmt(r.growth_24h)}</strong><small>${r.has_24h_history?pct(r.growth_24h_pct):historyState}</small></div>
      <div><span>7d</span><strong>+${fmt(r.growth_7d)}</strong><small>${r.has_7d_history?pct(r.growth_7d_pct):historyState}</small></div>
    </div>
    <div class="metrics">
      <div class="metric"><strong>★ ${fmt(r.stars)}</strong><span>stars</span></div>
      <div class="metric"><strong>${fmt(r.star_velocity)}</strong><span>stars/hour</span></div>
      <div class="metric"><strong class="${Number(r.star_acceleration)>0?'positive':''}">${Number(r.star_acceleration||0).toFixed(2)}</strong><span>acceleration</span></div>
      <div class="metric"><strong>${Number(r.opportunity_score||0).toFixed(1)}</strong><span>opportunity</span></div>
    </div>
   </article>`);
 }
}

function normalizeSkills(raw){
 return [...new Set(raw.split(',').map(s=>s.trim().toLowerCase()).filter(Boolean))];
}

const aliases={
 javascript:['js','node','nodejs','frontend','web'],typescript:['ts','frontend','web','node'],python:['py','backend','ai','ml','data'],
 flutter:['dart','mobile','android','ios'],dart:['flutter','mobile'],backend:['api','server','database','python','node','java','go'],
 ai:['ml','machine learning','llm','agent','agents','rag','python'],documentation:['docs','readme','writing'],docs:['documentation','readme'],
 docker:['containers','devops'],cloud:['aws','azure','gcp','devops'],database:['sql','postgres','postgresql','mysql','sqlite','backend']
};

function expandedSkills(skills){
 const set=new Set(skills);
 for(const s of skills){ for(const a of aliases[s]||[]) set.add(a); }
 return [...set];
}

function scoreIssue(issue, skills){
 const expanded=expandedSkills(skills);
 const hay=`${issue.title||''} ${issue.body_excerpt||''} ${(issue.labels||[]).join(' ')} ${issue.language||''} ${(issue.topics||[]).join(' ')}`.toLowerCase();
 let skillHits=[];
 for(const skill of expanded){ if(hay.includes(skill)) skillHits.push(skill); }
 const originalHits=skills.filter(s=>hay.includes(s));
 let score=originalHits.length*24+(skillHits.length-originalHits.length)*8;
 const labels=(issue.labels||[]).map(x=>x.toLowerCase());
 if(labels.some(x=>x.includes('good first issue'))) score+=18;
 if(labels.some(x=>x.includes('help wanted'))) score+=13;
 if(labels.some(x=>x.includes('beginner')||x.includes('easy'))) score+=8;
 score+=Math.min(16,Number(issue.repo_opportunity_score||0)*0.16);
 score+=Math.min(10,Number(issue.issue_opportunity_score||0)*0.1);
 score-=Math.min(12,Number(issue.comments||0)*1.5);
 return {score:Math.max(0,Math.min(100,Math.round(score))),hits:[...new Set(skillHits)].slice(0,5)};
}

function renderMatches(){
 const skills=normalizeSkills(document.querySelector('#skills').value);
 const grid=document.querySelector('#issueGrid');
 const summary=document.querySelector('#matchSummary');
 grid.innerHTML='';
 if(!skills.length){ summary.hidden=false; summary.textContent='Add at least one skill, separated by commas.'; return; }
 localStorage.setItem('reporadar-skills',skills.join(', '));
 const ranked=issues.map(i=>({...i,_match:scoreIssue(i,skills)})).filter(i=>i._match.score>0).sort((a,b)=>b._match.score-a._match.score).slice(0,18);
 summary.hidden=false;
 summary.innerHTML=`Matched <strong>${ranked.length}</strong> opportunities for <strong>${esc(skills.join(', '))}</strong>.`;
 if(!ranked.length){ grid.innerHTML='<div class="empty">No matching issues yet. Try broader skills such as backend, AI, docs or TypeScript.</div>'; return; }
 for(const i of ranked){
  const labels=(i.labels||[]).slice(0,4);
  grid.insertAdjacentHTML('beforeend',`
   <article class="issue-card">
    <div class="issue-head"><span class="match-score">${i._match.score}% match</span><span class="difficulty">${esc(i.difficulty||'Open')}</span></div>
    <a href="${esc(i.url)}" target="_blank" rel="noreferrer" class="issue-title">${esc(i.title)} ↗</a>
    <a href="${esc(i.repo_url)}" target="_blank" rel="noreferrer" class="issue-repo">${esc(i.repository)}</a>
    <p>${esc(i.body_excerpt||'Public GitHub issue ready for review.')}</p>
    <div class="tags">${labels.map(l=>`<span class="tag">${esc(l)}</span>`).join('')}</div>
    <div class="match-meta"><span>${esc(i.language||'Other')}</span><span>${i.comments||0} comments</span><span>Opportunity ${Number(i.issue_opportunity_score||0).toFixed(0)}</span></div>
    <div class="why">Matched: ${i._match.hits.length?esc(i._match.hits.join(', ')):'repository activity'}</div>
   </article>`);
 }
}

Promise.all([
 fetch('data/repositories.json').then(r=>r.ok?r.json():{repositories:[]}),
 fetch('data/issues.json').then(r=>r.ok?r.json():{issues:[]}).catch(()=>({issues:[]}))
]).then(([data,issueData])=>{
 all=data.repositories||[];
 issues=issueData.issues||[];
 document.querySelector('#repoCount').textContent=all.length;
 document.querySelector('#risingCount').textContent=data.signals?.rising_fast||0;
 document.querySelector('#gemCount').textContent=data.signals?.hidden_gem||0;
 document.querySelector('#updated').textContent=data.generated_at?new Date(data.generated_at).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'Not yet';
 const langs=[...new Set(all.map(r=>r.language).filter(Boolean))].sort();
 document.querySelector('#language').insertAdjacentHTML('beforeend',langs.map(l=>`<option>${esc(l)}</option>`).join(''));
 const saved=localStorage.getItem('reporadar-skills'); if(saved) document.querySelector('#skills').value=saved;
 render();
}).catch(()=>render());

document.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click',()=>{
 document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
 btn.classList.add('active'); activeCategory=btn.dataset.category||''; render();
}));
['search','language','sort'].forEach(id=>document.querySelector('#'+id).addEventListener(id==='search'?'input':'change',render));
document.querySelector('#matchBtn').addEventListener('click',renderMatches);
document.querySelector('#skills').addEventListener('keydown',e=>{if(e.key==='Enter') renderMatches()});
document.querySelectorAll('[data-skill]').forEach(btn=>btn.addEventListener('click',()=>{
 const input=document.querySelector('#skills'); const current=normalizeSkills(input.value); const skill=btn.dataset.skill;
 if(!current.includes(skill.toLowerCase())) input.value=[...current,skill].join(', '); renderMatches();
}));
