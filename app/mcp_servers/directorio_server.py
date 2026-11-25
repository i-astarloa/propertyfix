"""Servidor MCP del directorio de proveedores (base de datos local ficticia) y geolocalización.

La geolocalización usa la API pública de OpenStreetMap (Nominatim). Si no responde, se usa una
tabla local de códigos postales y municipios: la app nunca se queda bloqueada por esa API.
"""
from __future__ import annotations

from datetime import date

import httpx
from mcp.server.fastmcp import FastMCP

from propertyfix import dominio

mcp = FastMCP("directorio")
NOMINATIM = "https://nominatim.openstreetmap.org/search"
# Política de uso de Nominatim: identificar la aplicación, máx. 1 petición/segundo.
CABECERAS = {"User-Agent": "PropertyFix-demo-academico/0.1"}


@mcp.tool()
def geolocalizar(direccion: str, codigo_postal: str = "", municipio: str = "") -> dict:
    """Obtiene latitud y longitud de una dirección. Permiso: LECTURA (API externa).

    Args:
        direccion: calle y número.
        codigo_postal: código postal.
        municipio: municipio o distrito.
    """
    consulta = ", ".join(x for x in [direccion, codigo_postal, municipio, "España"] if x)
    try:
        r = httpx.get(NOMINATIM, params={"q": consulta, "format": "json", "limit": 1, "countrycodes": "es"},
                      headers=CABECERAS, timeout=6)
        r.raise_for_status()
        datos = r.json()
        if datos:
            return {"ok": True, "lat": float(datos[0]["lat"]), "lon": float(datos[0]["lon"]),
                    "fuente": "OpenStreetMap (Nominatim)"}
        motivo = "sin resultados en Nominatim"
    except Exception as e:  # caída o lentitud de la API externa
        motivo = f"Nominatim no disponible ({type(e).__name__})"
    t = dominio.geolocalizar_por_tabla(codigo_postal, municipio)
    if t:
        return {"ok": True, "lat": t[0], "lon": t[1], "fuente": f"{t[2]} — {motivo}"}
    z = dominio.zonas()["Centro"]
    return {"ok": True, "lat": z["lat"], "lon": z["lon"], "fuente": f"por defecto: Madrid centro — {motivo}"}


@mcp.tool()
def catalogo_trabajos() -> dict:
    """Devuelve los tipos de avería y los trabajos del catálogo. Permiso: LECTURA."""
    return {"ok": True, "catalogo": {t: {"nombre": c["nombre"], "trabajos": {k: v["descripcion"] for k, v in c["trabajos"].items()}}
                                     for t, c in dominio.catalogo().items()}}


@mcp.tool()
def comparar_ofertas(trabajo_id: str, lat: float, lon: float, urgencia: str = "media") -> dict:
    """Busca proveedores con la especialidad, calcula su presupuesto con sus tarifas y los ordena
    por una puntuación de precio, valoración, distancia y rapidez. Permiso: LECTURA.

    Args:
        trabajo_id: id del trabajo del catálogo (p. ej. fuga_tuberia).
        lat: latitud del inmueble.
        lon: longitud del inmueble.
        urgencia: baja, media, alta o urgente.
    """
    filas = dominio.comparar(trabajo_id, lat, lon, urgencia, hoy=date.today())
    if not filas:
        return {"ok": False, "error": f"No hay proveedores para el trabajo {trabajo_id}"}
    return {"ok": True, "candidatos": filas[:5], "total_aptos": len(filas)}


@mcp.tool()
def ficha_proveedor(proveedor_id: str) -> dict:
    """Devuelve la ficha completa de un proveedor. Permiso: LECTURA."""
    for p in dominio.proveedores():
        if p["id"] == proveedor_id:
            return {"ok": True, "proveedor": p}
    return {"ok": False, "error": f"Proveedor {proveedor_id} no existe"}


if __name__ == "__main__":
    mcp.run()
