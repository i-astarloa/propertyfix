"""Modelo financiero de PropertyFix (reproducible).

Entradas MEDIDAS (salen de ficheros generados por scripts del repositorio):
  - app/data/evaluacion/consumo_medido.json  → tokens por incidencia (medir_consumo.py)
  - docs/coste_construccion/coste_construccion.json → coste de construir la app (leer_usage_claude_code.py)

Todo lo demás es una ESTIMACIÓN de negocio y está en el diccionario SUPUESTOS con su fuente o razón.
Uso:  python docs/modelo_financiero/modelo_financiero.py   → escribe resultados.json y resultados.md
"""
from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONSUMO = json.loads((RAIZ / "app/data/evaluacion/consumo_medido.json").read_text(encoding="utf-8"))
CONSTRUCCION = json.loads((RAIZ / "docs/coste_construccion/coste_construccion.json").read_text(encoding="utf-8"))

SUPUESTOS = {
    # --- Demanda ----------------------------------------------------------------------------------
    "incidencias_por_inmueble_año": (3.3, "Hemlane 2024: 3,30 solicitudes de mantenimiento por vivienda y año (EE. UU.)"),
    # --- Precios y mezcla de planes (sin IVA) -------------------------------------------------------
    "planes": ({"Starter": (49, 25, 18, 0.50), "Professional": (149, 100, 70, 0.35), "Business": (349, 300, 210, 0.15)},
               "precio €/mes, inmuebles máximos, inmuebles usados de media (~70 %), cuota de clientes"),
    # --- Servidor del modelo abierto -----------------------------------------------------------------
    "gpu_servidor_eur_mes": (214.0, "Hetzner GEX45: RTX PRO 4000 Blackwell SFF, 24 GB VRAM, 214 €/mes (hetzner.com)"),
    "gpu_alta_eur": (209.0, "cuota de alta única del GEX45"),
    "gpu_vram_gb": (24, "VRAM del GEX45"),
    "modelo_vram_gb": (2.5, "qwen2.5:3b cuantizado Q4 ocupa 1,9 GB en disco + caché KV (medido en Ollama: 1,9 GB)"),
    "gpu_incidencias_por_minuto": (10, "capacidad conservadora en GPU (vLLM/Ollama con lotes): ~6 s por incidencia y concurrencia baja; ESTIMACIÓN a validar en el piloto"),
    # --- Otros costes de infraestructura (€/mes) -----------------------------------------------------
    "infra_web_bd_eur_mes": (25.0, "VPS para la web y la base de datos"),
    "infra_copias_monitor_eur_mes": (30.0, "copias de seguridad y monitorización"),
    "geocodificacion_eur_mes": (49.0, "geocodificador comercial (la API pública de Nominatim no admite uso intensivo)"),
    "dominio_correo_eur_mes": (15.0, "dominio y correo corporativo"),
    # --- Costes variables por cliente ----------------------------------------------------------------
    "pasarela_pago_pct": (0.015, "comisión típica de tarjeta europea"),
    "pasarela_pago_fijo_eur": (0.25, "fijo por cobro"),
    "soporte_eur_cliente_mes": (3.0, "tiempo de soporte prorrateado"),
    # --- Equipo y otros fijos (€/mes, coste empresa) ---------------------------------------------------
    "fundadores": (2, "dos fundadores a tiempo completo desde el mes 1"),
    "coste_fundador_eur_mes": (2800.0, "salario modesto de fundador con Seguridad Social"),
    "contratacion_ventas_mes": (13, "comercial/éxito de cliente desde el mes 13"),
    "coste_ventas_eur_mes": (2800.0, ""),
    "contratacion_dev_mes": (25, "desarrollador desde el mes 25"),
    "coste_dev_eur_mes": (3500.0, ""),
    "legal_gestoria_eur_mes": (300.0, "gestoría, RGPD, seguros"),
    "marketing_eur_mes": (1000.0, "marketing digital + presencia en congresos de administradores de fincas"),
    # --- Inversión inicial (antes del primer euro) -----------------------------------------------------
    "meses_pre_ingresos": (4, "4 meses para pasar del MVP a producto vendible (multiempresa, seguridad, verificación de Google)"),
    "verificacion_google_eur": (3000.0, "evaluación de seguridad CASA exigida por Google para permisos restringidos de Gmail"),
    "alta_legal_eur": (2000.0, "constitución, contratos SaaS, encargo de tratamiento RGPD"),
    "marketing_lanzamiento_eur": (4000.0, "piloto con administradores de fincas"),
    # --- Crecimiento de clientes ----------------------------------------------------------------------
    "altas_mes": ({1: 0, 5: 3, 6: 4, 13: 10, 25: 18}, "altas netas por mes a partir de ese mes (5 = lanzamiento con pilotos)"),
    "churn_mensual": (0.02, "2 % de bajas al mes, típico de SaaS para pymes"),
    # --- Inversor ------------------------------------------------------------------------------------
    "inversion_solicitada_eur": (110000.0, "ronda pre-semilla: cubre la necesidad máxima de caja del modelo con un margen de ~15 %"),
    "participacion_inversor": (0.20, "20 % del capital"),
    "multiplo_arr": (4.0, "valoración a 3 años = 4 × ingresos recurrentes anuales (múltiplo prudente de SaaS vertical)"),
    "usd_eur": (CONSTRUCCION["tipo_cambio_usd_eur"], "tipo de cambio usado para valorar los tokens de construcción"),
}
S = {k: v[0] for k, v in SUPUESTOS.items()}


