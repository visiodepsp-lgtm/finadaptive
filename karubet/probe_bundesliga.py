#!/usr/bin/env python3
"""Explora navegación de categorías, solo lectura, no recopila cuotas."""
import asyncio,re
from playwright.async_api import async_playwright
URL="https://www.apuestatotal.com/apuestas-en-vivo/?fpath=/es-pe/spbkv3/sports/1"
async def main():
  async with async_playwright() as pw:
    browser=await pw.chromium.launch(headless=True,args=["--no-sandbox"])
    context=await browser.new_context(locale="es-PE",timezone_id="America/Lima",viewport={"width":1500,"height":920})
    page=await context.new_page()
    await page.goto(URL,wait_until="domcontentloaded",timeout=55000)
    await page.wait_for_timeout(8000)
    frame=next(f for f in page.frames if "kmianko.com" in f.url)
    async def report(name):
      print("STAGE",name,"URL",frame.url,flush=True)
      print("BODY",repr((await frame.locator("body").inner_text())[:5500]),flush=True)
      data=await frame.evaluate("""() => [...document.querySelectorAll('button,[role=button],a,[data-part]')]
         .filter(e=>/menú|menu|fútbol|bundesliga|alemania|germany/i.test((e.innerText||e.textContent||'').trim())&&
           (e.innerText||e.textContent||'').trim().length<75)
         .slice(0,85).map(e=>({tag:e.tagName,text:(e.innerText||e.textContent||'').trim().slice(0,70),
           part:e.getAttribute('data-part'),role:e.getAttribute('role'),
           html:e.outerHTML.slice(0,250)}))""")
      print("CONTROLS",repr(data)[:16000],flush=True)
    await report("start")
    for label in ("MENÚ","Fútbol","Alemania","Bundesliga"):
      try:
        # exact text targets navigational elements rather than entire match card
        loc=frame.get_by_text(label,exact=True)
        print("LOOKUP",label,await loc.count(),flush=True)
        if await loc.count()==0: continue
        nodes=await loc.all()
        chosen=None
        for n in nodes[:8]:
          par=await n.evaluate("(e)=>e.closest('button,[role=button],a')?.outerHTML.slice(0,250)")
          print("CANDIDATE",label,par,flush=True)
          if label=="Bundesliga" and par and "featured" in par:continue
          chosen=n;break
        if not chosen:continue
        await chosen.click(timeout=5500)
        await frame.wait_for_timeout(1200)
        await report("clicked "+label)
      except Exception as e:
        print("CLICK_ERROR",label,type(e).__name__,str(e)[:250],flush=True)
    print("FINAL",frame.url,page.url,flush=True)
    await browser.close()
if __name__=="__main__":
  asyncio.run(main())
