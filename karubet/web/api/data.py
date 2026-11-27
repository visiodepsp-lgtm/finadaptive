"""KARUBET 7.0 — read-only public match API for Vercel.

Credentials never reach the browser or a static HTML file.
Data source: private Supabase tables through server-side sb_secret_ API key.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler


class BackendDiagnostic(RuntimeError):
    """Diagnóstico público sin exponer claves, consultas ni datos sensibles."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def get_json(table: str, params: dict) -> list:
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    secret = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    u = urllib.parse.urlparse(base)
    if u.scheme != "https" or not u.hostname or not u.hostname.endswith(".supabase.co"):
        raise BackendDiagnostic(
            "SUPABASE_URL_INVALIDA",
            "Revisa SUPABASE_URL en Vercel: debe ser la URL HTTPS del proyecto KARUBET, sin comillas.",
        )
    if not secret.startswith("sb_secret_"):
        raise BackendDiagnostic(
            "SUPABASE_SECRET_KEY_INVALIDA",
            "La clave privada SUPABASE_SECRET_KEY en Vercel debe comenzar por sb_secret_.",
        )
    if table not in ("karubet_fixtures_2026", "karubet_model_outputs",
                     "karubet_odds_1x2", "karubet_fixture_odds_links",
                     "karubet_fixture_context_original"):
        raise ValueError("Tabla no autorizada")
    url = base + "/rest/v1/" + table + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "apikey": secret, "Accept": "application/json",
        "User-Agent": "karubet-market-centre-7.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # El código HTTP basta para diagnosticar; nunca mostrar cuerpos ni cabeceras.
        if error.code in (401, 403):
            raise BackendDiagnostic(
                "SUPABASE_ACCESO_RECHAZADO",
                "Supabase rechazó la clave privada (HTTP " + str(error.code) +
                "). Revisa SUPABASE_SECRET_KEY y el proyecto KARUBET en Vercel.",
            ) from None
        if error.code == 404:
            raise BackendDiagnostic(
                "SUPABASE_API_NO_DISPONIBLE",
                "La API de Supabase devolvió HTTP 404. Revisa SUPABASE_URL y Data API.",
            ) from None
        raise BackendDiagnostic(
            "SUPABASE_ERROR_HTTP",
            "Supabase devolvió HTTP " + str(error.code) + ". Revisa Runtime Logs en Vercel.",
        ) from None
    except urllib.error.URLError:
        raise BackendDiagnostic(
            "SUPABASE_SIN_CONEXION",
            "El servidor no pudo establecer conexión con Supabase. Revisa URL y logs.",
        ) from None


def fixtures(query: dict) -> dict:
    now = datetime.now(timezone.utc)
    days = max(1, min(int(query.get("days", ["90"])[0]), 210))
    limit = max(10, min(int(query.get("limit", ["250"])[0]), 350))
    offset = max(0, min(int(query.get("offset", ["0"])[0]), 2000))
    future = get_json("karubet_fixtures_2026", {
        "select": "fixture_id,competition,home_team,away_team,kickoff_at,status,phase",
        "kickoff_at": "gte." + now.isoformat(timespec="seconds"),
        "order": "kickoff_at.asc", "limit": str(limit), "offset": str(offset),
    })
    before = now + timedelta(days=days)
    future = [row for row in future if parse_time(row.get("kickoff_at")) <= before]
    ids = [str(int(row["fixture_id"])) for row in future]
    predictions: dict = {}
    for start in range(0, len(ids), 80):
        part = get_json("karubet_model_outputs", {
            "select": "fixture_id,model_version,generated_at,data_cutoff_at,probabilities,metrics",
            "fixture_id": "in.(" + ",".join(ids[start:start + 80]) + ")",
            "order": "generated_at.desc",
            "limit": "900",
        })
        for item in part:
            predictions.setdefault(int(item["fixture_id"]), item)
    for row in future:
        row["model"] = predictions.get(int(row["fixture_id"]))
    return {"items": future, "count": len(future), "model_count": sum(bool(r["model"]) for r in future),
            "asof": now.isoformat(timespec="seconds"), "days": days,
            "offset": offset, "page_full": len(future) == limit}


def parse_time(value: str | None) -> datetime:
    try:
        if value is None:
            return datetime.max.replace(tzinfo=timezone.utc)
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.max.replace(tzinfo=timezone.utc)


