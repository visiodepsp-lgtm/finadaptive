"""KARUBET: endpoint privado para despachar el recolector GitHub Actions.

La web es pública de lectura; SOLO el POST está protegido por una clave de
captura privada y un token GitHub guardados en variables de Vercel.
"""
from __future__ import annotations

import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler

WORKFLOW = "karubet-1x2.yml"
REPO = "visiodepsp-lgtm/finadaptive"
GITHUB_API = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}"
COOLDOWN_SECONDS = 8 * 60


def ready() -> bool:
    return bool(os.getenv("GITHUB_ACTIONS_TOKEN", "").strip()
                and len(os.getenv("KARUBET_CAPTURE_KEY", "")) >= 24)


def authorized(provided: str) -> bool:
    expected = os.getenv("KARUBET_CAPTURE_KEY", "")
    return len(expected) >= 24 and hmac.compare_digest(provided, expected)


def recent_run_wait(runs: dict, now: datetime | None = None) -> int:
    """Segundos hasta siguiente envío, si GitHub ya inició captura no fallida."""
    now = now or datetime.now(timezone.utc)
    for run in runs.get("workflow_runs", [])[:20]:
        if run.get("event") not in ("workflow_dispatch", "schedule"):
            continue
        if run.get("conclusion") in ("failure", "cancelled", "skipped"):
            continue
        try:
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            seconds = (now - created).total_seconds()
        except (ValueError, KeyError, TypeError):
            continue
        if 0 <= seconds < COOLDOWN_SECONDS:
            return max(1, int(COOLDOWN_SECONDS - seconds) + 1)
    return 0


def github_api(token: str, method: str, url: str, payload: dict | None = None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "User-Agent": "karubet-market-capture",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=16) as response:
        if method == "POST":
            if response.status != 204:
                raise RuntimeError("GitHub no aceptó el dispatch.")
            return {}
        return json.loads(response.read().decode("utf-8"))


class handler(BaseHTTPRequestHandler):
    def send(self, code: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if urllib.parse.urlsplit(self.path).path != "/api/capture":
            self.send(404, {"error": "NO_EXISTE"})
            return
        self.send(200, {
            "ready": ready(),
            "message": "Captura disponible." if ready()
                       else "Configura GITHUB_ACTIONS_TOKEN y KARUBET_CAPTURE_KEY en el proyecto finadaptive-web de Vercel.",
        })

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/api/capture":
            self.send(404, {"error": "NO_EXISTE"})
            return
        if not ready():
            self.send(503, {"error": "CONFIGURACION_PENDIENTE",
                            "message": "Faltan GITHUB_ACTIONS_TOKEN o KARUBET_CAPTURE_KEY en Vercel."})
            return
        origin = self.headers.get("Origin", "")
        host = self.headers.get("Host", "")
        if origin:
            parsed = urllib.parse.urlsplit(origin)
            if parsed.scheme != "https" or parsed.netloc.lower() != host.lower():
                self.send(403, {"error": "ORIGEN_INVALIDO", "message": "Origen no autorizado."})
                return
        provided = self.headers.get("X-Karubet-Capture-Key", "")
        if not authorized(provided):
            self.send(401, {"error": "ACCESO_RECHAZADO", "message": "Clave de captura incorrecta."})
            return
        if self.headers.get("Content-Length", "0") not in ("", "0"):
            self.send(400, {"error": "CUERPO_NO_ADMITIDO", "message": "Solicitud sin cuerpo requerida."})
            return
        token = os.environ["GITHUB_ACTIONS_TOKEN"].strip()
        try:
            runs = github_api(token, "GET", GITHUB_API + "/runs?per_page=20")
            wait = recent_run_wait(runs)
            if wait:
                self.send(429, {"error": "CAPTURA_RECIENTE",
                                "message": "GitHub ya tiene una captura reciente.",
                                "retry_after_seconds": wait})
                return
            github_api(token, "POST", GITHUB_API + "/dispatches",
                       {"ref": "main", "inputs": {"save_to_db": "true"}})
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                message = "GitHub rechazó el token o falta permiso Actions: Read and write."
            elif error.code == 404:
                message = "No se encontró el workflow autorizado en GitHub."
            else:
                message = "GitHub devolvió HTTP " + str(error.code) + "."
            self.send(502, {"error": "GITHUB_NO_DISPONIBLE", "message": message})
            return
        except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError):
            self.send(502, {"error": "GITHUB_SIN_RESPUESTA",
                            "message": "No se pudo confirmar la solicitud en GitHub."})
            return
        self.send(202, {
            "status": "queued",
            "message": "Solicitud enviada a GitHub Actions; aún no es una captura completada.",
            "workflow_url": "https://github.com/" + REPO + "/actions/workflows/" + WORKFLOW,
        })

    def do_OPTIONS(self):
        self.send(405, {"error": "METODO_NO_ADMITIDO"})

    def log_message(self, fmt, *args):
        # No imprimir cabeceras, claves ni payloads.
        pass
