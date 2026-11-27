#!/usr/bin/env python3
"""Prueba de navegador REAL de Hoja 1 (sin claves ni Supabase).

Sirve la web estática en localhost, abre el iframe clásico dentro del panel,
inyecta una predicción sintética con el mismo formato del backend y valida
Fixture, Top por liga y Analizar partido. Sólo testea presentación.
"""
import asyncio
import json
import pathlib
import socket
import subprocess
import sys
import time

from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "test-output" / "classic-smoke.png"

SAMPLE = {
    "rows": [{
        "fixture_id": 12345678, "competition": "serie-a",
        "home": "Napoli", "away": "Inter", "dia": "2026-11-29", "hora": "09:00",
        "hora_confirmada": True,
        "lambda_h": 1.7, "lambda_a": 1.4,
        "h2h_count": 8, "h2h_evidence": 1.2,
        "ewma_pa": .52, "ewma_qpa": .21, "ewma_dpa": .08, "ewma_rem": .025,
        "h2h_pa": .55, "h2h_qpa": .22, "h2h_dpa": .085, "h2h_rem": .027,
        "original_pa": .50, "original_qpa": .20,
        "original_dpa": .075, "original_rem": .023,
        "h2h_matches": [], "home_recent": [], "away_recent": [],
    }],
    "meta": {"today": "2026-11-27", "fresh": True,
             "asof": "2026-11-27 10:00 a. m.",
             "source_date": "Supabase - KARUBET 6.3"},
    "logos": {}, "league_logos": {},
}


async def main():
    port = 8765
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(ROOT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        # Wait for the HTTP server to start, without using network outside localhost.
        for _ in range(35):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=.5):
                    break
            except OSError:
                await asyncio.sleep(.2)
        errors = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page(viewport={"width": 1450, "height": 900})
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            response = await page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            assert response.status == 200, "No carga la página KARUBET"
            await page.evaluate("""() => {
                document.getElementById('loginPanel').hidden=true;
                document.getElementById('workspace').hidden=false;
            }""")
            classic = page.frame_locator("#classicFrame")
            await classic.locator("#content").wait_for(timeout=10000)
            await page.evaluate("""payload => {
                document.getElementById("classicFrame").contentWindow.postMessage(
                    {type:"KARUBET_CLASSIC_DATA",payload:payload},location.origin
                );
            }""", SAMPLE)
            await classic.locator("#content").get_by_text("Napoli", exact=False).first.wait_for(timeout=15000)
            fixture_text = await classic.locator("#content").inner_text()
            assert "Inter" in fixture_text
            assert "52.0%" in fixture_text, fixture_text[:1000]
            print("Fixture + cuotas de probabilidad PA sinteticas: OK")
            await classic.locator("#nav button[data-view='rank']").click()
            rank = await classic.locator("#content").inner_text()
            assert "Napoli" in rank
            print("Top por liga: OK")
            await classic.locator("#content [data-id]").first.click()
            detail = await classic.locator("#content").inner_text()
            assert "Napoli" in detail and "Inter" in detail
            print("Análisis por partido: OK")
            await page.evaluate("document.getElementById('classicFrame').scrollIntoView()")
            OUT.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(OUT), full_page=True)
            assert not errors, "Error JS: " + json.dumps(errors)[:1200]
            await browser.close()
            print("Match Centre 6.3 en iframe del mismo origen: OK")
    finally:
        server.terminate()
        try:
            server.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    asyncio.run(main())