def markets() -> dict:
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=4)).isoformat(timespec="seconds")
    rows = get_json("karubet_odds_1x2", {
        "select": "id,league_code,home_team,away_team,kickoff_at,source_url,captured_at,"
                  "odd_home,odd_draw,odd_away,market_p_home,market_p_draw,market_p_away,quality_flags",
        "captured_at": "gte." + since, "order": "captured_at.desc", "limit": "1000",
    })
    latest = {}
    for row in rows:
        key = (row["league_code"], row["home_team"], row["away_team"], row["kickoff_at"])
        latest.setdefault(key, row)
    records = sorted(latest.values(), key=lambda row: row["kickoff_at"] or "9999")
    return {"items": records, "count": len(records), "asof": now.isoformat(timespec="seconds"),
            "source": "Apuesta Total", "sample_limit": len(rows) == 1000}


def history(query: dict) -> dict:
    league = query.get("league", [""])[0].strip()
    home = query.get("home", [""])[0].strip()
    away = query.get("away", [""])[0].strip()
    kickoff = query.get("kickoff", [""])[0].strip()
    if not re.fullmatch(r"[0-9]{1,6}", league) or not home or not away:
        raise ValueError("Faltan datos del mercado")
    if any(len(x) > 160 for x in (home, away, kickoff)):
        raise ValueError("Dato excesivamente largo")
    p = {
        "select": "id,captured_at,kickoff_at,odd_home,odd_draw,odd_away,"
                  "market_p_home,market_p_draw,market_p_away",
        "league_code": "eq." + league,
        "home_team": "eq." + home,
        "away_team": "eq." + away,
        "order": "captured_at.asc", "limit": "1000",
    }
    if kickoff and kickoff != "null":
        p["kickoff_at"] = "eq." + kickoff
    rows = get_json("karubet_odds_1x2", p)
    return {"items": rows, "count": len(rows), "truncated": len(rows) >= 1000}



def contexts(query: dict) -> dict:
    """Recupera SOLO el contexto histórico original de fixtures concretos.

    No modifica probabilidades ni crea estadísticas: son observaciones
    procedentes de KARUBET Match Centre 6.3 con fecha de corte 2026-11-22.
    La lista de IDs es limitada para evitar descargas sin restricción.
    """
    raw = query.get("ids", [""])[0].strip()
    if not re.fullmatch(r"[0-9]{1,15}(?:,[0-9]{1,15}){0,79}", raw):
        raise ValueError("Se requieren entre 1 y 80 fixture_id numéricos")
    ids = list(dict.fromkeys(raw.split(",")))
    rows = get_json("karubet_fixture_context_original", {
        "select": "fixture_id,source_snapshot_date,context",
        "fixture_id": "in.(" + ",".join(ids) + ")",
        "limit": "80",
    })
    return {
        "items": rows, "count": len(rows),
        "source": "KARUBET Match Centre 6.3 · copia histórica original",
        "snapshot_date": "2026-11-22",
    }


def linked(query: dict) -> dict:
    fixture_id = query.get("fixture_id", [""])[0]
    if not re.fullmatch(r"[0-9]{1,15}", fixture_id):
        raise ValueError("fixture_id inválido")
    items = get_json("karubet_fixture_odds_links", {
        "select": "odds_league_code,odds_home_team,odds_away_team",
        "fixture_id": "eq." + fixture_id, "reviewed": "eq.true", "limit": "4",
    })
    return {"items": items, "linked": bool(items)}


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "public, s-maxage=30, stale-while-revalidate=90")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        # API pública y estrictamente de solo lectura: sin token de acceso.
        # La clave sb_secret_ sigue siendo exclusivamente una variable del servidor.
        if not os.getenv("SUPABASE_SECRET_KEY", "").strip():
            self._send(503, {"error":"BACKEND_NO_CONFIGURADO",
                             "message":"Supabase no está configurado en el servidor."})
            return
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        kind = query.get("kind", ["fixtures"])[0]
        try:
            if kind == "fixtures":
                result = fixtures(query)
            elif kind == "markets":
                result = markets()
            elif kind == "history":
                result = history(query)
            elif kind == "linked":
                result = linked(query)
            elif kind == "contexts":
                result = contexts(query)
            else:
                self._send(400, {"error": "TIPO_INVALIDO"})
                return
        except ValueError as exc:
            self._send(400, {"error": "PARAMETROS_INVALIDOS", "message": str(exc)})
            return
        except BackendDiagnostic as exc:
            self._send(502, {"error": exc.code, "message": str(exc)})
            return
        except Exception as exc:
            # Sólo registramos tipo de excepción, jamás claves o datos del request.
            print("KARUBET_API: error inesperado " + type(exc).__name__)
            self._send(502, {"error": "LECTURA_NO_DISPONIBLE",
                             "message": "Error interno de lectura. Revisa Runtime Logs de Vercel."})
            return
        self._send(200, result)

    def do_OPTIONS(self):
        self._send(405, {"error": "METODO_NO_ADMITIDO"})

    def log_message(self, fmt, *args):
        # Don't log headers or secret values.
        pass
