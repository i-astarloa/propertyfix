"""Lógica de negocio determinista: distancias, presupuestos, puntuación y agenda.

Esta parte NO la decide el modelo de lenguaje: los precios salen siempre de las tarifas de la
base de proveedores. El modelo elige entre opciones ya calculadas y justifica su elección, pero
no puede inventar ni modificar una cifra (barandilla contra alucinaciones y contra inyección).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache

from .config import DATA_DIR

IVA = 0.21
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
FRANJAS = {"mañana": (time(9), time(14)), "tarde": (time(15), time(20)), "completa": (time(9), time(20))}
DURACION_VISITA_H = 2

# Pesos de la puntuación (suman 1). En urgencias pesa más la rapidez.
PESOS_NORMAL = {"precio": 0.40, "valoracion": 0.25, "distancia": 0.20, "rapidez": 0.15}
PESOS_URGENTE = {"precio": 0.25, "valoracion": 0.20, "distancia": 0.20, "rapidez": 0.35}


@lru_cache
def proveedores() -> list[dict]:
    return json.loads((DATA_DIR / "proveedores.json").read_text(encoding="utf-8"))


@lru_cache
def catalogo() -> dict:
    return json.loads((DATA_DIR / "catalogo.json").read_text(encoding="utf-8"))


@lru_cache
def zonas() -> dict:
    return json.loads((DATA_DIR / "zonas.json").read_text(encoding="utf-8"))


def trabajo(trabajo_id: str) -> tuple[str, dict] | None:
    """Devuelve (tipo, datos_trabajo) para un id del catálogo."""
    for tipo, info in catalogo().items():
        if trabajo_id in info["trabajos"]:
            return tipo, info["trabajos"][trabajo_id]
    return None


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en línea recta (fórmula de Haversine)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def geolocalizar_por_tabla(cp: str | None, municipio: str | None) -> tuple[float, float, str] | None:
    """Respaldo sin internet: coordenadas aproximadas por código postal o municipio/distrito."""
    cp = (cp or "").strip()
    mun = (municipio or "").strip().lower()
    for nombre, z in zonas().items():
        if cp and cp in z["cps"]:
            return z["lat"], z["lon"], f"tabla de códigos postales ({nombre})"
    for nombre, z in zonas().items():
        if mun and (mun == nombre.lower() or mun in nombre.lower() or nombre.lower() in mun):
            return z["lat"], z["lon"], f"tabla de municipios ({nombre})"
    if cp.startswith("280"):
        z = zonas()["Centro"]
        return z["lat"], z["lon"], "aproximación: Madrid capital"
    return None


@dataclass
class Presupuesto:
    proveedor_id: str
    mano_obra: float
    desplazamiento: float
    materiales: float
    recargo_urgencia: float
    base_imponible: float
    iva: float
    total: float

    def a_dict(self) -> dict:
        return self.__dict__.copy()


def presupuestar(prov: dict, trabajo_id: str, urgente: bool) -> Presupuesto | None:
    info = trabajo(trabajo_id)
    if info is None:
        return None
    _, t = info
    mano_obra = t["horas"] * prov["tarifa_hora"]
    materiales = t["materiales"] * (1 + prov["margen_materiales"])
    recargo = mano_obra * prov["recargo_urgencia"] if (urgente and prov["urgencias_24h"]) else 0.0
    base = mano_obra + prov["desplazamiento"] + materiales + recargo
    iva = base * IVA
    r = lambda x: round(x, 2)
    return Presupuesto(prov["id"], r(mano_obra), r(prov["desplazamiento"]), r(materiales), r(recargo), r(base), r(iva), r(base + iva))


def primer_hueco_proveedor(prov: dict, desde: date, urgente: bool) -> date:
    """Primer día en que el proveedor puede ir, según su antelación y días laborables."""
    antelacion = 0 if (urgente and prov["urgencias_24h"]) else prov["antelacion_dias"]
    d = desde + timedelta(days=antelacion)
    for _ in range(14):
        if DIAS[d.weekday()] in prov["dias"]:
            return d
        d += timedelta(days=1)
    return d


def comparar(trabajo_id: str, lat: float, lon: float, urgencia: str, hoy: date | None = None) -> list[dict]:
    """Calcula presupuesto, distancia, rapidez y una puntuación 0–100 para cada proveedor apto.

    Apto = tiene la especialidad. Los que están fuera de su radio de servicio se incluyen solo
    si no hay al menos 3 dentro de radio, y llevan una penalización.
    """
    info = trabajo(trabajo_id)
    if info is None:
        return []
    tipo, _ = info
    hoy = hoy or date.today()
    urgente = urgencia in ("alta", "urgente")
    filas = []
    for p in proveedores():
        if tipo not in p["especialidades"]:
            continue
        dist = distancia_km(lat, lon, p["lat"], p["lon"])
        pres = presupuestar(p, trabajo_id, urgente)
        dia = primer_hueco_proveedor(p, hoy + timedelta(days=1), urgente)
        filas.append({
            "proveedor_id": p["id"], "nombre": p["nombre"], "zona": p["zona"],
            "distancia_km": dist, "dentro_radio": dist <= p["radio_km"],
            "valoracion": p["valoracion"], "num_resenas": p["num_resenas"],
            "garantia_meses": p["garantia_meses"], "urgencias_24h": p["urgencias_24h"],
            "primer_dia": dia.isoformat(), "dias_espera": (dia - hoy).days,
            "presupuesto": pres.a_dict(),
        })
    dentro = [f for f in filas if f["dentro_radio"]]
    if len(dentro) >= 3:
        filas = dentro
    if not filas:
        return []

    pesos = PESOS_URGENTE if urgente else PESOS_NORMAL
    precios = [f["presupuesto"]["total"] for f in filas]
    dists = [f["distancia_km"] for f in filas]
    esperas = [f["dias_espera"] for f in filas]

    def norm_inv(x: float, xs: list[float]) -> float:  # 1 = el mejor (el más bajo)
        lo, hi = min(xs), max(xs)
        return 1.0 if hi == lo else 1 - (x - lo) / (hi - lo)

    for f in filas:
        comp = {
            "precio": norm_inv(f["presupuesto"]["total"], precios),
            "valoracion": (f["valoracion"] - 3.0) / 2.0,
            "distancia": norm_inv(f["distancia_km"], dists),
            "rapidez": norm_inv(f["dias_espera"], esperas),
        }
        punt = sum(pesos[k] * comp[k] for k in pesos) * 100
        if not f["dentro_radio"]:
            punt -= 15
        f["componentes"] = {k: round(v, 3) for k, v in comp.items()}
        f["puntuacion"] = round(max(punt, 0), 1)
    filas.sort(key=lambda f: f["puntuacion"], reverse=True)
    for i, f in enumerate(filas, start=1):
        f["ranking"] = i
    return filas


def proponer_cita(prov: dict, ocupado: list[tuple[datetime, datetime]], desde: date,
                  franja_cliente: str, urgente: bool) -> tuple[datetime, datetime] | None:
    """Primer hueco de DURACION_VISITA_H horas compatible con proveedor, cliente y su calendario."""
    dia = primer_hueco_proveedor(prov, desde, urgente)
    ini_p, fin_p = FRANJAS[prov["franja"]]
    ini_c, fin_c = FRANJAS.get(franja_cliente, FRANJAS["completa"])
    ini, fin = max(ini_p, ini_c), min(fin_p, fin_c)
    if ini >= fin:  # franjas incompatibles: se respeta la del proveedor
        ini, fin = ini_p, fin_p
    for _ in range(21):
        if DIAS[dia.weekday()] in prov["dias"]:
            h = datetime.combine(dia, ini)
            while h + timedelta(hours=DURACION_VISITA_H) <= datetime.combine(dia, fin):
                f = h + timedelta(hours=DURACION_VISITA_H)
                if all(not (h < o_fin and f > o_ini) for o_ini, o_fin in ocupado):
                    return h, f
                h += timedelta(hours=1)
        dia += timedelta(days=1)
    return None
