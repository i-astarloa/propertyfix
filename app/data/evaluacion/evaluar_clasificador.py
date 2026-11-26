"""Evaluación del agente clasificador sobre casos anotados a mano.

Mide el acierto de categoría y de trabajo de cuatro variantes con los mismos casos:
  - reglas:      solo el detector de palabras clave (sin modelo).
  - v1_antiguo:  clasificador v1 (un paso, 33 trabajos) con el catálogo antiguo, tal como estaba
                 desplegado cuando apareció el fallo del lavavajillas.
  - v1_nuevo:    el mismo v1 con el catálogo ampliado (para separar el efecto del catálogo).
  - v2:          clasificador actual (dos pasos + verificador + «no es avería»).

Modelo: el configurado en OLLAMA_MODEL (por defecto qwen2.5:3b), temperature=0 y seed=42.
Uso (desde app/):  .venv\\Scripts\\python data\\evaluacion\\evaluar_clasificador.py [variantes...]
Escribe resultados en data/evaluacion/resultados_clasificador.json y docs/evaluacion_clasificador.md.
"""
from __future__ import annotations

import asyncio
import copy
import json
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(Path(__file__).parent))

from propertyfix import db, dominio  # noqa: E402
from propertyfix.agents import clasificador as v2  # noqa: E402
from propertyfix.config import OLLAMA_MODEL  # noqa: E402

import clasificador_v1 as v1  # noqa: E402

DIR = Path(__file__).parent
CONJUNTOS = {
    # Desarrollo: casos vistos al diseñar el léxico y los prompts (su cifra es optimista).
    "desarrollo": json.loads((DIR / "casos_clasificacion.json").read_text(encoding="utf-8")),
    # Ciego: escritos después de congelar léxico y prompts, con otro vocabulario. Es la cifra que vale.
    "ciego": json.loads((DIR / "casos_ciegos.json").read_text(encoding="utf-8")),
}
NUEVOS = {"lavavajillas", "atasco_inodoro"}  # trabajos añadidos al catálogo el 26/11


def catalogo_mcp(antiguo: bool) -> dict:
    """Catálogo en el mismo formato que devuelve la herramienta MCP directorio.catalogo_trabajos."""
    cat = {t: {"nombre": c["nombre"], "trabajos": {k: v["descripcion"] for k, v in c["trabajos"].items()}}
           for t, c in dominio.catalogo().items()}
    if antiguo:
        cat = copy.deepcopy(cat)
        for c in cat.values():
            for k in NUEVOS:
                c["trabajos"].pop(k, None)
    return cat


class HubFalso:
    """Sustituye al hub MCP: devuelve el catálogo sin lanzar subprocesos."""

    def __init__(self, cat: dict) -> None:
        self.cat = cat

    async def llamar(self, agente: str, herramienta: str, args: dict) -> dict:
        return {"ok": True, "catalogo": self.cat}


def clasificar(variante: str, iid: str, texto: str) -> tuple[str | None, str | None]:
    if variante == "reglas":
        puntos = v2.puntuar_lexico(texto)
        trabajo, _ = v2.mejor_lexico(puntos)
        return (dominio.trabajo(trabajo)[0] if trabajo else "no_es_averia"), trabajo
    if variante.startswith("v1"):
        c = asyncio.run(v1.clasificar(HubFalso(catalogo_mcp(variante == "v1_antiguo")), iid, texto))
        return c["tipo"], c["trabajo_id"]
    c = v2.clasificar_texto(iid, texto, catalogo_mcp(False))
    return c["tipo"], c["trabajo_id"]


