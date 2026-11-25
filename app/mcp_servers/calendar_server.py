"""Servidor MCP de Google Calendar: consultar ocupación y crear la cita de la reparación."""
from __future__ import annotations

import random
import uuid
from datetime import date, datetime, time, timedelta

from mcp.server.fastmcp import FastMCP

from mcp_servers.comun import guardar_mock, leer_mock, modo, servicio

mcp = FastMCP("calendar")
ZONA = "Europe/Madrid"


def _eventos_simulados() -> list[dict]:
    """Calendario simulado del usuario. La primera vez se rellena con compromisos ficticios
    (semilla 42) para que la búsqueda de hueco tenga algo que esquivar."""
    eventos = leer_mock("calendar_eventos", None)
    if eventos is None:
        rnd = random.Random(42)
        eventos = []
        hoy = date.today()
        for d in range(1, 15):
            dia = hoy + timedelta(days=d)
            if dia.weekday() >= 5:
                continue
            for _ in range(rnd.choice([0, 1, 1, 2])):
                h = rnd.choice([9, 10, 11, 12, 16, 17, 18])
                ini = datetime.combine(dia, time(h))
                eventos.append({"id": f"sim-{uuid.uuid4().hex[:8]}", "titulo": rnd.choice(
                    ["Reunión de trabajo", "Médico", "Clase", "Llamada con banco", "Comida familiar"]),
                    "inicio": ini.isoformat(), "fin": (ini + timedelta(hours=1)).isoformat(), "propio": False})
        guardar_mock("calendar_eventos", eventos)
    return eventos


@mcp.tool()
def consultar_ocupacion(desde: str, hasta: str) -> dict:
    """Devuelve los intervalos ocupados del calendario principal del usuario. Permiso: LECTURA.

    Args:
        desde: fecha-hora ISO de inicio (p. ej. 2026-11-26T08:00:00).
        hasta: fecha-hora ISO de fin.
    """
    if modo() == "real":
        cuerpo = {"timeMin": _rfc(desde), "timeMax": _rfc(hasta), "timeZone": ZONA, "items": [{"id": "primary"}]}
        r = servicio("calendar", "v3").freebusy().query(body=cuerpo).execute()
        ocupado = r["calendars"]["primary"].get("busy", [])
        return {"ok": True, "modo": "real", "ocupado": [{"inicio": b["start"], "fin": b["end"]} for b in ocupado]}
    ini, fin = datetime.fromisoformat(desde), datetime.fromisoformat(hasta)
    ocupado = [{"inicio": e["inicio"], "fin": e["fin"]} for e in _eventos_simulados()
               if datetime.fromisoformat(e["fin"]) > ini and datetime.fromisoformat(e["inicio"]) < fin]
    return {"ok": True, "modo": "simulado", "ocupado": ocupado}


@mcp.tool()
def crear_evento(titulo: str, inicio: str, fin: str, descripcion: str = "", ubicacion: str = "") -> dict:
    """Crea un evento en el calendario principal del usuario. Permiso: ESCRITURA (requiere aprobación).

    Args:
        titulo: título del evento.
        inicio: fecha-hora ISO de inicio (hora de Madrid).
        fin: fecha-hora ISO de fin (hora de Madrid).
        descripcion: descripción del evento.
        ubicacion: dirección de la visita.
    """
    if modo() == "real":
        cuerpo = {"summary": titulo, "description": descripcion, "location": ubicacion,
                  "start": {"dateTime": inicio, "timeZone": ZONA}, "end": {"dateTime": fin, "timeZone": ZONA},
                  "reminders": {"useDefault": True}}
        r = servicio("calendar", "v3").events().insert(calendarId="primary", body=cuerpo).execute()
        return {"ok": True, "modo": "real", "id": r["id"], "enlace": r.get("htmlLink", "")}
    eventos = _eventos_simulados()
    eid = f"sim-{uuid.uuid4().hex[:8]}"
    eventos.append({"id": eid, "titulo": titulo, "inicio": inicio, "fin": fin,
                    "descripcion": descripcion, "ubicacion": ubicacion, "propio": True})
    guardar_mock("calendar_eventos", eventos)
    return {"ok": True, "modo": "simulado", "id": eid, "enlace": "/demo/google#calendario"}


def _rfc(iso: str) -> str:
    """Añade la zona horaria de Madrid si la fecha no la lleva."""
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        from zoneinfo import ZoneInfo
        dt = dt.replace(tzinfo=ZoneInfo(ZONA))
    return dt.isoformat()


if __name__ == "__main__":
    mcp.run()
