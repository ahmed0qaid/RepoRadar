let all=[];
const fmt=n=>new Intl.NumberFormat('en',{notation:n>999?'compact':'standard',maximumFractionDigits:1}).format(n);
function render(){
 const q=document.querySelector('#search').value.toLowerCase();
 const lang=document.querySelector('#language').value;
 const sort=document.querySelector('#sort').value;
 const rows=all.filter(r=>!lang||r.language===lang).filter(r=>`${r.full_name} ${r.description} ${(r.topics||[]).join(' ')}`.toLowerCase().includes(q)).sort((a,b)=>(b[sort]||0)-(a[sort]||0));
 const grid=document.querySelector('#grid'); grid.innerHTML='';
 document.querySelector('#empty').hidden=rows.length>0;
 for(const r of rows){
  const [owner,name]=r.full_name.split('/');
  const tags=[r.language,...(r.topics||[]).slice(0,3)].filter(Boolean);
  grid.insertAdjacentHTML('beforeend',`<article class="card"><div class="top"><div><a class="repo" href="${r.url}" target="_blank"><span class="owner">${owner}/</span>${name} ↗</a></div><div class="score"><strong>${r.rising_score}</strong><span>Rising</span></div></div><p class="desc">${escapeHtml(r.description)}</p><div class="tags">${tags.map(t=>`<span class="tag">${escapeHtml(t)}</span>`).join('')}</div><div class="metrics"><div class="metric"><strong>★ ${fmt(r.stars)}</strong><span>stars</span></div><div class="metric"><strong class="positive">+${fmt(r.star_delta)}</strong><span>since snapshot</span></div><div class="metric"><strong>${fmt(r.open_issues)}</strong><span>open issues</span></div><div class="metric"><strong>${r.opportunity_score}</strong><span>opportunity</span></div></div></article>`)
 }
}
function escapeHtml(s=''){return s.replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
fetch('data/repositories.json').then(r=>r.json()).then(data=>{
 all=data.repositories||[];
 document.querySelector('#repoCount').textContent=all.length;
 document.querySelector('#updated').textContent=data.generated_at?new Date(data.generated_at).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'Not yet';
 const langs=[...new Set(all.map(r=>r.language).filter(Boolean))].sort();
 document.querySelector('#language').insertAdjacentHTML('beforeend',langs.map(l=>`<option>${escapeHtml(l)}</option>`).join(''));
 render();
}).catch(()=>render());
['search','language','sort'].forEach(id=>document.querySelector('#'+id).addEventListener(id==='search'?'input':'change',render));
