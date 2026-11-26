"""Mide el consumo real de PropertyFix por incidencia, de punta a punta.

Procesa N incidencias completas (análisis → propuesta → aprobación → reserva) con el modelo local
(Ollama) y los servidores MCP de Google en modo simulado, para que la medida se pueda reproducir
sin credenciales. Registra por incidencia: tokens de entrada y salida (los que reporta Ollama),
llamadas al modelo, llamadas MCP, segundos de modelo y tiempo total.

También mide la «fracción cacheable»: los tokens de las instrucciones de sistema de cada agente, que
son idénticos en todas las incidencias y que un servidor con caché de prefijos no recalcula.

Uso (desde app/):  .venv\\Scripts\\python data\\evaluacion\\medir_consumo.py [N]
Escribe data/evaluacion/consumo_medido.json
"""
from __future__ import annotations

import asyncio
import json
import statistics as st
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP))

import httpx  # noqa: E402

from propertyfix import db  # noqa: E402
from propertyfix.agents import clasificador, comunicaciones, orquestador, proveedores  # noqa: E402
from propertyfix.config import OLLAMA_MODEL, OLLAMA_URL  # noqa: E402

DIR = Path(__file__).parent
USUARIO = "medicion@propertyfix.local"   # sin token de Google → MCP de Google en modo simulado
DIRECCIONES = [("Calle de Alcalá 120", "28009"), ("Calle de Bravo Murillo 210", "28020"),
               ("Calle de Serrano 45", "28001"), ("Paseo de Extremadura 80", "28011"),
               ("Calle de Arturo Soria 150", "28043")]


def tokens_sistema(sistema: str) -> int:
    """Tokens de un prompt de sistema (con un mensaje de usuario mínimo)."""
    r = httpx.post(f"{OLLAMA_URL}/api/chat", timeout=300, json={
        "model": OLLAMA_MODEL, "stream": False, "keep_alive": "30m",
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": "."}],
        "options": {"num_predict": 1, "temperature": 0, "seed": 42}}).json()
    return r.get("prompt_eval_count", 0)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    db.iniciar()
    casos = [c for c in json.loads((DIR / "casos_ciegos_2.json").read_text(encoding="utf-8"))
             if c["tipo"] != "no_es_averia"][:n]
    filas = []
    for i, caso in enumerate(casos):
        calle, cp = DIRECCIONES[i % len(DIRECCIONES)]
        iid = db.crear_incidencia(usuario=USUARIO, origen="medicion", descripcion=caso["texto"],
                                  contacto_nombre="Medición", telefono="", direccion=calle, cp=cp,
                                  municipio="Madrid", franja="completa")
        t0 = time.perf_counter()
        asyncio.run(orquestador.fase_analisis(iid))
        if db.incidencia(iid)["estado"] == "pendiente_aprobacion":
            asyncio.run(orquestador.fase_reserva(iid))
        total = time.perf_counter() - t0
        inc = db.incidencia(iid)
        filas.append({"incidencia": iid, "caso": caso["id"], "estado_final": inc["estado"],
                      "tokens_entrada": inc["tokens_entrada"], "tokens_salida": inc["tokens_salida"],
                      "llamadas_llm": inc["llamadas_llm"], "llamadas_mcp": inc["llamadas_mcp"],
                      "segundos_modelo": round(inc["segundos_llm"], 1), "segundos_totales": round(total, 1)})
        print(f"{iid} caso {caso['id']}: {inc['estado']:22s} entrada {inc['tokens_entrada']:5d} "
              f"salida {inc['tokens_salida']:4d} llm {inc['llamadas_llm']} mcp {inc['llamadas_mcp']} "
              f"{total:.0f} s", flush=True)

    # Fracción cacheable: instrucciones de sistema que se repiten en todas las incidencias.
    fijos = {
        "clasificador_categoria": tokens_sistema(clasificador.SISTEMA_TIPO),
        "clasificador_trabajo": tokens_sistema(clasificador.SISTEMA_TRABAJO),
        "orquestador": tokens_sistema(orquestador.SISTEMA),
        "proveedores": tokens_sistema(proveedores.SISTEMA),
        "comunicaciones": tokens_sistema(comunicaciones.SISTEMA),
    }
    prefijo_por_incidencia = sum(fijos.values())  # una llamada de cada agente en el flujo normal
    media = lambda k: round(st.mean(f[k] for f in filas), 1)
    resumen = {
        "modelo": OLLAMA_MODEL, "incidencias": len(filas),
        "completadas_hasta_reserva": sum(f["estado_final"] == "reservada" for f in filas),
        "tokens_entrada_medios": media("tokens_entrada"), "tokens_salida_medios": media("tokens_salida"),
        "tokens_entrada_desv": round(st.pstdev(f["tokens_entrada"] for f in filas), 1),
        "llamadas_llm_medias": media("llamadas_llm"), "llamadas_mcp_medias": media("llamadas_mcp"),
        "segundos_modelo_medios": media("segundos_modelo"), "segundos_totales_medios": media("segundos_totales"),
        # La mediana no se deja arrastrar por una incidencia anómala (p. ej. el modelo ocupado por otro proceso).
        "segundos_totales_mediana": round(st.median(f["segundos_totales"] for f in filas), 1),
        "tokens_prefijo_fijo_por_agente": fijos,
        "fraccion_cacheable_entrada": round(prefijo_por_incidencia / st.mean(f["tokens_entrada"] for f in filas), 3),
        "hardware": "portátil de desarrollo: Intel Core i7-1355U, 16 GB RAM, sin GPU dedicada (solo CPU)",
        "detalle": filas,
    }
    (DIR / "consumo_medido.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in resumen.items() if k != "detalle"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
