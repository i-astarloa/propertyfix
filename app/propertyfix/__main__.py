"""Arranque: python -m propertyfix  →  abre http://localhost:8000 en el navegador."""
from __future__ import annotations

import threading
import webbrowser

import uvicorn

from . import db, llm
from .config import OLLAMA_MODEL, PUERTO, URL_BASE, google_disponible


def main() -> None:
    db.iniciar()
    ok, texto = llm.disponible()
    print("\n  PropertyFix")
    print(f"  · Web:     {URL_BASE}")
    print(f"  · Modelo:  {texto}" + ("" if ok else f"  → instala Ollama y ejecuta: ollama pull {OLLAMA_MODEL}"))
    print(f"  · Google:  {'inicio de sesión con Google disponible' if google_disponible() else 'modo demo (sin credentials.json)'}")
    print("  Pulsa Ctrl+C para detener.\n")
    threading.Timer(1.5, lambda: webbrowser.open(URL_BASE)).start()
    uvicorn.run("propertyfix.web:app", host="127.0.0.1", port=PUERTO, log_level="warning")


if __name__ == "__main__":
    main()
