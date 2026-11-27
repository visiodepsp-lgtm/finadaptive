#!/usr/bin/env python3
"""KARUBET 6.3: puente exacto del notebook original a Supabase.

Lee únicamente los modelos pre-entrenados desde Supabase Storage privado
y BBETS_2026.zip actualizado. Sin reentrenar ni modificar engine.py/form.py.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import pathlib
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone

BUNDLE = "KARUBET_MODELO_6_3_PRIVADO.zip"
FIXTURE_ZIP = "BBETS_2026.zip"
BUCKET = "karubet-bbets-input"
BUNDLE_SHA256 = "06141a7fc956422e699fa59510e94759183daa62e08140cd2920978b4ea399df"
MODEL_VERSION = "6.3.0-original-" + BUNDLE_SHA256[:10]
REQUIRED = {"engine.py", "form.py", "model.joblib", "form_model.joblib",
            "labeled.csv", "pa_calibration.csv", "BBETS_2026_etiquetado.csv",
            "goal_timelines.json.gz"}


def credentials():
    base = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    secret = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    from urllib.parse import urlparse
    p = urlparse(base)
    if p.scheme != "https" or not p.hostname or not p.hostname.endswith(".supabase.co"):
        raise ValueError("SUPABASE_URL inválida")
    if not secret.startswith("sb_secret_"):
        raise ValueError("SUPABASE_SECRET_KEY inválida")
    return base, secret


def get_private(name: str) -> bytes:
    base, secret = credentials()
    request = urllib.request.Request(
        base + "/storage/v1/object/authenticated/" + BUCKET + "/" + name,
        headers={
            "apikey": secret,  # clave opaca: NO enviarla como Bearer JWT
            "User-Agent": "karubet-original-model-6.3",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=160) as result:
            contents = result.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"No se pudo leer el ZIP privado {name}: HTTP {error.code}") from None
    if len(contents) > 50 * 1024 * 1024:
        raise RuntimeError("ZIP supera máximo permitido")
    return contents


def post_rows(rows):
    base, secret = credentials()
    req = urllib.request.Request(
        base + "/rest/v1/karubet_model_outputs",
        data=json.dumps(rows, separators=(",", ":"), allow_nan=False).encode("utf-8"),
        headers={
            "apikey": secret, "Content-Type": "application/json",
            "Prefer": "return=minimal",
            "User-Agent": "karubet-original-model-6.3",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"Respuesta PostgREST inesperada: {resp.status}")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")[:240]
        raise RuntimeError(f"No se pudo guardar predicción: HTTP {error.code} {body}") from None


def extract_checked(bundle_bytes, target):
    if hashlib.sha256(bundle_bytes).hexdigest() != BUNDLE_SHA256:
        raise RuntimeError("El ZIP del modelo no coincide con KARUBET 6.3 verificado")
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as archive:
        names = {pathlib.PurePosixPath(n).as_posix() for n in archive.namelist()}
        if not REQUIRED.issubset(names):
            raise RuntimeError("El bundle privado no contiene todos los modelos requeridos")
        for info in archive.infolist():
            p = pathlib.PurePosixPath(info.filename)
            if info.is_dir():
                continue
            if len(p.parts) != 1 or ".." in p.parts or info.file_size > 15_000_000:
                raise RuntimeError("Ruta de modelo ZIP insegura")
            (target / info.filename).write_bytes(archive.read(info))


def val(row, name):
    v = row.get(name, None)
    if v is None:
        return None
    try:
        n = float(v)
        return round(n, 8) if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def make_rows(df, created):
    output = []
    for _, row in df.iterrows():
        r = row.to_dict()
        prob = {name: val(r, name) for name in ("pa", "qpa", "dpa", "rem")}
        if any(v is None or v < 0 or v > 1 for v in prob.values()):
            raise RuntimeError("Modelo original produjo una probabilidad inválida")
        if not (prob["pa"] >= prob["qpa"] >= prob["dpa"] >= prob["rem"]):
            raise RuntimeError("Violación de la jerarquía PA/Quasi/Doble/Remontada")
        output.append({
            "fixture_id": int(r["fixture_id"]),
            "model_name": "KARUBET_MATCH_CENTRE",
            "model_version": MODEL_VERSION,
            "generated_at": created,
            "data_cutoff_at": created,
            "probabilities": {
                **prob,
                "original_pa": val(r, "pa_original"),
                "adjustment_pa": val(r, "pa_ajuste"),
                "original_qpa": val(r, "original_qpa"),
                "original_dpa": val(r, "original_dpa"),
                "original_rem": val(r, "original_rem"),
                "ewma": {k: val(r, "ewma_" + k) for k in ("pa", "qpa", "dpa", "rem")},
                "h2h": {k: val(r, "h2h_" + k) for k in ("pa", "qpa", "dpa", "rem")},
                "elastic": {k: val(r, "elastic_" + k) for k in ("pa", "qpa", "dpa", "rem")},
                "poisson": {k: val(r, "poisson_" + k) for k in ("pa", "qpa", "dpa", "rem")},
            },
            "metrics": {
                "home": str(r["home"]), "away": str(r["away"]),
                "competition": str(r["competition"]),
                "date": str(r["dia"]), "hour_lima": str(r["hora"]),
                "time_confirmed": bool(r["hora_confirmada"]),
                "lambda_home": val(r, "lambda_h"),
                "lambda_away": val(r, "lambda_a"),
                "h2h_count": int(r["h2h_count"]) if r.get("h2h_count") is not None else 0,
                "h2h_evidence": val(r, "h2h_evidence"),
                "model_source": "KARUBET_Match_Centre_6_3_Colab.ipynb",
            },
        })
    return output


def main():
    import pandas as pd
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print("Preparando KARUBET 6.3 original; sin entrenamiento nuevo.", flush=True)
    bundle = get_private(BUNDLE)
    fixture = get_private(FIXTURE_ZIP)
    if not zipfile.is_zipfile(io.BytesIO(fixture)):
        raise RuntimeError("Fixture ZIP inválido")
    with tempfile.TemporaryDirectory(prefix="karubet63_") as folder:
        root = pathlib.Path(folder)
        extract_checked(bundle, root)
        fixture_path = root / FIXTURE_ZIP
        fixture_path.write_bytes(fixture)
        sys.path.insert(0, str(root))
        from engine import score
        from form import enhance
        asof = pd.Timestamp(created)
        result, current = score(root, fixture_path, asof)
        result = enhance(root, result, current)
        rows = make_rows(result, created)
        if not rows:
            raise RuntimeError("El motor original no encontró fixtures futuros")
        outfile = pathlib.Path("karubet/output/PA_Quasi_Doble_6_3.csv")
        outfile.parent.mkdir(parents=True, exist_ok=True)
        result.drop(columns=["h2h_matches"], errors="ignore").to_csv(outfile, index=False)
        # Importador de fixtures debe ejecutarse ANTES por la llave foránea.
        for start in range(0, len(rows), 80):
            post_rows(rows[start:start + 80])
        print(f"KARUBET 6.3: {len(rows)} encuentros, {len(result.columns)} atributos, "
              f"guardados en karubet_model_outputs", flush=True)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(f"## KARUBET 6.3 original\n\n- Modelo: \`{MODEL_VERSION}\`\n"
                        f"- Predicciones guardadas: **{len(rows)}**\n"
                        "- Reentrenamiento: **no** (pesos originales conservados)\n"
                        "- Datos: fixture privado BBETS_2026.zip\n")


if __name__ == "__main__":
    main()
