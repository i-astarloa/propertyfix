"""Tests de los servidores MCP en modo simulado y de las barandillas del hub."""
import asyncio

import pytest

from propertyfix import db
from propertyfix.mcp_hub import ErrorMCP, HubMCP


def _hub(aprobado: bool = False) -> HubMCP:
    db.iniciar()
    return HubMCP("TEST", "test@propertyfix.local", None, aprobado=aprobado)


def test_directorio_compara_por_mcp():
    async def run():
        async with _hub() as hub:
            return await hub.llamar("proveedores", "directorio.comparar_ofertas",
                                    {"trabajo_id": "fuga_tuberia", "lat": 40.46, "lon": -3.69, "urgencia": "media"})
    r = asyncio.run(run())
    assert r["ok"] and r["candidatos"][0]["ranking"] == 1


def test_envio_bloqueado_sin_aprobacion():
    async def run():
        async with _hub(aprobado=False) as hub:
            await hub.llamar("comunicaciones", "gmail.enviar_email",
                             {"para": "test@propertyfix.local", "asunto": "x", "cuerpo_html": "x"})
    with pytest.raises(ErrorMCP, match="aprobación"):
        asyncio.run(run())


def test_permiso_denegado_a_otro_agente():
    async def run():
        async with _hub(aprobado=True) as hub:
            await hub.llamar("clasificador", "gmail.enviar_email",
                             {"para": "test@propertyfix.local", "asunto": "x", "cuerpo_html": "x"})
    with pytest.raises(ErrorMCP, match="Permiso denegado"):
        asyncio.run(run())


def test_lista_blanca_de_destinatarios():
    async def run():
        async with _hub(aprobado=True) as hub:
            return await hub.llamar("comunicaciones", "gmail.enviar_email",
                                    {"para": "atacante@malo.com", "asunto": "x", "cuerpo_html": "x"})
    r = asyncio.run(run())
    assert r["ok"] is False and "lista blanca" in r["error"]
