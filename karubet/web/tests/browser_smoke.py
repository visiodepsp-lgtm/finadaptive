#!/usr/bin/env python3
"""KARUBET browser smoke sin iframe: visita la Hoja 1 como página completa,
inyecta una respuesta del API sintética, comprueba los cuatro módulos y el
enlace al Market Centre. No utiliza datos reales ni secretos."""
import asyncio
import json
import pathlib
import socket
import subprocess
import sys
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "test-output" / "classic-smoke.png"
PREDICTION = {
    "fixture_id": 12345678, "competition": "serie-a",
    "home_team": "Napoli", "away_team": "Inter",
    "kickoff_at": "2026-11-29T14:00:00+00:00",
    "status": "unplayed", "phase": None,
    "model": {
        "model_version": "6.3",
        "generated_at": "2026-11-27T15:00:00+00:00",
        "metrics": {"lambda_home":1.7,"lambda_away":1.4,
                    "h2h_count":8,"h2h_evidence":1.2},
        "probabilities": {
            "pa": .52, "qpa": .21, "dpa": .08, "rem": .025,
            "original_pa": .50, "original_qpa": .20,
            "original_dpa": .075, "original_rem": .023,
            "ewma": {"pa": .52,"qpa": .21,"dpa": .08,"rem": .025},
            "h2h": {"pa": .55,"qpa": .22,"dpa": .085,"rem": .027}
        }
    }
}

async def main():
    port = 8765
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(ROOT)],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL
    )
    try:
        for _ in range(35):
            try:
                with socket.create_connection(("127.0.0.1",port),timeout=.5):
                    break
            except OSError:
                await asyncio.sleep(.2)
        errors=[]
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True,args=["--no-sandbox"])
            context = await browser.new_context(viewport={"width":1450,"height":900})
            await context.add_init_script(
                "sessionStorage.setItem('karubet_access','TEST_TOKEN_LONG_ENOUGH_987654321')")
            page = await context.new_page()
            page.on("pageerror",lambda e: errors.append(str(e)))
            async def mock_data(route):
                from urllib.parse import urlparse,parse_qs
                kind=parse_qs(urlparse(route.request.url).query).get("kind",[""])[0]
                if kind=="fixtures":
                    data={"items":[PREDICTION],"count":1,"model_count":1,
                          "asof":"2026-11-27T15:00:00+00:00",
                          "page_full":False,"days":210}
                elif kind=="markets":
                    data={"items":[],"count":0,"asof":"2026-11-27T15:00:00+00:00"}
                else:
                    data={"items":[]}
                await route.fulfill(status=200,content_type="application/json",
                                    body=json.dumps(data))
            await page.route("**/api/data?*",mock_data)
            response=await page.goto(
                f"http://127.0.0.1:{port}/classic.html",wait_until="networkidle")
            assert response.status==200,"Hoja 1 no responde"
            assert await page.locator("iframe").count()==0,"No debe existir ningún iframe"
            await page.locator("#content").get_by_text("Napoli",exact=False).first.wait_for(timeout=15000)
            text=await page.locator("#content").inner_text()
            assert "Inter" in text and "52.0%" in text,text[:1100]
            print("Hoja 1 completa, fixtures y PA original: OK")
            await page.locator("#nav button[data-view='rank']").click()
            assert "Napoli" in await page.locator("#content").inner_text()
            print("Top por liga: OK")
            await page.locator("#content [data-id]").first.click()
            detail=await page.locator("#content").inner_text()
            assert "Napoli" in detail and "Inter" in detail
            print("Análisis por partido: OK")
            OUT.parent.mkdir(parents=True,exist_ok=True)
            await page.screenshot(path=str(OUT),full_page=True)
            assert not errors, "Error JavaScript: "+json.dumps(errors)[:1200]
            link=page.get_by_role("link",name="02 · Market Centre")
            assert await link.count()==1
            await link.click()
            await page.wait_for_url("**/?tab=market",timeout=12000)
            await page.locator("#marketPage").wait_for(state="visible",timeout=15000)
            assert await page.locator("iframe").count()==0
            print("Navegación a Market Centre: OK")
            await browser.close()
    finally:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill()


if __name__=="__main__":
    asyncio.run(main())
