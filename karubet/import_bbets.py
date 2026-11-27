#!/usr/bin/env python3
"""KARUBET: importer semanal idempotente para los ZIP privados BBETS.

Fuente: Supabase Storage bucket privado karubet-bbets-input.
Entradas exactas: BBETS_DATA.zip y BBETS_2026.zip.
Sólo ingiere fixtures; los ZIP íntegros conservan shots y appearances para
un futuro entrenamiento de los modelos PA/Quasi PA/Doble PA.
No ejecuta apuestas ni recalcula modelos.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePosixPath

HISTORIC = {"bundesliga", "epl", "la-liga", "ligue-1", "serie-a"}
CURRENT = HISTORIC | {"ucl"}
BUCKET = "karubet-bbets-input"
ARCHIVES = {
    "BBETS_DATA": ("BBETS_DATA.zip", "karubet_historical_matches"),
    "BBETS_2026": ("BBETS_2026.zip", "karubet_fixtures_2026"),
}


def endpoint():
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    secret = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    u = urllib.parse.urlparse(base)
    if u.scheme != "https" or not u.hostname or not u.hostname.endswith(".supabase.co"):
        raise ValueError("SUPABASE_URL no es una URL de proyecto válida")
    if not secret.startswith("sb_secret_"):
        raise ValueError("SUPABASE_SECRET_KEY no es una clave privada válida")
    return base, secret


def request(path, method="GET", body=None, raw=False, extra_headers=None, timeout=100):
    base, secret = endpoint()
    url = base + path
    headers = {
        "apikey": secret,
        "Accept": "application/json" if not raw else "application/octet-stream",
        "User-Agent": "KARUBET-weekly-BBETS/1.0",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = response.read()
            if raw:
                return payload
            return json.loads(payload) if payload else None
    except urllib.error.HTTPError as error:
        # Never output secret-bearing URLs, headers or request bodies.
        msg = error.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"Supabase respondió HTTP {error.code}: {msg}") from None


def read_private_zip(filename):
    # Supabase Storage private bucket: authorised request with the server-side secret.
    _, secret = endpoint()
    payload = request(
        f"/storage/v1/object/authenticated/{BUCKET}/{filename}",
        raw=True, timeout=160,
        extra_headers={"Authorization": "Bearer " + secret},
    )
    if len(payload) > 50 * 1024 * 1024:
        raise ValueError("ZIP supera el límite de seguridad de 50 MB")
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise ValueError(f"{filename} no contiene un ZIP válido")
    archive = zipfile.ZipFile(io.BytesIO(payload))
    if sum(info.file_size for info in archive.infolist()) > 200 * 1024 * 1024:
        raise ValueError("ZIP descomprimido excede 200 MB")
    return payload, archive


def num(value, numeric_type=float):
    if value is None or value == "" or str(value).strip().lower() in ("nan", "none", "null"):
        return None
    value = numeric_type(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def int_or_none(value):
    return num(value, int)


def float_or_none(value):
    return num(value, float)


def hashed(row):
    canonical = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def historic_row(raw, path):
    comp, season, _ = path.split("/")
    score = re.fullmatch(r"(\d+)-(\d+)", raw["score"].strip())
    if not score:
        raise ValueError(f"Marcador histórico no válido: {path}")
    if not raw["date"] or not raw["fixture_id"]:
        raise ValueError(f"Fecha o ID histórico faltante: {path}")
    row = {
        "fixture_id": int(raw["fixture_id"]),
        "provider": raw["provider"] or "Understat",
        "competition": comp,
        "season": int(season),
        "match_date": raw["date"],
        "home_team": raw["home"],
        "away_team": raw["away"],
        "score": raw["score"],
        "home_goals": int(score[1]),
        "away_goals": int(score[2]),
        "home_xg": float_or_none(raw.get("home_xg")),
        "away_xg": float_or_none(raw.get("away_xg")),
        "home_win_probability": float_or_none(raw.get("home_win_probability")),
        "draw_probability": float_or_none(raw.get("draw_probability")),
        "away_win_probability": float_or_none(raw.get("away_win_probability")),
        "totals_unreliable": str(raw.get("totals_unreliable", "")).lower() == "true",
        "raw_data": dict(raw),
    }
    row["row_hash"] = hashed(row)
    return row


def current_row(raw, path):
    comp = path.split("/")[0]
    if not raw["kickoff_utc"].endswith("Z") or not raw["fixture_id"]:
        raise ValueError(f"Hora UTC o fixture_id faltante en {path}")
    row = {
        "fixture_id": int(raw["fixture_id"]),
        "source": raw.get("source") or "Sportmonks",
        "competition": comp,
        "season": 2026,
        "match_date": raw["date"],
        "kickoff_at": raw["kickoff_utc"],
        "home_team_id": int_or_none(raw.get("home_id")),
        "away_team_id": int_or_none(raw.get("away_id")),
        "home_team": raw["home"],
        "away_team": raw["away"],
        "status": raw.get("status") or "unplayed",
        "phase": raw.get("phase"),
        "home_goals": int_or_none(raw.get("home_goals")),
        "away_goals": int_or_none(raw.get("away_goals")),
        "home_goals_90": int_or_none(raw.get("home_goals_90")),
        "away_goals_90": int_or_none(raw.get("away_goals_90")),
        "home_xg": float_or_none(raw.get("home_xg")),
        "away_xg": float_or_none(raw.get("away_xg")),
        "home_xpts": float_or_none(raw.get("home_xpts")),
        "away_xpts": float_or_none(raw.get("away_xpts")),
        "home_shots": int_or_none(raw.get("home_shots")),
        "away_shots": int_or_none(raw.get("away_shots")),
        "raw_data": dict(raw),
    }
    row["row_hash"] = hashed(row)
    return row


def parse_matches(archive, dataset):
    matches = {}
    files_seen = 0
    count = Counter()
    for entry in archive.namelist():
        path = PurePosixPath(entry).as_posix()
        if dataset == "BBETS_DATA":
            m = re.fullmatch(r"([^/]+)/(\d{4})/fixtures\.csv", path)
            if not m or m[1] not in HISTORIC or not 2017 <= int(m[2]) <= 2025:
                continue
        else:
            m = re.fullmatch(r"([^/]+)/fixtures\.csv", path)
            if not m or m[1] not in CURRENT:
                continue
        files_seen += 1
        with archive.open(entry) as csvfile:
            reader = csv.DictReader(io.TextIOWrapper(csvfile, encoding="utf-8-sig"))
            required = ("fixture_id", "date", "home", "away",
                        "score" if dataset == "BBETS_DATA" else "kickoff_utc")
            if not reader.fieldnames or any(c not in reader.fieldnames for c in required):
                raise ValueError(f"Columnas de fixture inesperadas en {path}")
            for raw in reader:
                row = historic_row(raw, path) if dataset == "BBETS_DATA" else current_row(raw, path)
                fid = row["fixture_id"]
                if fid in matches:
                    raise ValueError(f"Duplicado fixture_id={fid} en el archivo {dataset}")
                if not row["home_team"] or not row["away_team"] or row["home_team"] == row["away_team"]:
                    raise ValueError(f"Equipos no válidos fixture_id={fid}")
                matches[fid] = row
                count[row["competition"]] += 1
    expected_files = 45 if dataset == "BBETS_DATA" else 6
    minimum_rows = 15000 if dataset == "BBETS_DATA" else 1700
    if files_seen != expected_files or len(matches) < minimum_rows:
        raise ValueError(
            f"{dataset} incompleto: {files_seen} CSV de fixtures y {len(matches)} filas. "
            f"Esperados: {expected_files} CSV y >= {minimum_rows} filas."
        )
    return matches, dict(count)


def existing_hashes(table):
    hashes = {}
    page = 1000
    offset = 0
    while True:
        params = urllib.parse.urlencode({
            "select": "fixture_id,row_hash",
            "order": "fixture_id.asc",
            "limit": page, "offset": offset,
        })
        rows = request(f"/rest/v1/{table}?{params}")
        for row in rows:
            hashes[int(row["fixture_id"])] = row["row_hash"]
        if len(rows) < page:
            break
        offset += len(rows)
    return hashes


def log_start(dataset, digest, byte_count):
    row = request("/rest/v1/karubet_data_imports?select=id",
                  "POST", {"dataset": dataset, "file_sha256": digest,
                           "file_bytes": byte_count, "status": "running"},
                  extra_headers={"Prefer": "return=representation"})
    if not row or not row[0].get("id"):
        raise RuntimeError("No se pudo iniciar registro de importación")
    return row[0]["id"]


def log_finish(run_id, status, rows_seen, rows_changed, details):
    payload = {
        "status": status, "completed_at": datetime.now(timezone.utc).isoformat(),
        "rows_seen": rows_seen, "rows_changed": rows_changed,
        "diagnostics": details,
    }
    request(f"/rest/v1/karubet_data_imports?id=eq.{run_id}",
            "PATCH", payload)


def import_dataset(dataset):
    filename, table = ARCHIVES[dataset]
    print(f"KARUBET: leyendo ZIP privado {dataset}...")
    content, zipped = read_private_zip(filename)
    digest = hashlib.sha256(content).hexdigest()
    matches, by_league = parse_matches(zipped, dataset)
    print(f"KARUBET: CSV verificados, {len(matches)} partidos, {len(by_league)} ligas.")
    # El importe no se basa sólo en el nombre del archivo: cada row_hash permite
    # detectar nuevas filas o cambios a goles, xG, fechas y status.
    old = existing_hashes(table)
    delta = [row for fid, row in matches.items()
             if old.get(fid) != row["row_hash"]]
    print(f"KARUBET: {len(delta)} filas nuevas/modificadas; {len(matches)-len(delta)} sin cambio.")
    run = log_start(dataset, digest, len(content))
    changed = 0
    try:
        for index in range(0, len(delta), 120):
            batch = delta[index:index + 120]
            request(f"/rest/v1/{table}?on_conflict=fixture_id", "POST", batch,
                    extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"})
            changed += len(batch)
            if changed % 2400 == 0:
                print(f"KARUBET: {dataset} {changed}/{len(delta)} actualizadas.", flush=True)
        log_finish(run, "completed", len(matches), changed, {
            "competition_counts": by_league,
            "unchanged": len(matches) - changed,
            "zip_sha256": digest,
        })
    except Exception as error:
        try:
            log_finish(run, "error", len(matches), changed,
                       {"reason": type(error).__name__, "partial_changes": changed})
        except Exception:
            pass
        raise
    print(f"KARUBET: importación {dataset} completada, cambios={changed}")


def main():
    parser = argparse.ArgumentParser(description="BBETS actualización semanal incremental")
    parser.add_argument("--dataset", choices=["all", "BBETS_DATA", "BBETS_2026"],
                        default="all")
    args = parser.parse_args()
    endpoint()
    selected = list(ARCHIVES) if args.dataset == "all" else [args.dataset]
    for ds in selected:
        import_dataset(ds)
    print("Finalizado. Modelos PA/Quasi PA aún NO reentrenados.")


if __name__ == "__main__":
    main()
