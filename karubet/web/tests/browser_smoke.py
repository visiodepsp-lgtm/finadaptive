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
            # Sin claves ni cookies: ambas páginas deben funcionar públicamente.
            page = await context.new_page()
            page.on("pageerror",lambda e: errors.append(str(e)))
            async def mock_data(route):
                from urllib.parse import urlparse,parse_qs
                kind=parse_qs(urlparse(route.request.url).query).get("kind",[""])[0]
                if kind=="fixtures":
                    data={"items":[PREDICTION],"count":1,"model_count":1,
                          "asof":"2026-11-27T15:00:00+00:00",
                          "page_full":False,"days":210}
                elif kind=="contexts":
                    data={"items":[{
                        "fixture_id":12345678,
                        "source_snapshot_date":"2026-11-22",
                        "context":{
                            "home":"Napoli","away":"Inter","competition":"serie-a",
                            "h_n":20,"a_n":20,"h_gf_5":1.8,"a_gf_5":1.5,
                            "home_gf_ew10":1.9,"away_gf_ew10":1.4,
                            "home_ga_ew10":0.8,"away_ga_ew10":1.1,
                            "home_xgr_ew10":1.65,"away_xgr_ew10":1.33,
                            "home_xgar_ew10":0.81,"away_xgar_ew10":1.09,
                            "home_pts_ew10":2.1,"away_pts_ew10":1.4,
                            "h2h_count":1,"h2h_evidence":0.85,
                            "home_recent":[{
                                "date":"2026-11-21","opponent":"Juventus",
                                "venue":"A","score":"2–0","result":"W","xg":1.6,"xga":0.9
                            }],
                            "away_recent":[{
                                "date":"2026-11-20","opponent":"Roma",
                                "venue":"H","score":"1–1","result":"D","xg":1.2,"xga":1.3
                            }],
                            "h2h_matches":[{
                                "date":"2026-03-10","competition":"serie-a",
                                "home":"Inter","away":"Napoli","score":"1–2",
                                "weight":0.85,"pa":1,"qpa":1,"dpa":0,"rem":0,
                                "pa_team":"Napoli",
                                "minutes":{"pa":"70","qpa":"85","dpa":None,"rem":None},
                                "goal_sequence":[["12","h"],["70","a"],["85","a"]],
                                "minute_source":"Understat"
                            }]
                        }
                    }],"count":1,"snapshot_date":"2026-11-22"}
                elif kind=="markets":
                    data={"items":[{
                        "league_code":"74","home_team":"Napoli","away_team":"Inter",
                        "kickoff_at":"2026-11-29T14:00:00+00:00",
                        "captured_at":"2026-11-27T15:15:00+00:00",
                        "odd_home":2.14,"odd_draw":3.47,"odd_away":3.39,
                        "source_url":"https://www.apuestatotal.com/"
                    }],"count":1,"asof":"2026-11-27T15:15:00+00:00"}
                elif kind=="history":
                    data={"items":[
                        {"captured_at":"2026-11-27T15:00:00+00:00","odd_home":2.08,"odd_draw":3.40,"odd_away":3.49},
                        {"captured_at":"2026-11-27T15:15:00+00:00","odd_home":2.14,"odd_draw":3.47,"odd_away":3.39}
                    ],"count":2}
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
            crest = await page.evaluate("window.KARUBET_TEAM_CREST('Napoli','serie-a')")
            assert crest and 'SSC%20Napoli.png' in crest,crest
            print("Escudo Napoli 2026/27 identificado: OK")
            logos = await page.locator("#leagueTabs .league-crest img").count()
            assert logos == 5, f"Insignias de ligas faltantes: {logos}/5"
            urls = await page.locator("#leagueTabs .league-crest img").evaluate_all(
                "(imgs)=>imgs.map(im=>im.getAttribute('src'))"
            )
            assert any("league_premier-league.png" in u for u in urls),urls
            assert any("league_ligue-1.png" in u for u in urls),urls
            await page.wait_for_function("""
                () => [...document.querySelectorAll('#leagueTabs .league-crest img')]
                  .every(image => image.complete && image.naturalWidth > 0)
            """,timeout=20000)
            print("Los cinco logos de liga descargan y son visibles en Chromium")
            print("Insignias de Premier, LaLiga, Serie A, Bundesliga y Ligue 1: OK")

            await page.locator("#nav button[data-view='rank']").click()
            assert "Napoli" in await page.locator("#content").inner_text()
            print("Top por liga: OK")
            await page.locator("#content [data-id]").first.click()
            detail=await page.locator("#content").inner_text()
            assert "Napoli" in detail and "Inter" in detail
            assert "Juventus" in detail and "Roma" in detail, (
                "Faltan partidos recientes originales: "+detail[-1500:])
            assert "Sin resultados recientes disponibles" not in detail
            assert "No hay enfrentamientos directos oficiales disponibles" not in detail
            assert "2026-11-22" in await page.locator("#classicLiveStatus").inner_text()
            await page.get_by_text("Ver estadísticas y comparación de enfoques").click()
            factor=await page.locator("#content").inner_text()
            assert "Goles a favor" in factor and "1.90" in factor, factor[-1800:]
            print("Forma reciente, H2H, factores y fecha de corte originales restaurados: OK")
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
            await page.locator("#marketList").get_by_text("Napoli",exact=False).first.wait_for(timeout=12000)
            assert await page.locator("#marketList .market-line").count()==1
            await page.locator("#marketSearch").fill("Napo")
            assert await page.locator("#marketList .market-line").count()==1
            options=await page.locator("#marketSuggestions option").evaluate_all(
                "(nodes)=>nodes.map(x=>x.value)")
            assert "Napoli" in options,options
            await page.locator("#marketSearch").fill("")
            await page.locator("#marketLeague").select_option("24")
            assert await page.locator("#marketList .market-line").count()==0
            await page.locator("#marketLeague").select_option("74")
            assert await page.locator("#marketList .market-line").count()==1
            assert await page.locator("#chartArea svg").count()==1
            assert await page.locator("#marketName img").count()==2
            print("Filtros, autocompletado, logos y gráfico de mercado: OK")
            print("Navegación a Market Centre: OK")
            await browser.close()
    finally:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill()


if __name__=="__main__":
    asyncio.run(main())
