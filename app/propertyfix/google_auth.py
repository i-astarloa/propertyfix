"""Inicio de sesión con Google (OAuth 2.0) y almacenamiento local del token del usuario.

El usuario concede a PropertyFix permiso para enviar correos, leer su bandeja, consultar y crear
eventos en su calendario y crear ficheros propios en su Drive. El token se guarda solo en
app/runtime/tokens/ (excluido de GitHub) y lo usan los servidores MCP de ese usuario.
"""
from __future__ import annotations

import os

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from .config import CREDENCIALES_GOOGLE, SCOPES_GOOGLE, TOKENS_DIR, URL_BASE

# OAuth sobre http://localhost (sin TLS) solo se permite en local.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
REDIRECCION = f"{URL_BASE}/auth/callback"


def _flujo(state: str | None = None) -> Flow:
    return Flow.from_client_secrets_file(str(CREDENCIALES_GOOGLE), scopes=SCOPES_GOOGLE, state=state,
                                         redirect_uri=REDIRECCION, autogenerate_code_verifier=True)


def url_autorizacion() -> tuple[str, str, str]:
    flujo = _flujo()
    url, state = flujo.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    return url, state, flujo.code_verifier


def completar(url_respuesta: str, state: str, verificador: str) -> dict:
    flujo = _flujo(state)
    flujo.code_verifier = verificador
    flujo.fetch_token(authorization_response=url_respuesta)
    creds = flujo.credentials
    info = build("oauth2", "v2", credentials=creds, cache_discovery=False).userinfo().get().execute()
    email = info["email"].lower()
    ruta = TOKENS_DIR / f"{''.join(c if c.isalnum() else '_' for c in email)}.json"
    ruta.write_text(creds.to_json(), encoding="utf-8")
    return {"email": email, "nombre": info.get("given_name") or info.get("name") or email}
