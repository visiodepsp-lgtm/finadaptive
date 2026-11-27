# Extractor visual original del notebook KARUBET.
# Se ejecuta dentro del navegador Playwright sobre la página pública.
# 3 · Lectura por POSICIÓN VISUAL del listado de cuotas 1X2 (no abre cada partido)
# No depende de etiquetas internas PA/SC ni de una clase CSS concreta.
EXTRACT_1X2_JS = r"""
({teamNames}) => {
  const norm = s => String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();
  const known = new Map();
  for (const n of teamNames||[]) known.set(norm(n), String(n));
  const rect = el => {
    try {const r=el.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};} catch {return null;}
  };
  const visible = el => {
    const r=rect(el); if (!r || r.w<2 || r.h<4) return false;
    if (r.x>window.innerWidth+300 || r.y>window.innerHeight+900 || r.x+r.w<0 || r.y+r.h<-300) return false;
    const s=getComputedStyle(el);
    return s.display!=='none' && s.visibility!=='hidden' && Number(s.opacity)!==0;
  };
  const nodes=[...document.querySelectorAll('body *')].slice(0,25000);
  const teams=[], prices=[];
  const seenT=new Set(),seenP=new Set();
  for(const el of nodes){
    if(!visible(el)) continue;
    const r=rect(el);
    if(r.w>520 || r.h>120) continue;  // sólo texto breve/etiquetas, no tarjetas enteras
    const txt=(el.innerText||el.textContent||'').trim();
    if(!txt || txt.length>65)continue;
    const n=norm(txt);
    const canonical=known.get(n);
    if(canonical){
      // Mantener el elemento más pequeño cuando varios padres repiten el mismo nombre.
      const area=r.w*r.h, key=n+'@'+Math.round(r.x/4)+'@'+Math.round(r.y/4);
      if(!seenT.has(key)){
        const childSame=[...el.children].some(c=>norm(c.innerText||c.textContent)===n && visible(c));
        if(!childSame){teams.push({name:canonical,key:n,el,x:r.x,y:r.y,w:r.w,h:r.h,area});seenT.add(key);}
      }
    }
    if(/^\d{1,3}[.,]\d{2,3}$/.test(txt)){
      const odd=Number(txt.replace(',','.'));
      if(odd<1.01||odd>999)continue;
      const childSame=[...el.children].some(c=>(c.innerText||c.textContent||'').trim()===txt && visible(c));
      if(childSame)continue;
      const key=Math.round(r.x/4)+'@'+Math.round(r.y/4);
      if(seenP.has(key))continue;
      const clickable=el.closest('button,[role="button"], [data-component="market-selection"]');
      const locked=Boolean(clickable&&(clickable.disabled || clickable.getAttribute('aria-disabled')==='true' ||
            /locked|suspended/i.test(String(clickable.className))));
      prices.push({odd,el,x:r.x,y:r.y,w:r.w,h:r.h,locked});seenP.add(key);
    }
  }
  teams.sort((a,b)=>a.y-b.y || a.x-b.x);
  prices.sort((a,b)=>a.y-b.y || a.x-b.x);
  const rows=[];const rowsKeys=new Set();
  for(let i=0;i<teams.length;i++){
    const a=teams[i];
    for(let j=i+1;j<teams.length && j<i+24;j++){
      const b=teams[j];
      if(b.key===a.key || b.y < a.y+4 || b.y-a.y>110 || Math.abs(b.x-a.x)>150)continue;
      let p=a.el;
      for(let depth=0;p && depth<13;depth++,p=p.parentElement){
        if(!p.contains(b.el)) continue;
        const r=rect(p); if(!r || r.w<400 || r.h>250 || r.h<52)continue;
        const cardPrices=prices.filter(q=>p.contains(q.el)&&q.y>=r.y-4&&q.y<=r.y+r.h+4 && !q.locked);
        if(cardPrices.length<3 || cardPrices.length>16) continue;
        // Evita captar un bloque con múltiples partidos.
        const homeCandidates=teams.filter(t=>p.contains(t.el) && t.y >=r.y-4 && t.y <r.y+r.h+4);
        const unique=new Set(homeCandidates.map(x=>x.key));
        if(unique.size>2)continue;
        const sorted=[...cardPrices].sort((x,y)=>x.x-y.x || x.y-y.y);
        // Las primeras tres columnas de cuotas son L / Empate / V.
        let trio=null;
        for(let k=0;k<=sorted.length-3;k++){
          const t=sorted.slice(k,k+3);
          if(t[0].x+15>=t[1].x || t[1].x+15>=t[2].x)continue;
          if(Math.max(...t.map(x=>x.y))-Math.min(...t.map(x=>x.y))>45)continue;
          const rowMid=(a.y+b.y)/2;
          if(Math.abs(t[0].y-rowMid)>90)continue;
          trio=t;break;
        }
        if(!trio)continue;
        // Un panel de 1X2 puede mostrar selección casa, empate, visita.
        const text=(p.innerText||p.textContent||'').replace(/\s+/g,' ').trim().slice(0,400);
        const midBox=trio[1].el.closest('button,[role="button"]');
        const midTxt=norm(midBox?.innerText || midBox?.textContent || '');
        const hasDraw=/\b(empate|draw|x)\b/.test(midTxt) || /\bempate\b/.test(norm(text));
        const key=a.key+'|'+b.key;
        const dateMatch=text.match(/\b(\d{1,2}\/\d{1,2})\s*[·\-.]?\s*(\d{1,2}:\d{2})\b/);
        const candidate={local:a.name,visitante:b.name,L:trio[0].odd,E:trio[1].odd,V:trio[2].odd,
          fecha_hora_texto:dateMatch?dateMatch[1]+' '+dateMatch[2]:'',
          doble_verificacion_empate:hasDraw,
          dom_fragment:text.slice(0,260),
          y:a.y, ancho:r.w, alto:r.h,
          pos_x:trio.map(v=>Math.round(v.x))};
        const prior=rows.find(x=>x.local===candidate.local&&x.visitante===candidate.visitante);
        if(!prior) rows.push(candidate);
        else if(!prior.doble_verificacion_empate&&hasDraw)Object.assign(prior,candidate);
        break;
      }
      if(rows.some(x=>x.local===a.name && x.visitante===b.name))break;
    }
  }
  rows.sort((a,b)=>a.y-b.y);
  return {rows,diagnostico:{title:document.title,url:location.href,body_chars:(document.body?.innerText||'').length,
    elementos:nodes.length,etiquetas_equipos:teams.length,etiquetas_cuotas:prices.length,
    body_inicio:(document.body?.innerText||'').slice(0,450).replace(/\n+/g,' | ')}};
}
"""