def mezcla() -> dict:
    planes = S["planes"]
    arpu = sum(p * cuota for p, _, _, cuota in planes.values())
    inmuebles = sum(usados * cuota for _, _, usados, cuota in planes.values())
    return {"arpu_eur_mes": round(arpu, 2), "inmuebles_medios": round(inmuebles, 1),
            "incidencias_cliente_mes": round(inmuebles * S["incidencias_por_inmueble_año"] / 12, 2)}


def consumo_cliente(m: dict) -> dict:
    ent, sal = CONSUMO["tokens_entrada_medios"], CONSUMO["tokens_salida_medios"]
    n = m["incidencias_cliente_mes"]
    cap_incidencias_mes = S["gpu_incidencias_por_minuto"] * 60 * 24 * 30
    return {
        "sesion": "una incidencia procesada de punta a punta (análisis + reserva)",
        "tokens_entrada_sesion": ent, "tokens_salida_sesion": sal,
        "sesiones_cliente_mes": n,
        "tokens_entrada_cliente_mes": round(ent * n), "tokens_salida_cliente_mes": round(sal * n),
        "fraccion_cacheable": CONSUMO["fraccion_cacheable_entrada"],
        "capacidad_gpu_incidencias_mes": cap_incidencias_mes,
        "clientes_por_gpu": int(cap_incidencias_mes / n),
        "coste_marginal_gpu_cliente_mes": round(S["gpu_servidor_eur_mes"] * n / cap_incidencias_mes, 4),
        # Comparación: el mismo consumo con un modelo cerrado por API (precios de lista, USD → EUR).
        "coste_api_haiku_5_5_cliente_mes": round(n * (ent * 0.10 + sal * 0.50) / 1e6 * S["usd_eur"], 4),
        "coste_api_opus_5_5_cliente_mes": round(n * (ent * 4.0 + sal * 20.0) / 1e6 * S["usd_eur"], 4),
    }


def coste_variable_cliente(arpu: float) -> float:
    return arpu * S["pasarela_pago_pct"] + S["pasarela_pago_fijo_eur"] + S["soporte_eur_cliente_mes"]


def infra_mes() -> float:
    return (S["gpu_servidor_eur_mes"] + S["infra_web_bd_eur_mes"] + S["infra_copias_monitor_eur_mes"]
            + S["geocodificacion_eur_mes"] + S["dominio_correo_eur_mes"])


def fijos_mes(mes: int) -> float:
    equipo = S["fundadores"] * S["coste_fundador_eur_mes"]
    if mes >= S["contratacion_ventas_mes"]:
        equipo += S["coste_ventas_eur_mes"]
    if mes >= S["contratacion_dev_mes"]:
        equipo += S["coste_dev_eur_mes"]
    return equipo + infra_mes() + S["legal_gestoria_eur_mes"] + S["marketing_eur_mes"]


def altas(mes: int) -> int:
    v = 0
    for desde, n in sorted(S["altas_mes"].items()):
        if mes >= desde:
            v = n
    return v


def proyeccion(m: dict, gpu_factor: float = 1.0) -> list[dict]:
    arpu, clientes, caja = m["arpu_eur_mes"], 0.0, 0.0
    construccion = CONSTRUCCION["total_eur"]
    filas = []
    for mes in range(1, 37):
        clientes = clientes * (1 - S["churn_mensual"]) + altas(mes)
        ingresos = clientes * arpu
        var = clientes * coste_variable_cliente(arpu)
        fijos = fijos_mes(mes) + S["gpu_servidor_eur_mes"] * (gpu_factor - 1)
        unicos = 0.0
        if mes == 1:
            unicos = (construccion + S["gpu_alta_eur"] + S["verificacion_google_eur"] + S["alta_legal_eur"]
                      + S["marketing_lanzamiento_eur"])
        flujo = ingresos - var - fijos - unicos
        caja += flujo
        filas.append({"mes": mes, "clientes": round(clientes, 1), "ingresos": round(ingresos), "costes_variables": round(var),
                      "costes_fijos": round(fijos), "unicos": round(unicos), "flujo": round(flujo), "caja_acumulada": round(caja)})
    return filas


