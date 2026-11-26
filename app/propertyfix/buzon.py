"""Tarea en bucle: revisa periódicamente la bandeja de Gmail buscando incidencias nuevas.

- Qué se repite: una búsqueda en Gmail (MCP, lectura) de correos no procesados cuyo asunto
  mencione una incidencia o avería; cada correo nuevo crea una incidencia y lanza al orquestador.
- Cada cuánto: INTERVALO_BUZON_S segundos (120 por defecto; 0 la desactiva).
- Coste de cada vuelta: 1 llamada MCP y 0 tokens si no hay correos nuevos; con correos, el coste
  de procesar cada incidencia.
- Condición de parada / freno: como máximo 5 correos por vuelta; si fallan 3 vueltas seguidas,
  el bucle se pausa (cortacircuitos) y se muestra en la web; también se detiene al cerrar la app.
"""
from __future__ import annotations

import asyncio
import threading
import time

from . import db
from .agents import orquestador
from .config import INTERVALO_BUZON_S
from .mcp_hub import HubMCP

# Se excluyen los correos que envía la propia app (confirmaciones y órdenes de trabajo): si no,
# el buzón los leería como incidencias nuevas y se crearía un bucle (pasó en las pruebas).
CONSULTA = ("newer_than:7d -from:me -subject:\"Reparación reservada\" -subject:\"Orden de trabajo\" "
            "(subject:incidencia OR subject:averia OR subject:avería OR subject:reparacion OR subject:reparación)")
PREFIJOS_PROPIOS = ("reparación reservada", "[orden de trabajo")
MAX_POR_VUELTA = 5
MAX_FALLOS = 3

estado = {"activo": INTERVALO_BUZON_S > 0, "ultima_vuelta": None, "vueltas": 0, "fallos_seguidos": 0,
          "creadas": 0, "pausado": False, "mensaje": "", "intervalo_s": INTERVALO_BUZON_S}
usuarios_activos: set[str] = set()


async def revisar(usuario: str) -> int:
    creadas = 0
    async with HubMCP("BUZON", usuario, orquestador.token_de(usuario)) as hub:
        r = await hub.llamar("buzon", "gmail.buscar_emails", {"consulta": CONSULTA, "maximo": MAX_POR_VUELTA})
        for c in r.get("correos", []):
            clave = f"{usuario}:{c['id']}"
            if db.correo_procesado(clave):
                continue
            # Segunda barrera contra el bucle: ni correos propios ni respuestas a ellos.
            asunto = c.get("asunto", "").lower().removeprefix("re: ").removeprefix("fwd: ")
            if asunto.startswith(PREFIJOS_PROPIOS) or usuario.lower() in c.get("de", "").lower():
                db.marcar_correo(clave, usuario)
                continue
            db.marcar_correo(clave, usuario)
            await hub.llamar("buzon", "gmail.marcar_procesado", {"email_id": c["id"]})
            iid = db.crear_incidencia(usuario=usuario, origen="email",
                                      descripcion=f"{c.get('asunto', '')}\n\n{c.get('texto', '')}".strip()[:3000],
                                      contacto_nombre=c.get("de", ""), telefono="", direccion="", cp="", municipio="",
                                      franja="completa")
            db.registrar_traza(iid, "buzon", "info", detalle=f"Incidencia creada desde el correo de {c.get('de', '')}")
            orquestador.lanzar(orquestador.fase_analisis, iid)
            creadas += 1
    return creadas


def _bucle() -> None:
    while estado["activo"]:
        if not estado["pausado"]:
            try:
                for u in list(usuarios_activos):
                    estado["creadas"] += asyncio.run(revisar(u))
                estado["fallos_seguidos"] = 0
                estado["mensaje"] = "OK"
            except Exception as e:
                estado["fallos_seguidos"] += 1
                estado["mensaje"] = f"{type(e).__name__}: {e}"
                if estado["fallos_seguidos"] >= MAX_FALLOS:
                    estado["pausado"] = True
                    estado["mensaje"] = f"Pausado tras {MAX_FALLOS} fallos seguidos: {estado['mensaje']}"
            estado["vueltas"] += 1
            estado["ultima_vuelta"] = time.strftime("%H:%M:%S")
        time.sleep(max(estado["intervalo_s"], 10))


def arrancar() -> None:
    if estado["activo"]:
        threading.Thread(target=_bucle, daemon=True, name="buzon").start()


def reanudar() -> None:
    estado.update(pausado=False, fallos_seguidos=0, mensaje="Reanudado")
