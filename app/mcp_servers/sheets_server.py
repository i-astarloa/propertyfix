"""Servidor MCP de Google Sheets: registro histórico de incidencias del gestor.

La hoja «PropertyFix — Registro de incidencias» se crea en el Drive del usuario la primera
vez y se añade una fila por cada cambio de estado (historial auditable fuera de la app).
"""
from __future__ import annotations

import json
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from mcp_servers.comun import guardar_mock, leer_mock, modo, servicio, usuario
from propertyfix.config import RUNTIME_DIR

mcp = FastMCP("sheets")
CABECERA = ["Fecha", "Incidencia", "Estado", "Tipo", "Urgencia", "Dirección", "Proveedor", "Importe (€)", "Cita", "Nota"]


def _id_hoja() -> str:
    """Id de la hoja del usuario; la crea si no existe."""
    ruta = RUNTIME_DIR / "hojas.json"
    hojas = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    if usuario() in hojas:
        return hojas[usuario()]
    s = servicio("sheets", "v4")
    hoja = s.spreadsheets().create(body={"properties": {"title": "PropertyFix — Registro de incidencias"}},
                                   fields="spreadsheetId").execute()
    sid = hoja["spreadsheetId"]
    s.spreadsheets().values().append(spreadsheetId=sid, range="A1", valueInputOption="RAW",
                                     body={"values": [CABECERA]}).execute()
    hojas[usuario()] = sid
    ruta.write_text(json.dumps(hojas, indent=2), encoding="utf-8")
    return sid


@mcp.tool()
def registrar(incidencia: str, estado: str, tipo: str = "", urgencia: str = "", direccion: str = "",
              proveedor: str = "", importe: float = 0.0, cita: str = "", nota: str = "") -> dict:
    """Añade una fila al registro de incidencias. Permiso: ESCRITURA INTERNA.

    Args:
        incidencia: id de la incidencia (p. ej. INC-0003).
        estado: nuevo estado.
        tipo: tipo de avería.
        urgencia: urgencia estimada.
        direccion: dirección del inmueble.
        proveedor: proveedor asignado.
        importe: importe total con IVA.
        cita: fecha y hora de la visita.
        nota: comentario libre.
    """
    fila = [datetime.now().strftime("%Y-%m-%d %H:%M"), incidencia, estado, tipo, urgencia, direccion,
            proveedor, importe, cita, nota]
    if modo() == "real":
        sid = _id_hoja()
        servicio("sheets", "v4").spreadsheets().values().append(
            spreadsheetId=sid, range="A1", valueInputOption="USER_ENTERED", body={"values": [fila]}).execute()
        return {"ok": True, "modo": "real", "hoja": f"https://docs.google.com/spreadsheets/d/{sid}"}
    filas = leer_mock("sheets_registro", [CABECERA])
    filas.append(fila)
    guardar_mock("sheets_registro", filas)
    return {"ok": True, "modo": "simulado", "hoja": "/demo/google#hoja"}


@mcp.tool()
def leer_registro(maximo: int = 50) -> dict:
    """Lee las últimas filas del registro de incidencias. Permiso: LECTURA."""
    if modo() == "real":
        sid = _id_hoja()
        r = servicio("sheets", "v4").spreadsheets().values().get(spreadsheetId=sid, range="A1:J1000").execute()
        filas = r.get("values", [])
    else:
        filas = leer_mock("sheets_registro", [CABECERA])
    return {"ok": True, "modo": modo(), "filas": filas[:1] + filas[1:][-maximo:]}


if __name__ == "__main__":
    mcp.run()
