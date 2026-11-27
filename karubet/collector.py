#!/usr/bin/env python3
"""KARUBET: recolector de cuotas L/E/V desde listados Apuesta Total.

Ejecución inicial: solo lectura y diagnóstico.
Con --persist: guarda snapshots en la BD Supabase (API secret key, solo servidor).
Este script NO calcula las probabilidades del modelo futbolístico KARUBET.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from catalogo import NOMBRES_AT, URLS_LIGAS
from extractor_dom import EXTRACT_1X2_JS

MAX_EVENTOS_POR_LIGA = 50
PASOS_SCROLL = 16
ESPERA_INICIAL_MS = 6500
ESPERA_SCROLL_MS = 1200


def normaliza(nombre: str) -> str:
    nombre = unicodedata.normalize("NFD", str(nombre or ""))
    nombre = "".join(c for c in nombre if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", nombre).strip()


def liga_de_url(url: str) -> str:
    m = re.search(r"league=(\d+)", url)
    return m.group(1) if m else "desconocida"


def validar_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme == "https" and p.hostname in ("www.apuestatotal.com", "apuestatotal.com")
    except (TypeError, ValueError):
        return False


def hora_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def probabilidades_mercado(l: float, e: float, v: float) -> tuple[float, float, float]:
    inv = [1 / l, 1 / e, 1 / v]
    total = sum(inv)
    return tuple(round(p / total, 4) for p in inv)


async def scroll_contenedores(page) -> None:
    await page.mouse.move(1050, 700)
    await page.mouse.wheel(0, 640)
    # Listados SPA pueden usar contenedores desplazables dentro de iframes.
    js = """() => {
      const els=[...document.querySelectorAll('div,main,section')]
        .filter(e=>e.clientHeight>180 && e.scrollHeight>e.clientHeight+250);
      els.sort((a,b)=>(b.clientHeight*b.clientWidth)-(a.clientHeight*a.clientWidth));
      for(const e of els.slice(0,2))e.scrollBy(0,640);
    }"""
    for frame in page.frames:
        try:
            await frame.evaluate(js)
        except Exception:
            pass


async def escanear_liga(page, url: str, numero: int, carpeta: Path) -> tuple[list[dict], dict]:
    codigo = None
    errores = []
    filas = {}
    mayor_diagnostico = {}
    try:
        respuesta = await page.goto(url, wait_until="domcontentloaded", timeout=55000)
        codigo = respuesta.status if respuesta else None
        await page.wait_for_timeout(ESPERA_INICIAL_MS)
        for paso in range(PASOS_SCROLL):
            for frame in page.frames:
                try:
                    data = await frame.evaluate(EXTRACT_1X2_JS, {"teamNames": NOMBRES_AT})
                    diag = data.get("diagnostico") or {}
                    if (diag.get("body_chars") or 0) > (mayor_diagnostico.get("body_chars") or 0):
                        mayor_diagnostico = diag
                    for fila in data.get("rows", []):
                        if not fila.get("doble_verificacion_empate"):
                            continue
                        k = (normaliza(fila.get("local")),
                             normaliza(fila.get("visitante")),
                             fila.get("fecha_hora_texto") or "")
                        if all(k[:2]):
                            filas[k] = fila
                except Exception as error:
                    if len(errores) < 4:
                        errores.append(type(error).__name__ + ": " + str(error)[:160])
            if len(filas) >= MAX_EVENTOS_POR_LIGA:
                break
            await scroll_contenedores(page)
            await page.wait_for_timeout(ESPERA_SCROLL_MS)

        diag = {
            "liga": liga_de_url(url), "url": url, "url_final": page.url,
            "http": codigo, "eventos_con_1x2": len(filas),
            "etiquetas_equipos": mayor_diagnostico.get("etiquetas_equipos"),
            "etiquetas_cuotas": mayor_diagnostico.get("etiquetas_cuotas"),
            "longitud_texto": mayor_diagnostico.get("body_chars"),
            "inicio_texto": mayor_diagnostico.get("body_inicio", ""),
            "errores_js": errores,
            "pasos_scroll": paso + 1,
        }
        if filas:
            diag["estado"] = "CUOTAS_1X2_DETECTADAS"
        elif codigo in (403, 429):
            diag["estado"] = "BLOQUEO_HTTP"
        elif "captcha" in str(mayor_diagnostico).lower():
            diag["estado"] = "POSIBLE_CAPTCHA"
        elif not mayor_diagnostico.get("body_chars"):
            diag["estado"] = "PAGINA_SIN_CONTENIDO"
        else:
            diag["estado"] = "SIN_FILAS_1X2"
    except Exception as error:
        diag = {
            "liga": liga_de_url(url), "url": url, "http": codigo,
            "estado": "ERROR_NAVEGACION", "eventos_con_1x2": 0,
            "error": type(error).__name__ + ": " + str(error)[:250],
        }

    try:
        await page.screenshot(path=str(carpeta / f"liga_{numero:02d}.png"),
                              full_page=False, timeout=10000)
    except Exception as error:
        diag["error_screenshot"] = type(error).__name__
    if not filas:
        try:
            (carpeta / f"liga_{numero:02d}_html.html").write_text(
                (await page.content())[:1000000], encoding="utf-8")
        except Exception:
            pass
    return list(filas.values())[:MAX_EVENTOS_POR_LIGA], diag


async def recolectar(carpeta: Path) -> tuple[list[dict], list[dict]]:
    resultados = []
    diagnosticos = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            contexto = await browser.new_context(
                locale="es-PE", timezone_id="America/Lima",
                viewport={"width": 1500, "height": 1000},
                device_scale_factor=1,
            )
            for numero, url in enumerate(URLS_LIGAS, 1):
                if not validar_url(url):
                    raise ValueError(f"URL no permitida: {url}")
                page = await contexto.new_page()
                try:
                    filas, diag = await escanear_liga(page, url, numero, carpeta)
                    codigo = liga_de_url(url)
                    for fila in filas:
                        resultados.append({
                            "league_code": codigo,
                            "source_url": url,
                            "home_team": fila["local"],
                            "away_team": fila["visitante"],
                            "kickoff_text": fila.get("fecha_hora_texto") or None,
                            "odd_home": fila["L"], "odd_draw": fila["E"], "odd_away": fila["V"],
                            "verified_draw_label": bool(fila.get("doble_verificacion_empate")),
                            "raw_excerpt": str(fila.get("dom_fragment") or "")[:260],
                        })
                    diagnosticos.append(diag)
                    print(f"Liga {codigo}: {len(filas)} filas, HTTP {diag.get('http')}, {diag.get('estado')}", flush=True)
                finally:
                    await page.close()
            await contexto.close()
        finally:
            await browser.close()
    return resultados, diagnosticos



# La web muestra "27/11 • 15:00": el punto es U+2022 (no U+00B7).
DATE_WEB_RE = re.compile(
    r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})\s*[·•.\-]?\s*(\d{1,2}):(\d{2})(?!\d)"
)
EXPECTED_COMPETITIONS = {
    "25": "Ligue 1", "74": "Serie A", "24": "Premier League",
    "38": "La Liga", "125": "Champions League",
}


def completar_fecha(f: dict, capturado_utc: str | None = None) -> None:
    """Recupera fecha del HTML original y calcula fecha UTC si el año es inequívoco.

    La web no escribe el año: el año se infiere sólo dentro de una ventana futura
    de 120 días / pasada de 2 días desde la captura; de lo contrario queda NULL.
    La hora se interpreta en America/Lima (configuración de Playwright).
    """
    fuente = (f.get("kickoff_text") or "") + " " + (f.get("raw_excerpt") or "")
    hallazgo = DATE_WEB_RE.search(fuente)
    f["kickoff_at"] = None
    if not hallazgo:
        return
    dia, mes, hora, minuto = map(int, hallazgo.groups())
    f["kickoff_text"] = f"{dia:02d}/{mes:02d} {hora:02d}:{minuto:02d}"
    ahora = datetime.fromisoformat(capturado_utc) if capturado_utc else datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
    ahora_lima = ahora.astimezone(ZoneInfo("America/Lima"))
    opciones = []
    for anio in (ahora_lima.year - 1, ahora_lima.year, ahora_lima.year + 1):
        try:
            fecha = datetime(anio, mes, dia, hora, minuto, tzinfo=ZoneInfo("America/Lima"))
        except ValueError:
            continue
        segundos = (fecha - ahora_lima).total_seconds()
        if -2 * 86400 <= segundos <= 120 * 86400:
            opciones.append((abs(segundos), fecha))
    if opciones:
        fecha = min(opciones, key=lambda x: x[0])[1]
        f["kickoff_at"] = fecha.astimezone(timezone.utc).isoformat()


def revisar_filas(filas: list[dict], diagnosticos: list[dict], capturado_utc: str | None = None) -> tuple[list[dict], dict]:
    apariciones = defaultdict(set)
    for fila in filas:
        pareja = (normaliza(fila["home_team"]), normaliza(fila["away_team"]))
        apariciones[pareja].add(fila["league_code"])
    solapadas = {p for p, codigos in apariciones.items() if len(codigos) > 1}
    validas = []
    rechazadas = Counter()
    faltan_fechas = 0
    falta_categoria = 0
    visto = set()
    for f in filas:
        completar_fecha(f, capturado_utc)
        etiqueta_esperada = EXPECTED_COMPETITIONS.get(f["league_code"])
        liga_confirmada = bool(etiqueta_esperada and etiqueta_esperada.casefold() in (f.get("raw_excerpt") or "").casefold())
        pareja = (normaliza(f["home_team"]), normaliza(f["away_team"]))
        if pareja in solapadas:
            rechazadas["partido_en_multiples_categorias"] += 1
            continue
        if not pareja[0] or not pareja[1] or pareja[0] == pareja[1]:
            rechazadas["equipos_invalidos"] += 1
            continue
        llave = (f["league_code"], *pareja, f["kickoff_text"] or "")
        if llave in visto:
            rechazadas["duplicado_misma_captura"] += 1
            continue
        visto.add(llave)
        try:
            cuotas = [float(f[k]) for k in ("odd_home", "odd_draw", "odd_away")]
            suma_inv = sum(1 / q for q in cuotas)
        except (ValueError, TypeError, ZeroDivisionError):
            rechazadas["cuotas_invalidas"] += 1
            continue
        if not f["verified_draw_label"] or any(q < 1.01 or q > 999 for q in cuotas):
            rechazadas["cuotas_o_empate_no_verificados"] += 1
            continue
        if not 0.90 <= suma_inv <= 1.40:
            rechazadas["margen_1x2_atipico"] += 1
            continue
        f["odd_home"], f["odd_draw"], f["odd_away"] = cuotas
        p = probabilidades_mercado(*cuotas)
        f["market_p_home"], f["market_p_draw"], f["market_p_away"] = p
        f["quality_flags"] = {
            "kickoff_missing": not bool(f.get("kickoff_at")),
            "kickoff_year_inferred": bool(f.get("kickoff_at")),
            "league_not_confirmed": not liga_confirmada,
            "market_overround": round(suma_inv, 5),
        }
        if not f.get("kickoff_at"):
            faltan_fechas += 1
        if not liga_confirmada:
            falta_categoria += 1
        validas.append(f)

    conteos = [d.get("eventos_con_1x2", 0) for d in diagnosticos]
    alertas = []
    if len(conteos) > 1 and len(set(conteos)) == 1 and conteos[0] > 0:
        alertas.append("Todas las ligas devolvieron la misma cantidad de filas: revisar el listado.")
    if faltan_fechas:
        alertas.append(f"{faltan_fechas} filas sin fecha UTC confirmada: NO aptas aún para cruce automático con fixtures.")
    if falta_categoria:
        alertas.append(f"{falta_categoria} filas sin etiqueta de competición confirmada.")
    if solapadas:
        alertas.append(f"{len(solapadas)} cruces aparecen en varias categorías y fueron excluidos.")
    if any(d.get("estado") != "CUOTAS_1X2_DETECTADAS" for d in diagnosticos):
        alertas.append("Una o más categorías sin lectura válida.")

    return validas, {
        "partidos_leidos": len(filas), "partidos_aceptados": len(validas),
        "partidos_rechazados": dict(rechazadas),
        "sin_fecha": faltan_fechas, "categoria_no_confirmada": falta_categoria,
        "solapados_entre_ligas": len(solapadas),
        "alertas": alertas,
    }


def api_request(path: str, method="GET", data=None):
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    secret = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".supabase.co"):
        raise RuntimeError("SUPABASE_URL inválida o ausente")
    if not secret.startswith("sb_secret_"):
        raise RuntimeError("SUPABASE_SECRET_KEY ausente o no es una Secret API key sb_secret_")
    url = base + "/rest/v1/" + path
    headers = {
        "apikey": secret,  # sb_secret_ es clave opaca: NO enviarla como Bearer JWT
        "Accept": "application/json",
        "User-Agent": "karubet-gh-actions/1.0",
    }
    payload = None
    if data is not None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Prefer"] = "return=representation"
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            respuesta = r.read().decode("utf-8")
            return json.loads(respuesta) if respuesta else []
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")[:320]
        raise RuntimeError(f"Supabase HTTP {error.code}: {body}") from None


def persistir(filas: list[dict], diagnosticos: list[dict], resumen: dict, capturado: str):
    ej = api_request("karubet_ingest_runs?select=id", method="POST", data={
        "source": "apuestatotal", "started_at": capturado,
        "status": "running", "games_detected": len(filas),
        "diagnostics": {"resumen": resumen, "ligas": diagnosticos},
    })
    if not ej or not ej[0].get("id"):
        raise RuntimeError("Supabase no devolvió ID para la ejecución")
    run_id = ej[0]["id"]
    try:
        for comienzo in range(0, len(filas), 40):
            grupo = []
            for fila in filas[comienzo:comienzo + 40]:
                grupo.append({
                    **fila,
                    "run_id": run_id,
                    "captured_at": capturado,
                    "source": "apuestatotal",
                })
            api_request("karubet_odds_1x2", method="POST", data=grupo)
        api_request(f"karubet_ingest_runs?id=eq.{run_id}", method="PATCH", data={
            "finished_at": hora_utc(),
            "status": "partial" if resumen["alertas"] else "completed",
        })
    except Exception:
        try:
            api_request(f"karubet_ingest_runs?id=eq.{run_id}", method="PATCH", data={
                "finished_at": hora_utc(), "status": "error",
            })
        except Exception:
            pass
        raise
    return run_id


def guardar_resultados(carpeta: Path, filas: list[dict], diags: list[dict], resumen: dict):
    (carpeta / "resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    (carpeta / "diagnosticos.json").write_text(json.dumps(diags, indent=2, ensure_ascii=False), encoding="utf-8")
    (carpeta / "cuotas_1x2.json").write_text(json.dumps(filas, indent=2, ensure_ascii=False), encoding="utf-8")
    if filas:
        columnas = ["league_code", "home_team", "away_team", "kickoff_text", "kickoff_at",
                    "odd_home", "odd_draw", "odd_away", "market_p_home",
                    "market_p_draw", "market_p_away"]
        with (carpeta / "cuotas_1x2.csv").open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=columnas, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(filas)
    resumen_gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen_gh:
        with open(resumen_gh, "a", encoding="utf-8") as file:
            file.write("## KARUBET · Escáner 1X2\n\n")
            file.write(f"- Filas leídas: **{resumen['partidos_leidos']}**\n")
            file.write(f"- Aceptadas para guardar: **{resumen['partidos_aceptados']}**\n")
            file.write(f"- Sin fecha: **{resumen['sin_fecha']}**\n")
            for alerta in resumen["alertas"]:
                file.write(f"- ⚠️ {alerta}\n")
            file.write("\nLos snapshots de mercado no son probabilidades del modelo KARUBET.\n")


def filtrar_ventana_prematch(filas: list[dict], capturado: str, horizonte_dias: int = 4) -> tuple[list[dict], dict]:
    """Sólo partidos verificados que comenzarán durante los próximos N días.

    No borra ningún histórico existente: simplemente deja de tomar snapshots
    tras el inicio del partido. El código de liga web debe estar verificado.
    """
    ahora = datetime.fromisoformat(capturado)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
    limite = ahora + timedelta(days=horizonte_dias)
    aptas = []
    descartes = Counter()
    for fila in filas:
        flags = fila.get("quality_flags", {})
        if flags.get("league_not_confirmed"):
            descartes["competicion_no_verificada"] += 1
            continue
        if not fila.get("kickoff_at"):
            descartes["inicio_sin_fecha_verificada"] += 1
            continue
        inicio = datetime.fromisoformat(fila["kickoff_at"])
        if inicio.tzinfo is None:
            descartes["inicio_sin_zona_horaria"] += 1
            continue
        if inicio <= ahora:
            descartes["inicio_ya_comenzado"] += 1
            continue
        if inicio > limite:
            descartes["fuera_ventana_4_dias"] += 1
            continue
        aptas.append(fila)
    return aptas, dict(descartes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="karubet/output")
    parser.add_argument("--persist", action="store_true", help="Escribe capturas en Supabase")
    args = parser.parse_args()
    carpeta = Path(args.out)
    carpeta.mkdir(parents=True, exist_ok=True)
    # Prueba de conexión con RLS y credenciales sin mostrar la clave.
    api_request("karubet_ingest_runs?select=id&limit=1")
    capturado = hora_utc()
    filas, diagnosticos = asyncio.run(recolectar(carpeta))
    validas, resumen = revisar_filas(filas, diagnosticos, capturado)
    resumen["capturado_utc"] = capturado
    resumen["modo"] = "PERSISTIR_SUPABASE" if args.persist else "SOLO_DIAGNOSTICO"
    # Capturar únicamente partidos de las próximas 96 horas.
    # Los partidos que arrancaron dejan de recibir snapshots, pero se conserva
    # su serie histórica íntegra para backtesting sin sesgo de supervivencia.
    aptas, descartes = filtrar_ventana_prematch(validas, capturado, horizonte_dias=4)
    resumen["ventana_proximos_dias"] = 4
    resumen["partidos_aptos_prepartido"] = len(aptas)
    resumen["descartados_para_bd"] = descartes
    if descartes:
        resumen["alertas"].append(
            f"{sum(descartes.values())} filas fuera de ventana o sin verificar: sólo diagnóstico."
        )
    guardar_resultados(carpeta, validas, diagnosticos, resumen)
    print(json.dumps(resumen, ensure_ascii=False, indent=2), flush=True)
    if args.persist and aptas:
        # Cada ejecución crea un run_id independiente: retenemos también cuotas sin cambio.
        run_id = persistir(aptas, diagnosticos, resumen, capturado)
        print(f"Guardados {len(aptas)} snapshots prepartido en Supabase, run_id={run_id}")
    elif args.persist:
        print("Ningún partido prepartido validado: no se escribe un snapshot vacío.")
        # Un sitio sin datos puede reflejar un problema transitorio; reportar fallo de ejecución.
        if validas or any(d.get("estado") not in ("CUOTAS_1X2_DETECTADAS",) for d in diagnosticos):
            sys.exit("Sin partidas aptas para guardar: revisar diagnosticos.")
    else:
        print("Prueba de solo lectura completada: NO se ha escrito ningún dato.")
    if not validas:
        sys.exit("Sin cuotas 1X2 verificadas; revisa los artifacts del workflow.")


if __name__ == "__main__":
    main()
