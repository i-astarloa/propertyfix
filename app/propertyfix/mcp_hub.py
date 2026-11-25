"""Cliente MCP: lanza los servidores MCP como subprocesos (stdio) y enruta las llamadas.

Cada llamada pasa por aquí, así que en un solo punto se aplican:
- el control de permisos (qué agente puede usar qué herramienta),
- la aprobación humana obligatoria para acciones con efectos externos,
- el detector de bucles, el tiempo máximo y un reintento,
- el respaldo: si la plataforma real de Google falla, se repite en modo simulado,
- y el registro de la traza (herramienta, permiso, duración, resultado).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from . import barandillas, db
from .config import APP_DIR, CUENTA_SANDBOX, TIMEOUT_MCP_S

SERVIDORES = {
    "gmail": "mcp_servers.gmail_server",
    "calendar": "mcp_servers.calendar_server",
    "drive": "mcp_servers.drive_server",
    "sheets": "mcp_servers.sheets_server",
    "directorio": "mcp_servers.directorio_server",
}


class ErrorMCP(Exception):
    pass


class HubMCP:
    def __init__(self, incidencia_id: str, usuario: str, token_google: str | None, aprobado: bool = False) -> None:
        self.iid = incidencia_id
        self.usuario = usuario
        self.token_google = token_google
        self.aprobado = aprobado
        self.pila = AsyncExitStack()
        self.sesiones: dict[tuple[str, bool], ClientSession] = {}
        self.bucles = barandillas.DetectorBucles()

    async def __aenter__(self) -> "HubMCP":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.pila.aclose()

    def _entorno(self, simulado: bool) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(APP_DIR)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PROPERTYFIX_USUARIO"] = self.usuario
        env["PROPERTYFIX_DESTINATARIOS"] = ",".join({self.usuario, CUENTA_SANDBOX})
        env["GOOGLE_TOKEN_FILE"] = "" if simulado or not self.token_google else self.token_google
        env["PROPERTYFIX_FORZAR_SIMULADO"] = "1" if simulado else "0"
        return env

    async def _sesion(self, servidor: str, simulado: bool) -> ClientSession:
        clave = (servidor, simulado)
        if clave not in self.sesiones:
            params = StdioServerParameters(command=sys.executable, args=["-m", SERVIDORES[servidor]],
                                           env=self._entorno(simulado), cwd=str(APP_DIR))
            lectura, escritura = await self.pila.enter_async_context(stdio_client(params))
            sesion = await self.pila.enter_async_context(ClientSession(lectura, escritura))
            await asyncio.wait_for(sesion.initialize(), timeout=TIMEOUT_MCP_S)
            self.sesiones[clave] = sesion
        return self.sesiones[clave]

    async def llamar(self, agente: str, herramienta: str, args: dict) -> dict:
        """Llama a `servidor.herramienta` en nombre de `agente`, aplicando todas las barandillas."""
        permiso = barandillas.permiso(agente, herramienta)
        if permiso is None:
            db.registrar_traza(self.iid, agente, "barandilla", herramienta, "denegado",
                               f"El agente {agente} no tiene permiso para {herramienta}", ok=False)
            raise ErrorMCP(f"Permiso denegado: {agente} → {herramienta}")
        if herramienta in barandillas.REQUIEREN_APROBACION and not self.aprobado:
            db.registrar_traza(self.iid, agente, "barandilla", herramienta, permiso,
                               "Bloqueado: falta la aprobación humana", ok=False)
            raise ErrorMCP(f"{herramienta} requiere aprobación humana")
        if self.bucles.registrar(herramienta, args):
            db.registrar_traza(self.iid, agente, "barandilla", herramienta, permiso,
                               "Bucle detectado: misma llamada repetida 3 veces", ok=False)
            raise ErrorMCP("Bucle detectado")

        servidor, nombre = herramienta.split(".", 1)
        es_google = servidor in {"gmail", "calendar", "drive", "sheets"}
        simulado = not (es_google and self.token_google)
        ultimo_error = ""
        for intento in range(2):
            t0 = time.perf_counter()
            try:
                sesion = await self._sesion(servidor, simulado)
                r = await asyncio.wait_for(sesion.call_tool(nombre, args), timeout=TIMEOUT_MCP_S)
                texto = "".join(getattr(c, "text", "") for c in r.content)
                datos = json.loads(texto) if texto.strip().startswith("{") else {"ok": not r.isError, "texto": texto}
                if r.isError:
                    raise ErrorMCP(texto[:300])
                ms = int((time.perf_counter() - t0) * 1000)
                modo = datos.get("modo", "local")
                db.registrar_traza(self.iid, agente, "mcp", herramienta, permiso,
                                   f"[{modo}] args={_resumen(args)} → {_resumen(datos)}", ms=ms, ok=datos.get("ok", True))
                return datos
            except Exception as e:
                ms = int((time.perf_counter() - t0) * 1000)
                ultimo_error = f"{type(e).__name__}: {e}"
                db.registrar_traza(self.iid, agente, "mcp", herramienta, permiso,
                                   f"Fallo (intento {intento + 1}, {'simulado' if simulado else 'real'}): {ultimo_error}",
                                   ms=ms, ok=False)
                if es_google and not simulado:
                    # Respaldo: la plataforma real ha fallado → se continúa en modo simulado.
                    simulado = True
                    db.registrar_traza(self.iid, agente, "info", herramienta, permiso,
                                       "Respaldo activado: se repite la llamada en modo simulado")
        raise ErrorMCP(ultimo_error)


def _resumen(obj: Any, n: int = 350) -> str:
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + "…"
