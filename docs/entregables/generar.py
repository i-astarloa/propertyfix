"""Genera memoria.pdf y slides.pdf a partir de las plantillas y de los resultados medidos.

Ninguna cifra se escribe a mano en los documentos: todas salen de estos ficheros, generados por
scripts del repositorio.
  - app/data/evaluacion/resultados_clasificador.json  (evaluar_clasificador.py)
  - app/data/evaluacion/consumo_medido.json           (medir_consumo.py)
  - docs/coste_construccion/coste_construccion.json   (leer_usage_claude_code.py)
  - docs/modelo_financiero/resultados.json            (modelo_financiero.py)
  - app/runtime/propertyfix.db (traza de la sesión real con Google, incidencia TRAZA_ID)

Uso (desde la raíz):  app\\.venv\\Scripts\\python docs\\entregables\\generar.py
Requiere Microsoft Edge o Google Chrome para imprimir a PDF.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

RAIZ = Path(__file__).resolve().parents[2]
DIR = Path(__file__).parent
TRAZA_ID = "INC-0005"  # primera incidencia procesada con Gmail/Calendar/Drive/Sheets reales (25/11/2026)

NAVEGADORES = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
               r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
               r"C:\Program Files\Google\Chrome\Application\chrome.exe",
               "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "chromium"]


def cargar(ruta: str) -> dict:
    return json.loads((RAIZ / ruta).read_text(encoding="utf-8"))


def traza_real() -> list[dict]:
    con = sqlite3.connect(RAIZ / "app/runtime/propertyfix.db")
    con.row_factory = sqlite3.Row
    filas = [dict(r) for r in con.execute("SELECT * FROM traza WHERE incidencia = ? ORDER BY id", (TRAZA_ID,))]
    return filas


def num(x, dec: int = 0) -> str:
    if x is None:
        return "—"
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def eur(x, dec: int = 0) -> str:
    return f"{num(x, dec)} €"


def pct(x, dec: int = 0) -> str:
    return f"{num(x * 100, dec)} %"


def imprimir_pdf(html: Path, pdf: Path, apaisado: bool = False) -> None:
    exe = next((n for n in NAVEGADORES if Path(n).exists() or shutil.which(n)), None)
    if not exe:
        raise SystemExit("No se encontró Edge ni Chrome para generar el PDF")
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=8000", f"--print-to-pdf={pdf}", html.resolve().as_uri()],
                   check=True, capture_output=True)
    print(f"  {pdf.relative_to(RAIZ)}  ({pdf.stat().st_size // 1024} KB)")


def main() -> None:
    ctx = {
        "ev": cargar("app/data/evaluacion/resultados_clasificador.json"),
        "cons": cargar("app/data/evaluacion/consumo_medido.json"),
        "build": cargar("docs/coste_construccion/coste_construccion.json"),
        "fin": cargar("docs/modelo_financiero/resultados.json"),
        "traza": traza_real(), "traza_id": TRAZA_ID,
        "fecha": date.today().strftime("%d/%m/%Y"),
    }
    env = Environment(loader=FileSystemLoader(DIR), autoescape=True)
    env.filters.update(num=num, eur=eur, pct=pct)
    env.globals.update(pct=pct, num=num, eur=eur)
    for nombre in ("memoria", "slides"):
        html = DIR / f"{nombre}.html"
        html.write_text(env.get_template(f"{nombre}.html.j2").render(**ctx), encoding="utf-8")
        imprimir_pdf(html, RAIZ / f"{nombre}.pdf")


if __name__ == "__main__":
    main()
