#!/usr/bin/env python3
"""Exploración temporal de la navegación pública de Bundesliga; no escribe datos."""
import asyncio
import re
from playwright.async_api import async_playwright

URL="https://www.apuestatotal.com/apuestas-en-vivo/?fpath=/es-pe/spbkv3/sports/1"

async def main():
  async with async_playwright() as pw:
    browser=await pw.chromium.launch(headless=True,args=["--no-sandbox"])
    context=await browser.new_context(locale="es-PE",timezone_id="America/Lima",viewport={"width":1450,"height":920})
    page=await context.new_page()
    urls=set()
    page.on("request", lambda r: urls.add(r.url) if len(urls)<180 else None)
    await page.goto(URL,wait_until="domcontentloaded",timeout=60000)
    await page.wait_for_timeout(9000)
    print("START_URL",page.url,flush=True)
    for frame in page.frames:
      print("FRAME",frame.url[:250],flush=True)
      try:
        data=await frame.evaluate("""() => {
          const elements=[...document.querySelectorAll('a,button,[role="button"],[role="menuitem"],[role="option"],div,span')].filter(el=>/bundesliga|alemania|germany/i.test((el.innerText||el.textContent||'').trim())&& (el.innerText||el.textContent||'').trim().length<115).slice(0,200);
          return {matches:elements.slice(0,80).map(el=>({tag:el.tagName,txt:(el.innerText||el.textContent||'').trim().slice(0,100),href:el.getAttribute('href'),parent:el.parentElement?.outerHTML.slice(0,500)})),links:[...document.querySelectorAll('a[href]')].filter(a=>/league=|bundes|alemania|germany/i.test(a.getAttribute('href')||'')||/bundesliga/i.test(a.innerText||'')).slice(0,75).map(a=>({text:(a.innerText||'').slice(0,90),href:a.getAttribute('href')}))};
        }""")
        print("FOUND",repr(data)[:16000],flush=True)
        details=await frame.evaluate("""() => ({body:(document.body?.innerText||'').slice(0,4700),anchors:[...document.querySelectorAll('a[href]')].slice(0,75).map(a=>({text:(a.innerText||'').slice(0,100),href:a.getAttribute('href')})),buttons:[...document.querySelectorAll('button,[role=button]')].slice(0,75).map(a=>(a.innerText||'').trim().slice(0,60))})""")
        print("DETAILS",repr(details)[:14000],flush=True)
        for tag in ("text=Bundesliga","text=Alemania","text=Germany"):
          try:
            loc=frame.get_by_text(re.compile("Bundesliga|Alemania|Germany",re.I)).first
            if await loc.count():
              print("CLICKING",tag,flush=True)
              await loc.click(timeout=6500)
              await page.wait_for_timeout(2000)
              print("AFTER_CLICK",page.url,frame.url,flush=True)
              break
          except Exception as e:
            print("NO_CLICK",type(e).__name__,str(e)[:150],flush=True)
      except Exception as e:
        print("FRAME_ERROR",type(e).__name__,str(e)[:300],flush=True)
    print("REQUESTS",repr([u for u in urls if any(x in u.lower() for x in ("sports", "category", "api/", "event", "competition", "leag", "menu"))])[:20000],flush=True)
    print("FINISH_URL",page.url,flush=True)
    await browser.close()
if __name__=="__main__":
  asyncio.run(main())
