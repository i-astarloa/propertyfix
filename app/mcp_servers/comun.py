"""Utilidades compartidas por los servidores MCP de Google.

Cada servidor funciona en uno de dos modos:
- real: usa la API de Google con el token OAuth del usuario que ha iniciado sesión
  (ruta en la variable de entorno GOOGLE_TOKEN_FILE).
- simulado: guarda todo en ficheros JSON locales (runtime/mock_google/), para que la app
  funcione sin credenciales o cuando la plataforma real falla.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from propertyfix.config import MOCK_DIR, SCOPES_GOOGLE

_lock = threading.Lock()


def modo() -> str:
    """'real' si hay token de Google válido para este proceso; si no, 'simulado'."""
    if os.getenv("PROPERTYFIX_FORZAR_SIMULADO") == "1":
        return "simulado"
    ruta = os.getenv("GOOGLE_TOKEN_FILE", "")
    return "real" if ruta and Path(ruta).exists() else "simulado"


def credenciales():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    ruta = os.environ["GOOGLE_TOKEN_FILE"]
    creds = Credentials.from_authorized_user_file(ruta, SCOPES_GOOGLE)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        Path(ruta).write_text(creds.to_json(), encoding="utf-8")
    return creds


def servicio(nombre: str, version: str):
    from googleapiclient.discovery import build

    return build(nombre, version, credentials=credenciales(), cache_discovery=False)


def usuario() -> str:
    return os.getenv("PROPERTYFIX_USUARIO", "demo@propertyfix.local")


def _ruta_mock(nombre: str, usr: str | None = None) -> Path:
    seguro = "".join(c if c.isalnum() else "_" for c in (usr or usuario()))
    return MOCK_DIR / f"{nombre}__{seguro}.json"


def leer_mock(nombre: str, defecto: Any, usr: str | None = None) -> Any:
    ruta = _ruta_mock(nombre, usr)
    with _lock:
        if not ruta.exists():
            return defecto
        return json.loads(ruta.read_text(encoding="utf-8"))


def guardar_mock(nombre: str, datos: Any, usr: str | None = None) -> None:
    ruta = _ruta_mock(nombre, usr)
    with _lock:
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def destinatarios_permitidos() -> set[str]:
    """Lista blanca de destinatarios: el propio usuario y la bandeja sandbox del proyecto."""
    crudo = os.getenv("PROPERTYFIX_DESTINATARIOS", "")
    return {d.strip().lower() for d in crudo.split(",") if d.strip()}
