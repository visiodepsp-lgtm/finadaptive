#!/usr/bin/env python3
"""Archiva la serie de cuotas de todos los partidos iniciados, no solo éxitos."""
import json
import os
import urllib.request
from urllib.parse import urlparse


def run():
    base = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    secret = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    url = urlparse(base)
    if url.scheme != "https" or not url.hostname or not url.hostname.endswith(".supabase.co"):
        raise RuntimeError("SUPABASE_URL inválida")
    if not secret.startswith("sb_secret_"):
        raise RuntimeError("SUPABASE_SECRET_KEY inválida")
    request = urllib.request.Request(
        base + "/rest/v1/rpc/karubet_archive_started_matches",
        data=b"{}", method="POST",
        headers={"apikey": secret, "Content-Type": "application/json",
                 "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        count = json.load(response)
    if not isinstance(count, int) or count < 0:
        raise RuntimeError("Respuesta inesperada al archivar")
    print(f"KARUBET: {count} partidos archivados; snapshots originales conservados.")


if __name__ == "__main__":
    run()
