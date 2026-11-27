/* KARUBET 7.0. Read-only UI. Nunca almacena la clave privada de Supabase. */
"use strict";

const $ = id => document.getElementById(id);
const state = {
  token: sessionStorage.getItem("karubet_access") || "",
  fixtures: [], fixtureOffset: 0, fixtureDone: false, selectedFixture: null,
  markets: [], selectedMarket: null, history: [], side: "L", rolling: 6,
  lastModelDate: null
};

const LEAGUES = {
  "epl": "Premier League", "la-liga": "La Liga", "serie-a": "Serie A",
  "bundesliga": "Bundesliga", "ligue-1": "Ligue 1", "ucl": "Champions League",
  "25": "Ligue 1", "74": "Serie A", "24": "Premier League",
  "38": "La Liga", "125": "Champions League"
};

function escapeHTML(x) {
  return String(x ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);
}
function num(x, n=2) {
  const v = Number(x);
  return x === null || x === undefined || !Number.isFinite(v) ? "—" : v.toFixed(n);
}
function percent(x) { return x === null || x === undefined ? "—" : num(100 * Number(x), 1) + "%"; }
function when(x, time=true) {
  if (!x) return "Por definir";
  const d = new Date(x);
  if (!Number.isFinite(d.getTime())) return "Por definir";
  return new Intl.DateTimeFormat("es-PE", {
    timeZone: "America/Lima", day: "2-digit", month: "short",
    ...(time ? {hour: "2-digit", minute: "2-digit"} : {}),
    year: "numeric"
  }).format(d);
}
function setStatus(text, ok=false) {
  $("databaseState").innerHTML = '<span class="dot ' + (ok ? "ok" : "bad") + '"></span> ' + escapeHTML(text);
}
async function request(kind, args={}) {
  const query = new URLSearchParams(Object.assign({kind}, args));
  let response;
  try {
    response = await fetch("/api/data?" + query.toString(), {
      method: "GET",
      cache: "no-store",
      headers: {"Authorization": "Bearer " + state.token}
    });
  } catch {
    throw new Error("No se pudo contactar al servidor de KARUBET.");
  }
  let body = {};
  try { body = await response.json(); } catch {}
  if (!response.ok) {
    const err = new Error(body.message || body.error || "Error de conexión");
    err.status = response.status;
    throw err;
  }
  return body;
}
function toggleAccess(yes) {
  $("workspace").hidden = !yes;
  $("loginPanel").hidden = yes;
  $("logout").hidden = !yes;
  if (yes) setStatus("Supabase conectado", true);
}
async function login() {
  const token = $("accessToken").value.trim();
  if (token.length < 20) {
    $("loginFeedback").textContent = "El código debe tener por lo menos 20 caracteres.";
    return;
  }
  state.token = token;
  $("loginFeedback").textContent = "Verificando el acceso privado...";
  try {
    await loadFixtures(true);
    sessionStorage.setItem("karubet_access", state.token);
    toggleAccess(true);
    loadMarkets();
  } catch (e) {
    $("loginFeedback").textContent = e.message || "No se pudo conectar.";
    setStatus("Sin conexión", false);
    state.token = "";
    sessionStorage.removeItem("karubet_access");
  }
}
function logout() {
  state.token = "";
  sessionStorage.removeItem("karubet_access");
  $("accessToken").value = "";
  toggleAccess(false);
  setStatus("Acceso privado", false);
}
function setTab(tab) {
  const market = tab === "market";
  $("probPage").hidden = market;
  $("marketPage").hidden = !market;
  $("tabProbs").classList.toggle("active", !market);
  $("tabMarket").classList.toggle("active", market);
  $("tabProbs").setAttribute("aria-selected", String(!market));
  $("tabMarket").setAttribute("aria-selected", String(market));
  if (market && state.selectedFixture) syncLinkedMarket();
}
/* La unión es intencionalmente estricta: nunca emparejar solo por nombre. */
async function syncLinkedMarket() {
  const fixture = state.selectedFixture;
  if (!fixture || !state.markets.length) return;
  try {
    const data = await request("linked", {fixture_id: fixture.fixture_id});
    if (fixture !== state.selectedFixture || !data.linked) return;
    const match = state.markets.find(m => (data.items || []).some(link =>
      String(link.odds_league_code) === String(m.league_code) &&
      link.odds_home_team === m.home_team &&
      link.odds_away_team === m.away_team &&
      m.kickoff_at && Math.abs(
        new Date(m.kickoff_at).getTime() - new Date(fixture.kickoff_at).getTime()
      ) <= 3 * 60 * 60 * 1000
    ));
    if (match) selectMarket(match);
  } catch {
    // Si la vinculación no está disponible, conservamos la selección manual.
  }
}
async function loadFixtures(reset=false) {
  if (reset) {
    state.fixtures = [];
    state.fixtureOffset = 0;
    state.fixtureDone = false;
    state.selectedFixture = null;
    $("matchList").innerHTML = '<div class="empty">Consultando probabilidades originales de Supabase...</div>';
  }
  if (state.fixtureDone) return;
  const days = Number($("daysSelect").value);
  const data = await request("fixtures", {days, limit: 250, offset: state.fixtureOffset});
  state.fixtures.push(...(data.items || []));
  state.fixtureOffset += (data.items || []).length;
  state.fixtureDone = !(data.page_full);
  $("kpiMatches").textContent = state.fixtures.length.toLocaleString("es-PE") +
    (state.fixtureDone ? "" : "+");
  $("kpiPredicted").textContent = state.fixtures.filter(f => Boolean(f.model)).length.toLocaleString("es-PE") +
    (state.fixtureDone ? "" : "+");
  const latest = state.fixtures.reduce((a,f) => {
    const d = f.model?.generated_at;
    return d && (!a || d > a) ? d : a;
  }, state.lastModelDate);
  state.lastModelDate = latest;
  $("kpiUpdated").textContent = latest ? when(latest) : "—";
  $("freshStatus").textContent = "Última consulta " + when(data.asof);
  $("loadMore").hidden = state.fixtureDone;
  renderFixtures();
  if (!state.selectedFixture && state.fixtures.length) {
    selectFixture(state.fixtures.find(f => f.model) || state.fixtures[0]);
  }
}
function filteredFixtures() {
  const query = $("matchSearch").value.toLocaleLowerCase("es").trim();
  const league = $("leagueSelect").value;
  return state.fixtures.filter(f => (!league || f.competition === league)
      && (!query || (f.home_team + " " + f.away_team).toLocaleLowerCase("es").includes(query)));
}
function renderFixtures() {
  const list = $("matchList");
  const items = filteredFixtures();
  $("fixtureCount").textContent = items.length + " visibles" + (state.fixtureDone ? "" : " · más páginas");
  list.replaceChildren();
  if (!items.length) {
    list.innerHTML = '<div class="empty">No hay encuentros con estos filtros. Prueba otra liga o amplía la fecha.</div>';
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const f of items) {
    const btn = document.createElement("button");
    btn.className = "match" + (state.selectedFixture?.fixture_id === f.fixture_id ? " active" : "");
    btn.type = "button";
    btn.innerHTML = '<span><span class="match-title">' + escapeHTML(f.home_team) +
      ' <span style="color:#ecca70">vs</span> ' + escapeHTML(f.away_team) +
      '</span><span class="match-meta">' + escapeHTML(LEAGUES[f.competition] || f.competition) +
      ' · ' + escapeHTML(when(f.kickoff_at)) + '</span></span><span class="match-badge">' +
      (f.model ? 'PA ' + percent(f.model.probabilities?.pa) : "SIN MODELO") + "</span>";
    btn.addEventListener("click", () => selectFixture(f));
    fragment.append(btn);
  }
  list.append(fragment);
}
function probCard(label, value, highlighted=false) {
  const v = Number(value);
  return '<div class="prob-card ' + (highlighted ? "primary-prob" : "") +
    '"><small>' + escapeHTML(label) + '</small><strong>' +
    percent(value) + '</strong><div class="bar"><i style="width:' +
    (Number.isFinite(v) ? Math.min(100, Math.max(0, v*100)) : 0) + '%"></i></div></div>';
}
function selectFixture(f) {
  state.selectedFixture = f;
  renderFixtures();
  const model = f.model, p = model?.probabilities, m = model?.metrics;
  if (!model) {
    $("matchDetail").innerHTML = '<div class="detail-teams">' + escapeHTML(f.home_team) +
      ' vs ' + escapeHTML(f.away_team) + '</div><p class="note">Este fixture todavía no tiene una salida del motor KARUBET 6.3. No se mostrarán probabilidades artificiales.</p>';
    return;
  }
  const families = [
    ["EWMA", p.ewma], ["H2H", p.h2h], ["Poisson", p.poisson], ["Elastic", p.elastic]
  ];
  const familyRows = families.map(item => '<tr><td>' + escapeHTML(item[0]) +
    '</td><td>' + percent(item[1]?.pa) + '</td><td>' + percent(item[1]?.qpa) +
    '</td><td>' + percent(item[1]?.dpa) + '</td><td>' + percent(item[1]?.rem) + '</td></tr>').join("");
  $("matchDetail").innerHTML =
    '<div class="details-top"><div><p class="eyebrow">' + escapeHTML(LEAGUES[f.competition] || f.competition) +
    ' · KARUBET 6.3 ORIGINAL</p><div class="detail-teams">' + escapeHTML(f.home_team) +
    ' <em>VS</em> ' + escapeHTML(f.away_team) +
    '</div><span class="smallmuted">' + escapeHTML(when(f.kickoff_at)) +
    '</span></div><span class="tag">ID ' + escapeHTML(f.fixture_id) + '</span></div>' +
    '<p class="model-caption">PROBABILIDADES DEL MODELO ORIGINAL</p>' +
    '<div class="prob-grid">' + probCard("PA", p.pa, true) +
    probCard("QUASI PA", p.qpa) + probCard("DOBLE PA", p.dpa) +
    probCard("REMONTADA", p.rem) + '</div>' +
    '<div class="four-stats"><div><small>GOLES ESPERADOS LOCAL</small><strong>' + num(m?.lambda_home) +
    '</strong></div><div><small>GOLES ESPERADOS VISITA</small><strong>' + num(m?.lambda_away) +
    '</strong></div><div><small>ENFRENTAMIENTOS H2H</small><strong>' + escapeHTML(m?.h2h_count ?? "—") +
    '</strong></div><div><small>EVIDENCIA H2H</small><strong>' + num(m?.h2h_evidence) +
    '</strong></div></div><div class="components"><p class="model-caption">COMPONENTES DEL CÁLCULO</p>' +
    '<table><thead><tr><th>Componente</th><th>PA</th><th>Quasi</th><th>Doble</th><th>Rem.</th></tr></thead><tbody>' +
    familyRows + '</tbody></table></div>' +
    '<div class="note">Salida del motor original ' + escapeHTML(model.model_version) +
    ' · Calculada ' + escapeHTML(when(model.generated_at)) +
    '. Estos porcentajes corresponden a eventos KARUBET y NO son las probabilidades del mercado 1X2.</div>';
}
async function loadMarkets() {
  $("marketCount").textContent = "Consultando...";
  try {
    const data = await request("markets");
    state.markets = data.items || [];
    $("marketMatches").textContent = state.markets.length;
    $("marketCount").textContent = state.markets.length + " mercados";
    renderMarkets();
    if (!state.selectedMarket && state.markets.length) selectMarket(state.markets[0]);
  } catch (e) {
    $("marketCount").textContent = "No disponible";
    $("marketList").innerHTML = '<div class="empty">' + escapeHTML(e.message) + '</div>';
  }
}
function renderMarkets() {
  const container = $("marketList");
  container.replaceChildren();
  if (!state.markets.length) {
    container.innerHTML = '<div class="empty"><div class="empty-icon">⌁</div>Todavía no hay cuotas persistidas en Supabase. El recolector programado debe guardar al menos una captura válida antes de generar gráficas.</div>';
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const m of state.markets) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "match" + (m === state.selectedMarket ? " active" : "");
    btn.innerHTML = '<span><span class="match-title">' + escapeHTML(m.home_team) +
      ' <span style="color:#ecca70">vs</span> ' + escapeHTML(m.away_team) +
      '</span><span class="match-meta">' + escapeHTML(LEAGUES[m.league_code] || m.league_code) +
      ' · ' + escapeHTML(when(m.kickoff_at)) + '</span></span>' +
      '<span class="match-badge">' + num(m.odd_home) + ' / ' + num(m.odd_away) + '</span>';
    btn.addEventListener("click", () => selectMarket(m));
    fragment.append(btn);
  }
  container.append(fragment);
}
async function selectMarket(m) {
  state.selectedMarket = m;
  state.history = [];
  renderMarkets();
  $("marketName").textContent = m.home_team + " vs " + m.away_team;
  $("marketMeta").textContent = (LEAGUES[m.league_code] || m.league_code) + " · " + when(m.kickoff_at);
  $("capturedAt").textContent = "Capturada " + when(m.captured_at);
  $("quoteL").textContent = num(m.odd_home);
  $("quoteE").textContent = num(m.odd_draw);
  $("quoteV").textContent = num(m.odd_away);
  $("chartArea").innerHTML = '<div class="empty">Leyendo serie de tiempo...</div>';
  try {
    const data = await request("history", {
      league: m.league_code, home: m.home_team, away: m.away_team,
      kickoff: m.kickoff_at || ""
    });
    if (state.selectedMarket !== m) return;
    state.history = data.items || [];
    renderHistory();
  } catch (e) {
    $("chartArea").innerHTML = '<div class="empty">' + escapeHTML(e.message) + '</div>';
  }
}
function rolling(data, windowSize) {
  return data.map((_, i) => {
    const slice = data.slice(Math.max(0,i-windowSize+1),i+1);
    const avg = slice.reduce((sum,x)=>sum+x,0)/slice.length;
    const variance = slice.length > 1 ?
      slice.reduce((sum,x)=>sum+Math.pow(x-avg,2),0)/(slice.length-1) : 0;
    const sigma = Math.sqrt(variance);
    return {avg, sigma, top:avg+2*sigma, bottom:avg-2*sigma};
  });
}
function makePath(values, x, y) {
  return values.map((value,i) => (i ? "L" : "M") + x(i).toFixed(2) + "," + y(value).toFixed(2)).join(" ");
}
function renderHistory() {
  const keys = {L:"odd_home",E:"odd_draw",V:"odd_away"};
  const key = keys[state.side];
  const rows = state.history.filter(r => Number.isFinite(Number(r[key])) && Number(r[key]) > 1);
  if (!rows.length) {
    $("chartArea").innerHTML = '<div class="empty">Sin observaciones verificadas para este mercado.</div>';
    $("historyTable").textContent = "Sin datos.";
    return;
  }
  const values = rows.map(r => Number(r[key]));
  const stats = rolling(values, state.rolling);
  const latest = stats[stats.length-1];
  const min = Math.min(...values, ...stats.map(r=>r.bottom));
  const max = Math.max(...values, ...stats.map(r=>r.top));
  const margin = Math.max(.04, (max-min)*.09);
  const low = Math.max(1, min-margin), high = max+margin;
  const width=940,height=302,left=62,right=22,top=23,bottom=43;
  const x = i=>left+(values.length===1 ? (width-left-right)/2 : i*(width-left-right)/(values.length-1));
  const y = v=>top+(high-v)*(height-top-bottom)/(high-low);
  const grid = Array.from({length:5}, (_,i)=>{
    const val=low+(high-low)*i/4;
    return '<line x1="'+left+'" x2="'+(width-right)+'" y1="'+y(val)+'" y2="'+y(val)+'"/>'+
           '<text x="'+(left-9)+'" y="'+(y(val)+4)+'" text-anchor="end">'+num(val)+'</text>';
  }).join("");
  const price = makePath(values,x,y);
  const avg = makePath(stats.map(s=>s.avg),x,y);
  const band = stats.map((s,i)=>x(i).toFixed(2)+","+y(s.top).toFixed(2)).join(" ") + " " +
    [...stats].reverse().map((s,ind)=>x(stats.length-1-ind).toFixed(2)+","+y(s.bottom).toFixed(2)).join(" ");
  const first = escapeHTML(when(rows[0].captured_at));
  const last = escapeHTML(when(rows[rows.length-1].captured_at));
  $("chartArea").innerHTML = '<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="Evolución observada de las cuotas y su media móvil">' +
    grid + '<polygon points="'+band+'" fill="#77b7f9" opacity=".12"/>' +
    '<path d="'+avg+'" fill="none" stroke="#77b7f9" stroke-width="2.3" stroke-linejoin="round"/>' +
    '<path d="'+price+'" fill="none" stroke="#74e9a1" stroke-width="2.8" stroke-linejoin="round"/>' +
    '<circle cx="'+x(values.length-1)+'" cy="'+y(values[values.length-1])+'" r="4.3" fill="#74e9a1"/>' +
    '<text x="'+left+'" y="'+(height-12)+'">'+first+'</text>' +
    '<text x="'+(width-right)+'" y="'+(height-12)+'" text-anchor="end">'+last+'</text></svg>';
  const lastValue = values[values.length-1],prev = values.length>1 ? values[values.length-2] : null;
  const delta = prev === null ? null : 100*(lastValue/prev-1);
  const statsEl = $("rollingStats");
  statsEl.innerHTML = '<div><small>MÁXIMO OBSERVADO</small><strong>'+num(Math.max(...values))+'</strong></div>'+
    '<div><small>MÍNIMO OBSERVADO</small><strong>'+num(Math.min(...values))+'</strong></div>'+
    '<div><small>CAMBIO ÚLTIMA CAPTURA</small><strong>'+(delta===null?"—":(delta>=0?"+":"")+num(delta)+"%")+'</strong></div>'+
    '<div><small>VOLATILIDAD ROLLING</small><strong>'+num(latest.sigma,3)+'</strong></div>';
  $("decision").innerHTML = '<span class="signal-tag">NO ENTRAR · MODELO DE TIMING NO VALIDADO</span>' +
    '<p>Se observan '+values.length+' capturas. Media móvil de '+Math.min(values.length,state.rolling)+
    ' observaciones: '+num(latest.avg)+'. Desviación actual: '+
    (latest.sigma>0?num((lastValue-latest.avg)/latest.sigma,2)+" σ":"no calculable")+
    '. Estos indicadores son descriptivos: todavía no existe una predicción de máximo futuro validada. No comprar ni esperar por una señal estadística no demostrada.</p>';
  const recent = [...rows].reverse().slice(0,10);
  $("historyTable").innerHTML = '<table><thead><tr><th>Captura (Lima)</th><th>Local</th><th>Empate</th><th>Visita</th></tr></thead><tbody>' +
    recent.map(r=>'<tr><td>'+escapeHTML(when(r.captured_at))+'</td><td>'+num(r.odd_home)+
      '</td><td>'+num(r.odd_draw)+'</td><td>'+num(r.odd_away)+'</td></tr>').join("")+'</tbody></table>';
}
document.addEventListener("DOMContentLoaded", () => {
  $("loginForm").addEventListener("submit", event=>{event.preventDefault();login();});
  $("logout").addEventListener("click",logout);
  $("tabProbs").addEventListener("click",()=>setTab("probs"));
  $("tabMarket").addEventListener("click",()=>setTab("market"));
  $("refreshFixtures").addEventListener("click",()=>loadFixtures(true).catch(e=>{setStatus("Error de lectura",false);alert(e.message);}));
  $("refreshMarkets").addEventListener("click",()=>loadMarkets());
  $("loadMore").addEventListener("click",()=>loadFixtures(false).catch(e=>{alert(e.message);}));
  $("daysSelect").addEventListener("change",()=>loadFixtures(true).catch(e=>alert(e.message)));
  $("matchSearch").addEventListener("input",renderFixtures);
  $("leagueSelect").addEventListener("change",renderFixtures);
  document.querySelectorAll(".price[data-side]").forEach(b=>b.addEventListener("click",()=>{
    state.side=b.dataset.side;
    document.querySelectorAll(".price[data-side]").forEach(c=>c.classList.toggle("active",c===b));
    renderHistory();
  }));
  document.querySelectorAll("#rollingGroup button").forEach(b=>b.addEventListener("click",()=>{
    state.rolling=Number(b.dataset.roll);
    document.querySelectorAll("#rollingGroup button").forEach(c=>c.classList.toggle("active",c===b));
    renderHistory();
  }));
  if (state.token) {
    loadFixtures(true).then(()=>{
      toggleAccess(true);
      loadMarkets();
    }).catch(()=>{
      state.token="";
      sessionStorage.removeItem("karubet_access");
      toggleAccess(false);
    });
  }
});
