/* Motor de presentación original del Match Centre 6.3.
   La plantilla y las funciones de UI provienen del archivo original.
   El contenido ahora llega desde la API privada de KARUBET vía parent window. */
"use strict";
function startClassic(payload) {
  if(window.__classicStarted) return;
  window.__classicStarted=true;
  window.__karubetClassicPayload=payload;
  document.querySelectorAll('img[data-karubet-logo]').forEach(img=>{
    if(window.KARUBET_ORIGINAL_LOGO) img.src=window.KARUBET_ORIGINAL_LOGO;
  });
  (function(){
const payload=window.__karubetClassicPayload,data=payload.rows, meta=payload.meta;
const logos=payload.logos||{}, leagueLogos=payload.league_logos||{};
const leagueForTeam=new Map();
for(const match of data){for(const team of [match.home,match.away]){
  if(team&&!leagueForTeam.has(team))leagueForTeam.set(team,match.competition);
}}
const lg={'epl':'Premier League','la-liga':'LaLiga','serie-a':'Serie A','bundesliga':'Bundesliga','ligue-1':'Ligue 1'},
      ev={pa:'PA',qpa:'Quasi Doble PA',dpa:'Doble PA',rem:'Remontada'};
const $=id=>document.getElementById(id);
const esc=s=>String(s??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=n=>n==null?'—':(100*n).toFixed(1)+'%';
const num=(n,d=2)=>n==null?'—':Number(n).toFixed(d);
const fmtDay=s=>s?new Date(s+'T12:00:00Z').toLocaleDateString('es-PE',{weekday:'short',day:'numeric',month:'short',timeZone:'UTC'}):'—';
const add=(s,n)=>{let d=new Date(s+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)};
let view='fixture',selected=null;

// Autocompletado local sobre el fixture 2026/27, sin servidor ni peticiones externas.
const clubNorm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('es').replace(/[^a-z0-9 ]/g,' ').replace(/\s+/g,' ').trim();
const aliases={
 'barca':'barcelona','barça':'barcelona','man utd':'manchester united','man united':'manchester united',
 'man city':'manchester city','atleti':'atletico madrid','bayern munich':'bayern','psg':'paris saint germain',
 'inter milan':'inter','spurs':'tottenham','wolves':'wolverhampton'
};
const queryNorm=s=>{const n=clubNorm(s);return clubNorm(aliases[n]||n)};
const clubIndex=(()=>{
 const clubs=new Map();
 for(const r of data)for(const name of [r.home,r.away]){
  if(!name)continue;const key=r.competition+'|'+clubNorm(name);
  if(!clubs.has(key))clubs.set(key,{name,league:r.competition,count:0});
  clubs.get(key).count++;
 }
 return [...clubs.values()].sort((a,b)=>a.name.localeCompare(b.name,'es'));
})();
let selectedClub=null, clubOptions=[],clubActive=-1;
const clubQuery=()=>queryNorm($('teamQuery').value);
function clubMatch(name,q){const n=clubNorm(name);return !q||n.includes(q)||n.split(' ').some(w=>w.startsWith(q))}
function clubDistance(a,b){let prev=Array.from({length:b.length+1},(_,i)=>i);for(let i=1;i<=a.length;i++){const cur=[i];for(let j=1;j<=b.length;j++)cur[j]=Math.min(cur[j-1]+1,prev[j]+1,prev[j-1]+(a[i-1]===b[j-1]?0:1));prev=cur}return prev[b.length]}
function clubSuggestions(query){
 const q=queryNorm(query);if(!q)return clubIndex.slice(0,7);
 return clubIndex.map(c=>{const n=clubNorm(c.name),words=n.split(' ');let score=n===q?0:n.startsWith(q)?1:words.some(w=>w.startsWith(q))?2:n.includes(q)?3:50;
  if(score===50&&q.length>=5&&words.some(w=>Math.abs(w.length-q.length)<=2&&clubDistance(w,q)<=(q.length>=7?2:1)))score=4;
  return {...c,score};
 }).filter(c=>c.score<50).sort((a,b)=>a.score-b.score||a.name.localeCompare(b.name,'es')).slice(0,8);
}
function hideClubSuggestions(){ $('teamSuggestions').hidden=true;$('teamQuery').setAttribute('aria-expanded','false');clubActive=-1; }
function paintClubSuggestions(){
 const input=$('teamQuery'),area=$('teamSuggestions');clubOptions=clubSuggestions(input.value);clubActive=-1;
 if(!clubOptions.length){area.innerHTML='<div class="team-search-help">No encuentro ese equipo. Prueba otra palabra.</div>'}
 else area.innerHTML=clubOptions.map((c,i)=>`<button type="button" class="team-suggestion" role="option" data-club-i="${i}" aria-selected="false">${crest(c.name)}<span class="team-suggestion-label"><strong>${esc(c.name)}</strong><small>${esc(lg[c.league]||c.league)} · ${c.count} partidos</small></span></button>`).join('');
 area.hidden=false;input.setAttribute('aria-expanded','true');
}
function highlightClub(i){clubActive=i;const buttons=[...$('teamSuggestions').querySelectorAll('[data-club-i]')];buttons.forEach((b,j)=>{b.classList.toggle('active',j===i);b.setAttribute('aria-selected',j===i?'true':'false')});buttons[i]?.scrollIntoView({block:'nearest'})}
function chooseClub(c){if(!c)return;selectedClub=c;$('teamQuery').value=c.name;$('teamClear').hidden=false;hideClubSuggestions();
 // Al elegir un club se muestran sus próximos partidos de toda la temporada.
 const upcoming=data.map(r=>r.dia).filter(d=>d>=meta.today).sort();if(upcoming.length){$('start').value=upcoming[0];$('end').value=upcoming[upcoming.length-1]}
 $('league').value=c.league;render();
}
function resetClub(){selectedClub=null;$('teamQuery').value='';$('teamClear').hidden=true;hideClubSuggestions();$('league').value='all';view='fixture';week();}
function updateClubStatus(rows){
 const node=$('teamSearchStatus');const q=$('teamQuery').value.trim();node.classList.toggle('show',!!q);
 if(q){node.innerHTML=selectedClub?`<span>⚽ <strong>${esc(selectedClub.name)}</strong> · ${rows.length} partidos encontrados · 2026/27</span>`:`<span>🔎 Coincidencias con <strong>${esc(q)}</strong> · ${rows.length} en las fechas seleccionadas. Elige un equipo para ver toda su temporada.</span>`}
 else node.textContent='';
}
$('teamQuery').addEventListener('input',()=>{selectedClub=null;$('teamClear').hidden=!$('teamQuery').value;paintClubSuggestions();render()});
$('teamQuery').addEventListener('focus',()=>paintClubSuggestions());
$('teamQuery').addEventListener('keydown',e=>{if(e.key==='Escape'){hideClubSuggestions();return}if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if($('teamSuggestions').hidden)paintClubSuggestions();if(clubOptions.length)highlightClub((clubActive+(e.key==='ArrowDown'?1:-1)+clubOptions.length)%clubOptions.length);return}if(e.key==='Enter'){if(!$('teamSuggestions').hidden&&clubOptions.length){e.preventDefault();chooseClub(clubOptions[clubActive>=0?clubActive:0])}}});
$('teamSuggestions').addEventListener('click',e=>{const b=e.target.closest('[data-club-i]');if(b)chooseClub(clubOptions[Number(b.dataset.clubI)])});
$('teamClear').addEventListener('click',resetClub);
document.addEventListener('pointerdown',e=>{if(!$('teamSearch').contains(e.target))hideClubSuggestions()});

const event=()=> $('event').value,k=()=>Number($('k').value);
function hashColor(str){let h=0;for(let i=0;i<str.length;i++)h=(h*31+str.charCodeAt(i))>>>0;const hue=h%360;const hue2=(hue+35)%360;return [`hsl(${hue} 70% 42%)`,`hsl(${hue2} 75% 55%)`];}
function initials(name){const clean=(name||'').replace(/\b(?:FC|CF|AC|SC|SV|AS|RC|CD|UD|US|SSC)\b/gi,'').replace(/[^A-Za-zÀ-ÿ0-9 ]/g,'').trim();const parts=clean.split(/\s+/).filter(Boolean);if(parts.length===0)return 'FC';if(parts.length===1)return parts[0].slice(0,3).toUpperCase();return (parts[0][0]+parts[1][0]+(parts[2]?.[0]||'')).toUpperCase();}
function crest(name, league=false){const cls=league?'league-crest':'crest';const ids=league?leagueLogos:logos;const key=league?(Object.keys(lg).find(k=>lg[k]===name)||name):name;const urls=ids[key]||[];const url=(league?window.KARUBET_LEAGUE_CREST?.(key):window.KARUBET_TEAM_CREST?.(name,leagueForTeam.get(name)))||urls[0];return `<span class="${cls}"><span class="initials">${esc(initials(name))}</span>${url?`<img alt="" loading="lazy" referrerpolicy="no-referrer" src="${esc(url)}" data-alt="${esc(urls[1]||'')}" onerror="if(this.dataset.alt){const next=this.dataset.alt;this.dataset.alt='';this.src=next}else{this.remove()}">`:''}</span>`}
function modelLabel(v){return v==='ewma'?'Forma actual':v==='h2h'?'Forma + historial':'Referencia';}
function filt(){const mode=$('model').value;for(const r of data){for(const e of Object.keys(ev)){r[e]=r[mode+'_'+e];r['fair_'+e]=r[e]>0?1/r[e]:null}}const q=clubQuery();return data.filter(r=>r.dia>=$('start').value&&r.dia<=$('end').value&&($('league').value==='all'||$('league').value===r.competition)&&(!q||(selectedClub?clubNorm(r.home)===clubNorm(selectedClub.name)||clubNorm(r.away)===clubNorm(selectedClub.name):clubMatch(r.home,q)||clubMatch(r.away,q))))}
function sorted(a,rev=false){return [...a].sort((x,y)=>(rev?1:-1)*(x[event()]-y[event()])||x.dia.localeCompare(y.dia)||x.hora.localeCompare(y.hora))}
function week(){ const first=data.filter(r=>r.dia>=meta.today).map(r=>r.dia).sort()[0]||meta.today;$('start').value=first;$('end').value=add(first,6);render() }
function entireSeason(){
 const dates=data.map(r=>r.dia).filter(Boolean).sort();
 if(!dates.length)return;
 $('start').value=dates[0];$('end').value=dates[dates.length-1];render();
}
for(const [v,t] of Object.entries(lg))$('league').add(new Option(t,v));
$('leagueTabs').innerHTML='<button data-league="all">Todas</button>'+Object.entries(lg).map(([code,name])=>`<button data-league="${code}">${crest(name,true)}${esc(name)}</button>`).join('');$('leagueTabs').onclick=e=>{const b=e.target.closest('[data-league]');if(b){$('league').value=b.dataset.league;render()}};
if($('stamp')) $('stamp').textContent=meta.fresh?'Actualizado en este run':'Copia guardada · no actualizada';
if($('source')) $('source').textContent=(meta.source_date||'Sin fecha confirmada')+' · cálculo '+meta.asof;
function section(title,body,sub=''){return `<section class="section"><div class="section-header"><div><h2>${esc(title)}</h2>${sub?`<p>${esc(sub)}</p>`:''}</div></div>${body}</section>`}

// Pronóstico Poisson: lambda_h / lambda_a = goles medios previstos antes del partido.
// NO son el xG observado en un encuentro ni las cifras de Flashscore.
function projected(x){return typeof x==='number'&&Number.isFinite(x)&&x>=0?x.toFixed(2).replace('.',','):null}
function goalMini(x){const n=projected(x);return n===null?'':`<span class="goal-inline" title="Proyección prematch de goles por el modelo Poisson">xG ${n}</span>`}
function teamNamePred(name,lambda){return `<span class="team-name-stack"><span class="team-primary">${esc(name)}</span>${goalMini(lambda)}</span>`}
function dayTeamName(name,lambda){return `<span class="day-team-stack"><span class="team-primary">${esc(name)}</span>${goalMini(lambda)}</span>`}
function projectedGoals(a){
 const h=projected(a.lambda_h),v=projected(a.lambda_a);
 if(h===null||v===null)return '';
 const total=projected(a.lambda_h+a.lambda_a);
 return `<div class="projected-score"><div class="projected-team"><span>${esc(a.home)}</span><strong>${h}</strong></div><div class="projected-mid">Goles proyectados<br><span style="color:#ffd166">Total ${total}</span></div><div class="projected-team"><strong>${v}</strong><span>${esc(a.away)}</span></div></div>`;
}

// Distribución exacta de marcadores por dos procesos Poisson independientes.
// Los xG mostrados junto a los nombres corresponden a la media de goles del modelo.
function topScorelines(a){
 const h=Number(a.lambda_h),v=Number(a.lambda_a);
 if(!Number.isFinite(h)||!Number.isFinite(v)||h<0||v<0)return [];
 const poisson=(lambda)=>{const p=[Math.exp(-lambda)];for(let i=1;i<=12;i++)p.push(p[i-1]*lambda/i);return p};
 const ph=poisson(h),pv=poisson(v),poss=[];
 for(let i=0;i<ph.length;i++)for(let j=0;j<pv.length;j++)poss.push({home:i,away:j,p:ph[i]*pv[j]});
 return poss.sort((a,b)=>b.p-a.p||a.home+a.away-b.home-b.away).slice(0,3);
}
function compactRead(a){
 const h=Number(a.lambda_h),v=Number(a.lambda_a);
 const gap=h-v;
 let text='';
 if(Math.abs(gap)<.22) text='Veo un duelo bastante equilibrado en goles.';
 else if(Math.abs(gap)<.6) text=`Ligera inclinación hacia ${esc(gap>0?a.home:a.away)} por su producción ofensiva prevista.`;
 else text=`${esc(gap>0?a.home:a.away)} parte con mayor expectativa de gol.`;
 const hp=Number(a.home_pts_ew10),ap=Number(a.away_pts_ew10);
 if(Number.isFinite(hp)&&Number.isFinite(ap)&&Math.abs(hp-ap)>.45){
  const form=hp>ap?a.home:a.away;
  text+=` La forma reciente favorece a ${esc(form)}.`;
 }
 const hist=Array.isArray(a.h2h_matches)?a.h2h_matches:[];
 const labeled=hist.filter(m=>m.pa!==null&&m.pa!==undefined);
 if(labeled.length>=3){const count=labeled.filter(m=>m.pa===1||m.pa===true).length;
  text+=` H2H: ${count} de ${labeled.length} cruces tuvieron PA.`;
 }
 return text;
}
function editorialPick(a){
 const scores=topScorelines(a);
 if(!scores.length)return `<div class="pick-note avoid"><span class="pick-tag">Mi fija</span><strong>Sin proyección de marcador</strong></div>`;
 const items=scores.map((s,i)=>`<div class="score-choice"><b>${s.home}–${s.away}</b><small>${i===0?'Principal · ':''}${pct(s.p)}</small></div>`).join('');
 // El evento de mayor interés es separado del pronóstico exacto de marcador.
 const candidates=[{k:'pa',min:.62},{k:'qpa',min:.30},{k:'dpa',min:.12},{k:'rem',min:.055}];
 const active=candidates.filter(c=>Number.isFinite(a[c.k])&&a[c.k]>=c.min)
  .map(c=>({...c,relative:a[c.k]/c.min})).sort((x,y)=>y.relative-x.relative);
 const signal=active.length?`Señal para observar: ${ev[active[0].k]} ${pct(a[active[0].k])}`:'PA / QPA / DPA: sin selección clara';
 return `<div class="pick-note"><span class="pick-tag">Mi fija · marcadores estimados</span><div class="score-choices">${items}</div><p class="short-read">${compactRead(a)}</p><span class="signal-pill">${signal}</span></div>`;
}

function teamBlock(name,lambda){return `<span class="team">${crest(name)}<span>${teamNamePred(name,lambda)}</span></span>`}
function leagueCell(code){return `<div class="league-box">${crest(lg[code]||code,true)}<div class="league-name">${esc(lg[code]||code)}</div></div>`}
function table(rows){if(!rows.length)return '<div class="empty">No hay partidos para estos filtros.</div>';return '<div class="tablewrap"><table class="fixture-table"><thead><tr><th>Fecha</th><th>Liga</th><th>Partido</th>'+Object.entries(ev).map(([e,t])=>`<th class="num">${esc(e==='qpa'?'QPA':e==='rem'?'REM':t)}</th>`).join('')+'<th>Acción</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${esc(fmtDay(r.dia))}<br><small style="color:#b7d6c0">${esc(r.hora)}${r.hora_confirmada?' PE':''}</small></td><td>${leagueCell(r.competition)}</td><td class="match-cell"><div class="matchline">${teamBlock(r.home,r.lambda_h)} <span class="vs">VS</span> ${teamBlock(r.away,r.lambda_a)}</div></td>${Object.keys(ev).map(e=>`<td class="num">${e===event()?'<span class="highlight">':''}${pct(r[e])}${e===event()?'</span><div class="bar"><i style="width:'+100*r[e]+'%"></i></div>':''}</td>`).join('')}<td><button class="btn-mini" data-id="${esc(r.competition+'|'+r.fixture_id)}">Ver análisis</button></td></tr>`).join('')+'</tbody></table></div>'}
function render(){
 const rows=filt(),e=event();
 updateClubStatus(rows);
 document.querySelectorAll('#leagueTabs button').forEach(b=>b.classList.toggle('active',b.dataset.league===$('league').value));
 document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
 if(view==='fixture'){
   $('content').innerHTML=section('Fixture de la próxima ventana',table([...rows].sort((a,b)=>a.dia.localeCompare(b.dia)||a.hora.localeCompare(b.hora))),'Goles proyectados de KARUBET junto al nombre de cada equipo.');
 } else if(view==='rank'){
   let groups=Object.keys(lg).filter(l=>rows.some(r=>r.competition===l));
   $('content').innerHTML=section(`Top ${k()} general · ${ev[e]}`,table(sorted(rows).slice(0,k())),`Modelo activo: ${modelLabel($('model').value)}`) + groups.map(l=>section(lg[l]+' · Top '+k(),table(sorted(rows.filter(r=>r.competition===l)).slice(0,k())))).join('');
 } else if(view==='day'){
   let days=[...new Set(rows.map(r=>r.dia))].sort();
   $('content').innerHTML=section('Cuadro general por día',days.length?'<div class="tablewrap"><table><thead><tr><th>Día</th><th>Partidos</th><th>Media</th><th>Mayor probabilidad</th><th>Menor probabilidad</th></tr></thead><tbody>'+days.map(d=>{let a=sorted(rows.filter(r=>r.dia===d)),hi=a[0],lo=a.at(-1);return `<tr><td>${esc(fmtDay(d))}</td><td>${a.length}</td><td class="num">${pct(a.reduce((s,r)=>s+r[e],0)/a.length)}</td><td>${dayTeamName(hi.home,hi.lambda_h)} <span class="vs">vs</span> ${dayTeamName(hi.away,hi.lambda_a)} <span class="high">${pct(hi[e])}</span></td><td>${dayTeamName(lo.home,lo.lambda_h)} <span class="vs">vs</span> ${dayTeamName(lo.away,lo.lambda_a)} <span class="low">${pct(lo[e])}</span></td></tr>`}).join('')+'</tbody></table></div>':'<div class="empty">Sin partidos</div>','Las mayores y menores probabilidades del día para el evento seleccionado.') + days.map(d=>{let a=sorted(rows.filter(r=>r.dia===d));return section(fmtDay(d),`<h3 class="high">Top ${Math.min(k(),a.length)} del día</h3>${table(a.slice(0,k()))}<h3 class="low" style="margin-top:22px">Bottom ${Math.min(k(),a.length)} del día</h3>${table(a.slice(-k()).reverse())}`)}).join('');
 } else {
   let a=rows.find(r=>r.competition+'|'+r.fixture_id===selected)||rows[0];
   if(!a){$('content').innerHTML=section('Análisis','<div class="empty">Sin partidos</div>');return}
   selected=a.competition+'|'+a.fixture_id;
   let info=[['Goles a favor','home_gf_ew10','away_gf_ew10'],['Goles en contra','home_ga_ew10','away_ga_ew10'],['xG relativo','home_xgr_ew10','away_xgr_ew10'],['xGA relativo','home_xgar_ew10','away_xgar_ew10'],['Puntos por partido','home_pts_ew10','away_pts_ew10'],['Goles a favor · últimos 5','h_gf_5','a_gf_5'],['Goles en contra · últimos 5','h_ga_5','a_ga_5'],['xG relativo · últimos 5','h_xgr_5','a_xgr_5'],['xGA relativo · últimos 5','h_xgar_5','a_xgar_5'],['Elo','h_elo','a_elo'],['Partidos usados','h_n','a_n'],['Descanso (días)','h_rest','a_rest'],['Proyección de goles','lambda_h','lambda_a']];
   $('content').innerHTML=section('Análisis individual',`<label>Elegir partido<select id="matchselect">${rows.map(r=>`<option value="${esc(r.competition+'|'+r.fixture_id)}" ${selected===r.competition+'|'+r.fixture_id?'selected':''}>${esc(r.dia+' | '+r.home+' vs '+r.away)}</option>`).join('')}</select></label>
   <div class="big-match"><div class="big-team">${crest(a.home)}<div><div style="font-size:22px;font-weight:800">${teamNamePred(a.home,a.lambda_h)}</div><div style="color:var(--muted)">${esc(lg[a.competition])}</div></div></div><div class="big-vs">VS</div><div class="big-team">${crest(a.away)}<div><div style="font-size:22px;font-weight:800">${teamNamePred(a.away,a.lambda_a)}</div><div style="color:var(--muted)">${esc(fmtDay(a.dia))} · ${esc(a.hora)}${a.hora_confirmada?' PE':''}</div></div></div></div>
   ${projectedGoals(a)}
   ${editorialPick(a)}
   <details class="analysis-details"><summary>Ver análisis completo</summary>${analysisText(a,rows,e)}</details>
   <div class="prob-grid">${Object.keys(ev).map(q=>`<div class="goal-card ${q===e?'selected':''}"><small>${ev[q]}</small><strong>${pct(a[q])}</strong><span style="color:var(--muted)">Cuota teórica: ${num(a['fair_'+q])}</span></div>`).join('')}</div>
   ${recentCards(a)}<details><summary>Ver estadísticas y comparación de enfoques</summary><div class="grid2"><div><h3 style="margin:0 0 10px">Factores observados</h3><div class="tablewrap"><table><thead><tr><th>Variable</th><th>${esc(a.home)}</th><th>${esc(a.away)}</th></tr></thead><tbody>${info.map(([t,h,v])=>`<tr><td>${esc(t)}</td><td class="num">${num(a[h],h.includes('elo')||h.endsWith('_n')||h.endsWith('_rest')?0:2)}</td><td class="num">${num(a[v],v.includes('elo')||v.endsWith('_n')||v.endsWith('_rest')?0:2)}</td></tr>`).join('')}</tbody></table></div></div>
   <div class="comparison"><h3 style="margin:0 0 10px">Comparación de pronósticos</h3><div class="tablewrap"><table><thead><tr><th>Evento</th><th class="num">Referencia</th><th class="num">Forma actual</th><th class="num">Forma + historial</th></tr></thead><tbody>${Object.keys(ev).map(q=>`<tr><td>${ev[q]}</td><td class="num">${pct(a['original_'+q])}</td><td class="num">${pct(a['ewma_'+q])}</td><td class="num">${pct(a['h2h_'+q])}</td></tr>`).join('')}</tbody></table></div></div></div></details>`, 'Vista completa del encuentro seleccionado.');
   $('content').innerHTML += h2hSection(a);
   $('matchselect').onchange=ev=>{selected=ev.target.value;render()};
 }
}
function recentCards(a){function card(side,name){const f=a[side+'_recent']||[];return `<div class="form-card"><div class="matchline">${crest(name)}<b>${esc(name)}</b></div><small>Últimos ${f.length} partidos de liga disponibles · más reciente primero</small><div class="form-strip">${f.map(m=>`<span class="form-chip ${m.result}" title="${esc(m.opponent+' '+m.score)}">${({W:'G',D:'E',L:'P'})[m.result]}</span>`).join('')}</div><ul>${f.map(m=>`<li><span>${esc(m.opponent)} <small>${m.venue==='H'?'(L)':'(V)'}</small></span><b>${esc(m.score)}</b></li>`).join('')}</ul>${f.length?'':'<small>Sin resultados recientes disponibles.</small>'}</div>`}return `<h3 class="detail-title">Así llegan los equipos</h3><div class="analysis-grid">${card('home',a.home)}${card('away',a.away)}</div>`}
function analysisText(a,rows,e){const v=x=>typeof x==='number'&&Number.isFinite(x);const f=x=>v(x)?num(x,2):'sin dato';const mean=x=>x.length?x.reduce((s,r)=>s+r[e],0)/x.length:null;const same=data.filter(r=>r.competition===a.competition&&r.dia>=$('start').value&&r.dia<=$('end').value);const order=[...same].sort((x,y)=>y[e]-x[e]);const rank=order.findIndex(r=>r===a)+1;const avg=mean(same);const d=avg==null?0:a[e]-avg;const relative=same.length<3?'muestra pequeña; sin clasificación relativa sólida':rank<=Math.ceil(same.length/4)&&d>0?'entre los perfiles más altos de su liga':rank>Math.floor(same.length*0.75)&&d<0?'entre los perfiles más bajos de su liga':'en la zona intermedia de su liga';function team(side,short,name){const gf=a[short+'_gf_5'],ga=a[short+'_ga_5'],pp=a[side+'_pts_ew10'];const ff=a[side+'_recent']||[];const tally=ff.reduce((s,m)=>(s[m.result]++,s),{W:0,D:0,L:0});const xg=ff.filter(m=>v(m.xg));const xga=ff.filter(m=>v(m.xga));const xa=xg.length?xg.reduce((s,m)=>s+m.xg,0)/xg.length:null;const xb=xga.length?xga.reduce((s,m)=>s+m.xga,0)/xga.length:null;let note=ff.length?` registra ${tally.W} ${tally.W===1?'victoria':'victorias'}, ${tally.D} ${tally.D===1?'empate':'empates'} y ${tally.L} ${tally.L===1?'derrota':'derrotas'} en sus últimos ${ff.length} encuentros de liga.`:' no tiene resultados recientes detallados disponibles.';note+=v(gf)&&v(ga)?` En su ventana reciente promedia ${f(gf)} goles a favor y ${f(ga)} en contra por partido.`:'';note+=xa!=null&&xb!=null?` Su xG observado es ${f(xa)} y su xGA ${f(xb)} por encuentro (${xg.length}/${xga.length} partidos con datos, respectivamente).`:'';return `<p><b>${esc(name)}</b>${note}${v(pp)?` Su ritmo de puntos ponderado por forma es ${f(pp)} por partido.`:''}</p>`}let goals='';if(v(a.lambda_h)&&v(a.lambda_a)){const diff=a.lambda_h-a.lambda_a;const desc=Math.abs(diff)<.30?'El reparto proyectado de goles es relativamente equilibrado.':`La proyección favorece en volumen goleador a ${esc(diff>0?a.home:a.away)}.`;goals=`<p><b>Goles pronosticados (Poisson):</b> ${esc(a.home)} ${f(a.lambda_h)} · ${esc(a.away)} ${f(a.lambda_a)}. Total estimado: ${f(a.lambda_h+a.lambda_a)} goles. ${desc} Es una estimación del encuentro, no un marcador exacto.</p>`}const hist=Array.isArray(a.h2h_matches)?a.h2h_matches:[];const labeled=hist.filter(m=>m[e]!==null&&m[e]!==undefined);const hits=labeled.filter(m=>m[e]===1||m[e]===true).length;const h2h=hist.length?`Hay ${hist.length} cruces oficiales disponibles. ${labeled.length?`${hits} de ${labeled.length} con etiqueta conocida registraron ${ev[e]}.`:'No hay etiquetas suficientes para este evento.'} El último fue el ${esc(hist[0].date)} (${esc(hist[0].home)} ${esc(hist[0].score)} ${esc(hist[0].away)}).`:'No constan cruces directos en la base disponible.';const comparison=avg!=null?` · media de los ${same.length} partidos de su liga en estas fechas: ${pct(avg)}${same.length>1?` · puesto ${rank}/${same.length}`:''}`:'';return `<article class="analysis-panel"><div class="eyebrow">Previa estadística · ${esc(lg[a.competition])}</div><h3>Lectura del partido</h3>${team('home','h',a.home)}${team('away','a',a.away)}${goals}<p><b>Antecedentes:</b> ${h2h}</p><p><b>Lectura KARUBET para ${ev[e]}:</b> <span class="signal">${pct(a[e])}</span>${comparison}. Se sitúa ${relative}. ${e==='pa'?'El escenario requiere que alguno de los dos equipos consiga una ventaja de al menos dos goles.':e==='qpa'?'El escenario exige que el equipo que sufra esa ventaja reduzca después la diferencia a un gol.':e==='dpa'?'El empate debe producirse después de una ventaja de dos goles; un partido equilibrado por sí solo no basta.':'La remontada exige que el equipo que sufrió el primer PA termine ganando.'} Las probabilidades de los escenarios son PA ${pct(a.pa)}, QPA ${pct(a.qpa)}, DPA ${pct(a.dpa)} y remontada ${pct(a.rem)}.</p><p class="data-note">Comentario generado automáticamente a partir de las estadísticas disponibles. Las probabilidades son prematch; una posición alta en el ranking no implica que el evento sea probable en términos absolutos. No incluye noticias ni alineaciones en directo.</p></article>`}

function h2hTeam(name,m){
  let cls=m.rem_team===name?'h2h-rem-team':m.pa_team===name?'h2h-pa-team':'';
  return cls?`<strong class="${cls}">${esc(name)}</strong>`:esc(name)
}
function h2hMoment(m,e){
  if(m[e]==null)return '—';
  if(m[e]!==1)return '<span class="event-no">No</span>';
  const moment=m.minutes?.[e];
  return `<span class="event-yes">Sí</span>${moment!=null?`<span class="event-minute ${e}" title="Minuto en que ocurre ${ev[e]}">${esc(moment)}′</span>`:'<span class="minute-missing" title="Cronología no disponible o no verificable">s/min</span>'}`;
}
function goalTrail(m){
  if(m.pa!==1||!Array.isArray(m.goal_sequence)||!m.goal_sequence.length)return '';
  let h=0,a=0;
  const steps=m.goal_sequence.map(g=>{
    if(g[1]==='h')h++;else a++;
    const name=g[1]==='h'?m.home:m.away;
    return `<span class="goal-tick"><b>${esc(g[0])}′</b> ${esc(name)} <b>${h}–${a}</b></span>`
  }).join('');
  return `<details class="goal-details"><summary>Ver secuencia de goles</summary><div class="goal-trail">${steps}</div></details>`
}
function h2hSection(a){
 const matches=Array.isArray(a.h2h_matches)?a.h2h_matches:[];
 const active=matches.filter(m=>m.pa===1).length;
 const timed=matches.filter(m=>m.pa===1&&m.minutes?.pa).length;
 const legend=`<div class="h2h-intro"><span class="h2h-legend"><i style="background:#ffd166"></i> <b style="color:#ffe29a">Equipo que consiguió PA</b></span><span class="h2h-legend"><i style="background:#6cf0b0"></i> <b style="color:#8ffbc7">Equipo que remontó y ganó</b></span><span>${active} cruces con PA · ${timed} con minutos de PA verificados</span></div>`;
 const cols='<thead><tr><th>Fecha</th><th>Liga</th><th>Partido</th><th>Marcador</th><th>Peso</th><th>PA</th><th>QPA</th><th>DPA</th><th>REM</th></tr></thead>';
 const body=matches.map(m=>`<tr><td>${esc(m.date)}</td><td>${esc(lg[m.competition]||m.competition)}</td><td class="h2h-matches">${h2hTeam(m.home,m)} <span class="vs">–</span> ${h2hTeam(m.away,m)}${goalTrail(m)}</td><td class="score-col">${esc(m.score)}</td><td class="num">${pct(m.weight)}</td>${Object.keys(ev).map(e=>`<td class="event-cell">${h2hMoment(m,e)}</td>`).join('')}</tr>`).join('');
 const tbl=matches.length?`<div class="tablewrap"><table class="h2h-table">${cols}<tbody>${body}</tbody></table></div>`:'<div class="empty">No hay enfrentamientos directos oficiales disponibles en la base.</div>';
 const note=`<p class="h2h-subnote">El minuto PA corresponde al gol que produjo por primera vez la ventaja de dos tantos; QPA, al gol que redujo esa ventaja a uno; DPA, al empate; REM, al último gol que puso por delante al equipo que acabó ganando. <b>«s/min» significa minuto no verificado</b>. Se muestran solo cronologías consistentes con el marcador final y las etiquetas. Los H2H son encuentros disponibles en nuestras bases; no incluyen todas las copas.</p>`;
 return section('Antecedentes entre ambos equipos',legend+tbl+note,`Últimos ${matches.length} cruces oficiales disponibles · pesos más altos en partidos recientes`);
}
$('nav').onclick=e=>{let b=e.target.closest('[data-view]');if(b){view=b.dataset.view;render()}};
$('content').onclick=e=>{let b=e.target.closest('[data-id]');if(b){selected=b.dataset.id;view='detail';render();window.scrollTo({top:document.getElementById('content').offsetTop-10,behavior:'smooth'})}};
for(const id of ['start','end','league','event','k','model'])$(id).onchange=render;
$('week').onclick=week; $('season').onclick=entireSeason;
week();
  })();
}

/* Vista pública de solo lectura; nunca se entrega la clave de Supabase al navegador. */

function classicDateParts(value) {
  const d = new Date(value);
  if (!Number.isFinite(d.getTime())) return {date:"",hour:""};
  const items = new Intl.DateTimeFormat("en-GB",{
    timeZone:"America/Lima",year:"numeric",month:"2-digit",day:"2-digit",
    hour:"2-digit",minute:"2-digit",hourCycle:"h23"
  }).formatToParts(d);
  const x = Object.fromEntries(items.map(y=>[y.type,y.value]));
  return {date:x.year+"-"+x.month+"-"+x.day, hour:x.hour+":"+x.minute};
}

async function classicFetchFixtures(offset) {
  const u = new URL("/api/data", location.origin);
  for(const [k,v] of Object.entries({kind:"fixtures",days:"210",limit:"250",offset:String(offset)}))
    u.searchParams.set(k,v);
  const res = await fetch(u.pathname+u.search,{cache:"no-store"});
  if(!res.ok){
    let body={};
    try{body=await res.json();}catch{}
    throw new Error(body.message||"Supabase no está disponible (HTTP "+res.status+").");
  }
  return res.json();
}
/* Contexto exacto exportado por el notebook original.
   No reemplazar probabilidades recalculadas ni reconstruir cronologías. */
async function classicFetchContexts(ids){
  const u=new URL("/api/data",location.origin);
  u.searchParams.set("kind","contexts");
  u.searchParams.set("ids",ids.join(","));
  const res=await fetch(u.pathname+u.search,{cache:"no-store"});
  if(!res.ok){
    let error={};
    try{error=await res.json();}catch{}
    throw new Error(error.message||"No se pudo recuperar el historial original (HTTP "+res.status+").");
  }
  const value=await res.json();
  if(!Array.isArray(value.items))throw new Error("Respuesta de contexto original inválida.");
  return value.items;
}
async function loadOriginalContexts(rows,status){
  const groups=[];
  for(let i=0;i<rows.length;i+=75)groups.push(rows.slice(i,i+75).map(r=>r.fixture_id));
  const result=new Map();
  let done=0;
  // Concurrencia limitada: respeta Supabase y Vercel.
  for(let i=0;i<groups.length;i+=4){
    const pages=await Promise.all(groups.slice(i,i+4).map(ids=>classicFetchContexts(ids)));
    for(const entries of pages){
      for(const entry of entries){
        if(!entry||!Number.isSafeInteger(Number(entry.fixture_id)))continue;
        result.set(Number(entry.fixture_id),entry);
      }
    }
    done+=pages.length;
    status.textContent="Recuperando forma y H2H originales: "+done+"/"+groups.length+" tandas...";
  }
  const protectedKeys=new Set([
    "fixture_id","home","away","competition","dia","hora","hora_confirmada",
    "lambda_h","lambda_a","ewma_pa","ewma_qpa","ewma_dpa","ewma_rem",
    "h2h_pa","h2h_qpa","h2h_dpa","h2h_rem",
    "original_pa","original_qpa","original_dpa","original_rem"
  ]);
  let restored=0,h2h=0,latestOriginal=null;
  for(const row of rows){
    const record=result.get(Number(row.fixture_id));
    if(!record || !record.context)continue;
    const c=record.context;
    // Unir por ID + nombre exacto de ambos equipos y liga: no mezclar partidos.
    if(c.home!==row.home || c.away!==row.away || c.competition!==row.competition)continue;
    for(const [key,value] of Object.entries(c)){
      if(!protectedKeys.has(key))row[key]=value;
    }
    restored++;
    if(Array.isArray(row.h2h_matches)&&row.h2h_matches.length)h2h++;
    if(record.source_snapshot_date && (!latestOriginal||record.source_snapshot_date>latestOriginal))
      latestOriginal=record.source_snapshot_date;
  }
  return {restored,h2h,sourceDate:latestOriginal};
}
function classicViewRow(f){
  const p=f.model.probabilities||{},m=f.model.metrics||{};
  const dt=classicDateParts(f.kickoff_at);
  const row={
    fixture_id:f.fixture_id,competition:f.competition,
    home:f.home_team,away:f.away_team,dia:dt.date,hora:dt.hour,
    hora_confirmada:dt.hour!=="",
    lambda_h:m.lambda_home??null,lambda_a:m.lambda_away??null,
    h2h_count:m.h2h_count??0,h2h_evidence:m.h2h_evidence??null,
    home_recent:[],away_recent:[],h2h_matches:[],
    original_pa:p.original_pa??p.pa??null,
    original_qpa:p.original_qpa??p.qpa??null,
    original_dpa:p.original_dpa??p.dpa??null,
    original_rem:p.original_rem??p.rem??null
  };
  for(const model of ["ewma","h2h"]){
    for(const ev of ["pa","qpa","dpa","rem"])
      row[model+"_"+ev]=p[model]?.[ev]??null;
  }
  return row;
}
async function loadClassicStandalone(){
   const status=document.getElementById("classicLiveStatus");
  const content=document.getElementById("content");
  status.textContent="Conectando con Supabase...";
  content.textContent="Consultando probabilidades originales de KARUBET 6.3...";
  try{
    const fixtures=[];
    let offset=0,latest=null;
    for(let page=0;page<12;page++){
      const data=await classicFetchFixtures(offset);
      if(!Array.isArray(data.items))throw new Error("Formato de fixture inválido");
      fixtures.push(...data.items);
      offset+=data.items.length;
      status.textContent="Leyendo fixtures: "+fixtures.length+"...";
      if(!data.page_full||!data.items.length)break;
    }
    const rows=[];
    for(const f of fixtures){
      if(!f.model || !f.kickoff_at)continue;
      rows.push(classicViewRow(f));
      if(f.model.generated_at && (!latest||f.model.generated_at>latest))
        latest=f.model.generated_at;
    }
    const restored=await loadOriginalContexts(rows,status);
    if(rows.length && restored.restored<rows.length*0.8){
      throw new Error("Solo se restauró "+restored.restored+"/"+rows.length+
        " fichas originales. Verifica las referencias del fixture y los datos de Supabase.");
    }
    const today=classicDateParts(new Date().toISOString()).date;
    const updated=latest?new Intl.DateTimeFormat("es-PE",{
      timeZone:"America/Lima",dateStyle:"medium",timeStyle:"short"
    }).format(new Date(latest)):"sin recálculo";
    // El motor visual clásico se conserva íntegro; solo cambia el origen del dataset.
    startClassic({
      rows,logos:{},league_logos:{},
      meta:{today,asof:updated,
            source_date:"Modelo en Supabase · contexto histórico original "+(restored.sourceDate||"2026-11-22"),
            fresh:Boolean(latest)}
    });
    status.textContent="Supabase · "+rows.length+" predicciones · "+restored.restored+
      " contextos históricos · "+restored.h2h+" con H2H · corte "+(restored.sourceDate||"2026-11-22")+
      " · modelo "+updated;
    status.classList.add("ready");
  }catch(error){
    status.textContent="No se pudieron cargar las probabilidades";
    content.replaceChildren();
    const p=document.createElement("p");
    p.className="classic-error";
    p.textContent=error.message||"Error de conexión";
    const a=document.createElement("a");
    a.href="/";
    a.textContent="Volver a KARUBET";
    content.append(p,a);
  }
}
document.addEventListener("DOMContentLoaded",()=>{
  document.querySelectorAll('img[data-karubet-logo]').forEach(img=>{
    if(window.KARUBET_ORIGINAL_LOGO) img.src=window.KARUBET_ORIGINAL_LOGO;
  });
  document.getElementById("classicLogout")?.addEventListener("click",()=>location.assign("/?tab=market"));
  document.getElementById("classicRefresh")?.addEventListener("click",()=>location.reload());
  document.addEventListener("error",event=>{
    if(event.target instanceof HTMLImageElement && event.target.closest(".crest")) event.target.remove();
  },true);
  loadClassicStandalone();
});
