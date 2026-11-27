#!/usr/bin/env python3
"""Resumen descriptivo de movimientos entre snapshots 1X2 de KARUBET.

No recomienda apostar ni ejecuta transacciones. Lee sólo cotizaciones ya
guardadas en Supabase. Sólo muestra comparaciones reales prepartido.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from collector import api_request, normaliza

SIDES = {
    "L": ("odd_home", "market_p_home"),
    "E": ("odd_draw", "market_p_draw"),
    "V": ("odd_away", "market_p_away"),
}


def calcular_movimientos(registros: list[dict], minimo_pct=3.0, minimo_pp=1.0):
    grupos = defaultdict(list)
    for r in registros:
        if not r.get("kickoff_at") or not r.get("captured_at"):
            continue
        key = (r["league_code"], normaliza(r["home_team"]),
               normaliza(r["away_team"]), r["kickoff_at"])
        grupos[key].append(r)

    alertas = []
    for _, filas in grupos.items():
        filas.sort(key=lambda r: (r["captured_at"], int(r.get("id", 0))), reverse=True)
        actual = filas[0]
        anterior = next((r for r in filas[1:]
                         if r["captured_at"] != actual["captured_at"]), None)
        if anterior is None:
            continue
        for lado, (odd_key, p_key) in SIDES.items():
            try:
                cuota, previa = float(actual[odd_key]), float(anterior[odd_key])
                prob, prob_previa = float(actual[p_key]), float(anterior[p_key])
            except (TypeError, ValueError, ZeroDivisionError, KeyError):
                continue
            if cuota <= 1 or previa <= 1:
                continue
            delta_pct = 100 * (cuota / previa - 1)
            delta_pp = 100 * (prob - prob_previa)
            if abs(delta_pct) < minimo_pct and abs(delta_pp) < minimo_pp:
                continue
            alertas.append({
                "league_code": actual["league_code"],
                "home_team": actual["home_team"],
                "away_team": actual["away_team"],
                "kickoff_at": actual["kickoff_at"],
                "lado": lado,
                "cuota_anterior": round(previa, 3),
                "cuota_actual": round(cuota, 3),
                "cambio_cuota_pct": round(delta_pct, 2),
                "cambio_probabilidad_pp": round(delta_pp, 2),
                "capturado_anterior_utc": anterior["captured_at"],
                "capturado_actual_utc": actual["captured_at"],
                "descripcion": "CUOTA_SUBE" if delta_pct > 0 else "CUOTA_BAJA",
                "interpretacion": "Movimiento observado, no señal de compra/venta",
            })
    return sorted(alertas, key=lambda a: abs(a["cambio_probabilidad_pp"]), reverse=True)


def main():
    ahora = datetime.now(timezone.utc)
    cutoff = (ahora - timedelta(hours=2)).isoformat(timespec="seconds")
    cols = ("id,league_code,home_team,away_team,kickoff_at,captured_at,"
            "odd_home,odd_draw,odd_away,market_p_home,market_p_draw,market_p_away")
    path = (f"karubet_odds_1x2?select={cols}"
            f"&captured_at=gte.{quote(cutoff, safe='-:TZ')}"
            "&order=captured_at.desc&limit=1000")
    recientes = api_request(path)
    alertas = calcular_movimientos(recientes)
    carpeta = Path(os.getenv("KARUBET_OUT", "karubet/output"))
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "alertas_movimientos.json").write_text(
        json.dumps({"generado_utc": ahora.isoformat(), "total": len(alertas),
                    "alertas": alertas}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"KARUBET movimientos observados: {len(alertas)} alertas (umbral ≥3% cuota o ≥1 pp probabilidad).")
    for x in alertas[:10]:
        print(f"  {x['home_team']} - {x['away_team']} {x['lado']}: "
              f"{x['cuota_anterior']:.2f} → {x['cuota_actual']:.2f} "
              f"({x['cambio_cuota_pct']:+.2f}% cuota; "
              f"{x['cambio_probabilidad_pp']:+.2f} pp prob.)")

    resumen_gh = os.getenv("GITHUB_STEP_SUMMARY")
    if resumen_gh:
        with open(resumen_gh, "a", encoding="utf-8") as file:
            file.write("\n## Movimientos de mercado detectados\n\n")
            file.write("Alertas exploratorias: **no representan una recomendación de apuesta**.\n\n")
            if alertas:
                file.write("| Partido | Selección | Cuota antes → ahora | Cambio cuota | Cambio prob. |\n")
                file.write("|---|---|---:|---:|---:|\n")
                for x in alertas[:15]:
                    file.write(f"| {x['home_team']} – {x['away_team']} | {x['lado']} | "
                               f"{x['cuota_anterior']:.2f} → {x['cuota_actual']:.2f} | "
                               f"{x['cambio_cuota_pct']:+.2f}% | "
                               f"{x['cambio_probabilidad_pp']:+.2f} pp |\n")
            else:
                file.write("Sin movimientos que superen el umbral (o sin dos capturas todavía).\n")


if __name__ == "__main__":
    main()
