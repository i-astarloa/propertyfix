"""Agente 3 — Coordinador de proveedores.

Recibe la clasificación y la ubicación del inmueble (no el texto original ni los datos de
contacto). Consulta el directorio por MCP, que calcula los presupuestos con las tarifas reales
de la base; el modelo elige un proveedor entre los candidatos y justifica la elección.
"""
from __future__ import annotations

import json

from .. import db, llm
from ..mcp_hub import HubMCP

AGENTE = "proveedores"

SISTEMA = """Eres el agente coordinador de proveedores de PropertyFix.
Recibes una avería ya clasificada y una tabla de proveedores candidatos con su presupuesto calculado,
distancia, valoración, días de espera y una puntuación orientativa.
Elige el proveedor más adecuado para el cliente y una alternativa. Ten en cuenta:
- Si la urgencia es alta o urgente, prioriza la rapidez y el servicio de urgencias 24h.
- Si no es urgente, prioriza el precio sin sacrificar mucha valoración.
- La puntuación es una referencia: puedes elegir otro si lo justificas.
No inventes cifras: usa solo las de la tabla. Justifica en una o dos frases, en español."""


async def geolocalizar(hub: HubMCP, direccion: str, cp: str, municipio: str) -> dict:
    return await hub.llamar(AGENTE, "directorio.geolocalizar",
                            {"direccion": direccion, "codigo_postal": cp, "municipio": municipio})


async def seleccionar(hub: HubMCP, iid: str, clasificacion: dict, lat: float, lon: float) -> dict:
    r = await hub.llamar(AGENTE, "directorio.comparar_ofertas",
                         {"trabajo_id": clasificacion["trabajo_id"], "lat": lat, "lon": lon,
                          "urgencia": clasificacion["urgencia"]})
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error", "sin candidatos"), "candidatos": []}
    candidatos = r["candidatos"]
    ids = [c["proveedor_id"] for c in candidatos]

    tabla = [{"id": c["proveedor_id"], "nombre": c["nombre"], "total_eur": c["presupuesto"]["total"],
              "distancia_km": c["distancia_km"], "valoracion": c["valoracion"], "dias_espera": c["dias_espera"],
              "urgencias_24h": c["urgencias_24h"], "garantia_meses": c["garantia_meses"], "puntuacion": c["puntuacion"]}
             for c in candidatos]
    usuario = (f"Avería: {clasificacion['trabajo_descripcion']} · urgencia {clasificacion['urgencia']}\n"
               f"Candidatos:\n{json.dumps(tabla, ensure_ascii=False)}")
    esquema = {"type": "object",
               "properties": {"proveedor_id": {"type": "string", "enum": ids},
                              "alternativa_id": {"type": "string", "enum": ids},
                              "justificacion": {"type": "string"}},
               "required": ["proveedor_id", "alternativa_id", "justificacion"]}
    res = llm.chat_json(iid, AGENTE, SISTEMA, usuario, esquema, max_salida=200)

    if res.ok and res.datos.get("proveedor_id") in ids:
        elegido, justif, fuente = res.datos["proveedor_id"], res.datos.get("justificacion", ""), "modelo"
        alternativa = res.datos.get("alternativa_id") if res.datos.get("alternativa_id") in ids else None
    else:
        elegido, fuente = ids[0], "reglas (respaldo)"
        alternativa = ids[1] if len(ids) > 1 else None
        c0 = candidatos[0]
        justif = (f"Mejor puntuación global ({c0['puntuacion']}/100): {c0['presupuesto']['total']} € con IVA, "
                  f"valoración {c0['valoracion']} y a {c0['distancia_km']} km.")
        db.registrar_traza(iid, AGENTE, "info", detalle=f"Respaldo por reglas: {res.error or 'elección no válida'}")
    if alternativa == elegido:
        alternativa = next((i for i in ids if i != elegido), None)

    pos = ids.index(elegido) + 1
    if pos != 1:
        db.registrar_traza(iid, AGENTE, "decision",
                           detalle=f"El agente se aparta del ranking: elige el n.º {pos} ({elegido}). Motivo: {justif}")
    return {"ok": True, "candidatos": candidatos, "elegido": elegido, "alternativa": alternativa,
            "justificacion": justif, "fuente": fuente, "total_aptos": r.get("total_aptos", len(candidatos))}