def resumen(m: dict, filas: list[dict]) -> dict:
    arpu = m["arpu_eur_mes"]
    contrib = arpu - coste_variable_cliente(arpu)
    pre = [f for f in filas if f["mes"] <= S["meses_pre_ingresos"]]
    inversion_inicial = -sum(f["flujo"] for f in pre)
    minimo_caja = min(f["caja_acumulada"] for f in filas)
    mes_equilibrio = next((f["mes"] for f in filas if f["flujo"] >= 0 and f["mes"] > S["meses_pre_ingresos"]), None)
    mes_recuperacion = next((f["mes"] for f in filas if f["caja_acumulada"] >= 0 and f["mes"] > 1), None)
    arr_36 = filas[-1]["ingresos"] * 12
    valor_empresa = arr_36 * S["multiplo_arr"]
    valor_inversor = valor_empresa * S["participacion_inversor"]
    return {
        "arpu_eur_mes": arpu,
        "coste_variable_cliente_mes": round(coste_variable_cliente(arpu), 2),
        "margen_contribucion_cliente_mes": round(contrib, 2),
        "margen_bruto_pct": round(contrib / arpu, 3),
        "costes_fijos_mes_año1": round(fijos_mes(5)), "costes_fijos_mes_año2": round(fijos_mes(13)),
        "costes_fijos_mes_año3": round(fijos_mes(25)),
        "infraestructura_mes": round(infra_mes()),
        "clientes_equilibrio_año1": round(fijos_mes(5) / contrib, 1),
        "clientes_equilibrio_año3": round(fijos_mes(25) / contrib, 1),
        "inversion_antes_primer_ingreso": round(inversion_inicial),
        "necesidad_maxima_caja": round(-minimo_caja),
        "mes_equilibrio_operativo": mes_equilibrio,
        "mes_recuperacion_caja": mes_recuperacion,
        "clientes_mes_12": filas[11]["clientes"], "clientes_mes_24": filas[23]["clientes"], "clientes_mes_36": filas[35]["clientes"],
        "ingresos_año1": sum(f["ingresos"] for f in filas[:12]), "ingresos_año2": sum(f["ingresos"] for f in filas[12:24]),
        "ingresos_año3": sum(f["ingresos"] for f in filas[24:36]),
        "flujo_año1": sum(f["flujo"] for f in filas[:12]), "flujo_año2": sum(f["flujo"] for f in filas[12:24]),
        "flujo_año3": sum(f["flujo"] for f in filas[24:36]),
        "caja_mes_36": filas[-1]["caja_acumulada"],
        "arr_mes_36": arr_36, "valor_empresa_mes_36": round(valor_empresa),
        "valor_participacion_inversor_mes_36": round(valor_inversor),
        "multiplo_inversor": round(valor_inversor / S["inversion_solicitada_eur"], 1),
        "roi_inversor_pct": round((valor_inversor - S["inversion_solicitada_eur"]) / S["inversion_solicitada_eur"] * 100),
        "coste_construccion_eur": CONSTRUCCION["total_eur"],
    }


def main() -> None:
    m = mezcla()
    c = consumo_cliente(m)
    base = proyeccion(m)
    r = resumen(m, base)
    gpu50 = resumen(m, proyeccion(m, gpu_factor=1.5))
    salida = {"mezcla": m, "consumo": c, "resumen": r,
              "sensibilidad_gpu_mas_50": {k: gpu50[k] for k in ("mes_equilibrio_operativo", "mes_recuperacion_caja",
                                                                  "necesidad_maxima_caja", "caja_mes_36")},
              "proyeccion": base,
              "supuestos": {k: {"valor": v[0] if not isinstance(v[0], dict) else {str(a): b for a, b in v[0].items()},
                                "fuente": v[1]} for k, v in SUPUESTOS.items()}}
    d = Path(__file__).parent
    (d / "resultados.json").write_text(json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"mezcla": m, "consumo": c, "resumen": r, "sensibilidad_gpu_mas_50": salida["sensibilidad_gpu_mas_50"]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
