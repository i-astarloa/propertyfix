"""Configuración central: rutas, variables de entorno y modo de funcionamiento."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent          # carpeta app/
DATA_DIR = APP_DIR / "data"
RUNTIME_DIR = APP_DIR / "runtime"                          # datos de ejecución (no se suben a GitHub)
TOKENS_DIR = RUNTIME_DIR / "tokens"
MOCK_DIR = RUNTIME_DIR / "mock_google"
DOCS_DIR = RUNTIME_DIR / "documentos"
DB_PATH = RUNTIME_DIR / "propertyfix.db"
CREDENCIALES_GOOGLE = APP_DIR / "credentials.json"          # cliente OAuth de Google (no se sube)

load_dotenv(APP_DIR / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
PUERTO = int(os.getenv("PROPERTYFIX_PORT", "8000"))
URL_BASE = f"http://localhost:{PUERTO}"

# Barandillas
MAX_TOKENS_POR_INCIDENCIA = int(os.getenv("MAX_TOKENS_PER_INCIDENT", "20000"))
TIMEOUT_LLM_S = float(os.getenv("TIMEOUT_LLM_S", "180"))
TIMEOUT_MCP_S = float(os.getenv("TIMEOUT_MCP_S", "45"))
UMBRAL_GASTO_REFORZADO = float(os.getenv("UMBRAL_GASTO_REFORZADO", "1000"))  # € con IVA

# Cuenta de Google del proyecto: los correos dirigidos a proveedores (ficticios) se
# redirigen a esta bandeja ("sandbox de proveedores") para que nunca salgan a terceros.
CUENTA_SANDBOX = os.getenv("GOOGLE_ACCOUNT", "proyectofinaldeeplearning@gmail.com")

# Tarea en bucle: revisar la bandeja de entrada cada N segundos (0 = desactivada)
INTERVALO_BUZON_S = int(os.getenv("INTERVALO_BUZON_S", "120"))

SCOPES_GOOGLE = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.freebusy",
    "https://www.googleapis.com/auth/drive.file",
]

for d in (RUNTIME_DIR, TOKENS_DIR, MOCK_DIR, DOCS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def google_disponible() -> bool:
    """True si hay un cliente OAuth configurado (credentials.json)."""
    return CREDENCIALES_GOOGLE.exists()