def evaluar(variante: str, conjunto: str) -> dict:
    CASOS = CONJUNTOS[conjunto]
    filas = []
    for caso in CASOS:
        iid = f"EVAL-{variante}-{caso['id']:03d}"
        db.borrar_traza(iid)  # repetir una evaluación no debe sumar tokens de la ejecución anterior
        t0 = time.perf_counter()
        tipo, trabajo = clasificar(variante, iid, caso["texto"])
        seg = time.perf_counter() - t0
        traza = [t for t in db.traza(iid) if t["tipo"] == "llm"]
        filas.append({"id": caso["id"], "esperado": f"{caso['tipo']}/{caso['trabajo']}", "obtenido": f"{tipo}/{trabajo}",
                      "tipo_ok": tipo == caso["tipo"],
                      "trabajo_ok": (trabajo == caso["trabajo"]) if caso["trabajo"] else tipo == "no_es_averia",
                      "tokens_entrada": sum(t["tokens_entrada"] for t in traza),
                      "tokens_salida": sum(t["tokens_salida"] for t in traza), "segundos": round(seg, 1)})
        print(f"  [{variante}] caso {caso['id']:2d}: {'OK ' if filas[-1]['trabajo_ok'] else 'MAL'} "
              f"esperado {filas[-1]['esperado']:40s} obtenido {filas[-1]['obtenido']}", flush=True)
    n = len(filas)
    fuera = [f for f, c in zip(filas, CASOS) if c["tipo"] == "no_es_averia"]
    return {"variante": variante, "casos": n,
            "acierto_tipo": round(sum(f["tipo_ok"] for f in filas) / n, 3),
            "acierto_trabajo": round(sum(f["trabajo_ok"] for f in filas) / n, 3),
            "fuera_de_ambito_detectados": f"{sum(f['tipo_ok'] for f in fuera)}/{len(fuera)}",
            "tokens_entrada_medios": round(sum(f["tokens_entrada"] for f in filas) / n),
            "tokens_salida_medios": round(sum(f["tokens_salida"] for f in filas) / n),
            "segundos_medios": round(sum(f["segundos"] for f in filas) / n, 1), "detalle": filas}


def main() -> None:
    db.iniciar()
    variantes = sys.argv[1:] or ["reglas", "v1_antiguo", "v2"]
    ruta = DIR / "resultados_clasificador.json"
    resultados = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    resultados = {k: v for k, v in resultados.items() if ":" in k}  # descarta formatos antiguos
    for conjunto in CONJUNTOS:
        for v in variantes:
            print(f"\n== {conjunto} · {v} ==", flush=True)
            r = evaluar(v, conjunto)
            r["modelo"] = OLLAMA_MODEL
            resultados[f"{conjunto}:{v}"] = r
            ruta.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    escribir_informe(resultados)


def escribir_informe(res: dict) -> None:
    nombres = {"reglas": "Solo palabras clave (sin modelo)", "v1_antiguo": "v1 · un paso, catálogo antiguo (lo desplegado)",
               "v1_nuevo": "v1 · un paso, catálogo ampliado", "v2": "**v2 · dos pasos + verificador (actual)**"}
    lineas = ["# Evaluación del agente clasificador", "",
              "Generado por `app/data/evaluacion/evaluar_clasificador.py`. Modelo `qwen2.5:3b` en Ollama, temperature 0, "
              "seed 42. Cifras **medidas** y reproducibles ejecutando el script.", "",
              "- **Conjunto de desarrollo** (`casos_clasificacion.json`): casos que se vieron al diseñar el léxico y los "
              "prompts. Su acierto es **optimista** (sesgo de haber visto el examen).",
              "- **Conjunto ciego** (`casos_ciegos.json`): escrito después de congelar léxico y prompts, con otro "
              "vocabulario. **Es la cifra que se defiende.**", ""]
    for conjunto, casos in CONJUNTOS.items():
        claves = [v for v in ["reglas", "v1_antiguo", "v1_nuevo", "v2"] if f"{conjunto}:{v}" in res]
        if not claves:
            continue
        lineas += [f"## Conjunto {conjunto} ({len(casos)} casos)", "",
                   "| Variante | Acierto categoría | Acierto trabajo | «No es avería» detectados | Tokens entrada / caso | Tokens salida / caso | Segundos / caso |",
                   "|---|---|---|---|---|---|---|"]
        for v in claves:
            r = res[f"{conjunto}:{v}"]
            lineas.append(f"| {nombres[v]} | {r['acierto_tipo']:.0%} | {r['acierto_trabajo']:.0%} | {r['fuera_de_ambito_detectados']} "
                          f"| {r['tokens_entrada_medios']} | {r['tokens_salida_medios']} | {r['segundos_medios']} |")
        if f"{conjunto}:v2" in res:
            fallos = [f for f in res[f"{conjunto}:v2"]["detalle"] if not f["trabajo_ok"]]
            lineas += ["", "Fallos de v2:", ""] + ([f"- Caso {f['id']}: esperado `{f['esperado']}`, obtenido `{f['obtenido']}`"
                                                    for f in fallos] or ["- Ninguno."])
        lineas.append("")
    (APP.parent / "docs" / "evaluacion_clasificador.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\nInforme escrito en docs/evaluacion_clasificador.md")


if __name__ == "__main__":
    main()
