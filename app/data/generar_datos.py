"""Genera los datos ficticios de PropertyFix (proveedores, catálogo de trabajos, zonas).

Todo es inventado. Las cifras numéricas (tarifas, valoraciones, disponibilidad) salen de
un generador con semilla fija (42), así que ejecutar este script siempre produce los
mismos ficheros. Uso:  python data/generar_datos.py
"""
from __future__ import annotations

import json
import random
import unicodedata
from pathlib import Path

SEMILLA = 42
DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Zonas de la Comunidad de Madrid con coordenadas aproximadas (centro del distrito o municipio).
# Se usan como base de los proveedores y como respaldo de geolocalización por código postal.
# ---------------------------------------------------------------------------
ZONAS: dict[str, dict] = {
    "Centro": {"lat": 40.4168, "lon": -3.7038, "cps": ["28004", "28005", "28012", "28013"]},
    "Arganzuela": {"lat": 40.3980, "lon": -3.6970, "cps": ["28045", "28005"]},
    "Retiro": {"lat": 40.4110, "lon": -3.6760, "cps": ["28007", "28009", "28014"]},
    "Salamanca": {"lat": 40.4300, "lon": -3.6770, "cps": ["28001", "28006", "28028"]},
    "Chamartín": {"lat": 40.4580, "lon": -3.6770, "cps": ["28002", "28016", "28036"]},
    "Tetuán": {"lat": 40.4600, "lon": -3.6980, "cps": ["28020", "28039"]},
    "Chamberí": {"lat": 40.4340, "lon": -3.7040, "cps": ["28003", "28010", "28015"]},
    "Fuencarral-El Pardo": {"lat": 40.4950, "lon": -3.7100, "cps": ["28029", "28034", "28035"]},
    "Moncloa-Aravaca": {"lat": 40.4350, "lon": -3.7300, "cps": ["28008", "28040", "28023"]},
    "Latina": {"lat": 40.4030, "lon": -3.7450, "cps": ["28011", "28024", "28047"]},
    "Carabanchel": {"lat": 40.3830, "lon": -3.7280, "cps": ["28019", "28025", "28044"]},
    "Usera": {"lat": 40.3850, "lon": -3.7070, "cps": ["28026", "28041"]},
    "Puente de Vallecas": {"lat": 40.3910, "lon": -3.6580, "cps": ["28018", "28038", "28053"]},
    "Moratalaz": {"lat": 40.4070, "lon": -3.6440, "cps": ["28030"]},
    "Ciudad Lineal": {"lat": 40.4380, "lon": -3.6530, "cps": ["28017", "28027", "28043"]},
    "Hortaleza": {"lat": 40.4730, "lon": -3.6410, "cps": ["28033", "28050"]},
    "Villaverde": {"lat": 40.3460, "lon": -3.7090, "cps": ["28021"]},
    "San Blas-Canillejas": {"lat": 40.4290, "lon": -3.6110, "cps": ["28022", "28037"]},
    "Barajas": {"lat": 40.4730, "lon": -3.5800, "cps": ["28042"]},
    "Pozuelo de Alarcón": {"lat": 40.4350, "lon": -3.8130, "cps": ["28223", "28224"]},
    "Majadahonda": {"lat": 40.4730, "lon": -3.8720, "cps": ["28220"]},
    "Las Rozas": {"lat": 40.4930, "lon": -3.8740, "cps": ["28230", "28231"]},
    "Alcobendas": {"lat": 40.5470, "lon": -3.6420, "cps": ["28100", "28108"]},
    "Getafe": {"lat": 40.3050, "lon": -3.7330, "cps": ["28901", "28903", "28905"]},
    "Leganés": {"lat": 40.3280, "lon": -3.7640, "cps": ["28911", "28914"]},
    "Móstoles": {"lat": 40.3220, "lon": -3.8650, "cps": ["28931", "28933", "28938"]},
    "Alcalá de Henares": {"lat": 40.4820, "lon": -3.3640, "cps": ["28801", "28805", "28807"]},
}

# ---------------------------------------------------------------------------
# Catálogo de trabajos: horas estimadas y materiales (€) de referencia por tipo de avería.
# ---------------------------------------------------------------------------
CATALOGO: dict[str, dict] = {
    "fontaneria": {
        "nombre": "Fontanería",
        "trabajos": {
            "fuga_tuberia": ("Reparación de fuga en tubería", 2.0, 40),
            "atasco_desague": ("Desatasco de desagüe o bajante", 1.5, 15),
            "cambio_grifo": ("Sustitución de grifo o monomando", 1.0, 60),
            "reparacion_cisterna": ("Reparación de cisterna o mecanismo del WC", 1.0, 35),
            "calentador_termo": ("Reparación de calentador o termo eléctrico", 2.5, 120),
        },
    },
    "humedades": {
        "nombre": "Humedades y goteras",
        "trabajos": {
            "gotera_tejado": ("Reparación de gotera en cubierta o tejado", 4.0, 150),
            "humedad_capilaridad": ("Tratamiento de humedad por capilaridad", 6.0, 300),
            "humedad_condensacion": ("Tratamiento de humedad por condensación y moho", 3.0, 120),
            "filtracion_terraza": ("Impermeabilización de terraza con filtraciones", 5.0, 220),
        },
    },
    "electricidad": {
        "nombre": "Electricidad",
        "trabajos": {
            "averia_enchufes": ("Avería en enchufes o mecanismos", 1.5, 25),
            "salta_diferencial": ("Localización de avería: salta el diferencial", 2.0, 40),
            "cuadro_electrico": ("Reparación o renovación del cuadro eléctrico", 3.0, 180),
            "cambio_iluminacion": ("Sustitución de puntos de luz o lámparas", 1.5, 50),
        },
    },
    "pintura": {
        "nombre": "Pintura",
        "trabajos": {
            "pintar_habitacion": ("Pintura de una habitación (paredes y techo)", 8.0, 120),
            "pintar_techo_humedad": ("Saneado y pintura de techo con mancha de humedad", 5.0, 90),
            "pintar_vivienda": ("Pintura completa de vivienda (aprox. 80 m²)", 32.0, 450),
        },
    },
    "climatizacion": {
        "nombre": "Climatización y calefacción",
        "trabajos": {
            "reparacion_aire": ("Reparación de aire acondicionado", 2.0, 80),
            "recarga_gas": ("Recarga de gas refrigerante", 1.5, 90),
            "instalacion_split": ("Instalación de split de aire acondicionado", 5.0, 550),
            "caldera_calefaccion": ("Reparación de caldera o calefacción", 2.5, 110),
        },
    },
    "cerrajeria": {
        "nombre": "Cerrajería",
        "trabajos": {
            "apertura_puerta": ("Apertura de puerta sin rotura", 1.0, 0),
            "cambio_cerradura": ("Cambio de cerradura", 1.5, 90),
            "bombin_seguridad": ("Sustitución de bombín de seguridad", 1.0, 70),
        },
    },
    "bano_albanileria": {
        "nombre": "Baño y albañilería",
        "trabajos": {
            "reparacion_ducha": ("Reparación de ducha, mampara o rociador", 3.0, 120),
            "cambio_plato_ducha": ("Sustitución de plato de ducha", 8.0, 350),
            "azulejos": ("Reposición de azulejos rotos", 5.0, 150),
            "sellado_juntas": ("Sellado de juntas de bañera o ducha", 2.0, 30),
        },
    },
    "electrodomesticos": {
        "nombre": "Electrodomésticos",
        "trabajos": {
            "lavadora": ("Reparación de lavadora", 1.5, 60),
            "frigorifico": ("Reparación de frigorífico", 1.5, 80),
            "horno_vitro": ("Reparación de horno o vitrocerámica", 1.5, 70),
        },
    },
    "carpinteria": {
        "nombre": "Carpintería y ventanas",
        "trabajos": {
            "puerta_interior": ("Ajuste o reparación de puerta interior", 2.0, 60),
            "ventana_persiana": ("Reparación de ventana o persiana", 2.0, 70),
            "armario": ("Reparación de armario empotrado", 2.0, 40),
        },
    },
}

# ---------------------------------------------------------------------------
# Proveedores inventados: nombre, especialidades y zona base. El resto lo genera la semilla.
# ---------------------------------------------------------------------------
PROVEEDORES_BASE: list[tuple[str, list[str], str]] = [
    ("Fontanería Hermanos Robledo", ["fontaneria"], "Tetuán"),
    ("AquaFix Madrid Sur", ["fontaneria", "bano_albanileria"], "Carabanchel"),
    ("Desatascos Rápidos Castellana", ["fontaneria"], "Chamartín"),
    ("Tuberías y Grifos Llorente", ["fontaneria"], "Alcobendas"),
    ("Impermeabilizaciones Sierra Norte", ["humedades"], "Las Rozas"),
    ("SecaMuro Soluciones", ["humedades", "pintura"], "Ciudad Lineal"),
    ("Cubiertas y Tejados Moratilla", ["humedades"], "Getafe"),
    ("HumedadCero Centro", ["humedades"], "Arganzuela"),
    ("Electricidad Ruano e Hijos", ["electricidad"], "Latina"),
    ("Voltio Instalaciones", ["electricidad", "climatizacion"], "Salamanca"),
    ("Chispa Electricistas 24h", ["electricidad"], "Puente de Vallecas"),
    ("Pinturas Alcázar", ["pintura"], "Móstoles"),
    ("Color y Acabados Vega", ["pintura"], "Chamberí"),
    ("Brocha Fina Reformas", ["pintura", "bano_albanileria"], "Hortaleza"),
    ("ClimaConfort Madrid", ["climatizacion"], "Fuencarral-El Pardo"),
    ("FríoCalor Servicio Técnico", ["climatizacion", "electrodomesticos"], "Leganés"),
    ("Aire Norte Instaladores", ["climatizacion"], "Pozuelo de Alarcón"),
    ("Cerrajería La Llave de Oro", ["cerrajeria"], "Centro"),
    ("Cerrajeros Express Retiro", ["cerrajeria"], "Retiro"),
    ("Seguridad Bombín Pro", ["cerrajeria", "carpinteria"], "Usera"),
    ("Reformas Baño Perfecto", ["bano_albanileria"], "San Blas-Canillejas"),
    ("Albañilería Ortega", ["bano_albanileria", "humedades"], "Villaverde"),
    ("TecnoHogar Reparaciones", ["electrodomesticos"], "Moncloa-Aravaca"),
    ("ElectroServicio Alcalá", ["electrodomesticos"], "Alcalá de Henares"),
    ("Carpintería Madera Viva", ["carpinteria"], "Majadahonda"),
    ("Persianas y Ventanas Barajas", ["carpinteria"], "Barajas"),
    ("MultiServicios Hogar Total", ["fontaneria", "electricidad", "carpinteria"], "Moratalaz"),
]

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]


def _slug(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return "".join(c if c.isalnum() else "-" for c in s).strip("-").replace("--", "-")


def generar() -> None:
    rnd = random.Random(SEMILLA)
    proveedores = []
    for i, (nombre, especialidades, zona) in enumerate(PROVEEDORES_BASE, start=1):
        dias_laborables = sorted(rnd.sample(range(6), k=rnd.choice([4, 5, 5, 6])))
        franja = rnd.choice(["mañana", "tarde", "completa", "completa"])
        urgencias = rnd.random() < 0.4 or "24h" in nombre or "Express" in nombre
        proveedores.append(
            {
                "id": f"PRV-{i:03d}",
                "nombre": nombre,
                "especialidades": especialidades,
                "zona": zona,
                "lat": round(ZONAS[zona]["lat"] + rnd.uniform(-0.006, 0.006), 5),
                "lon": round(ZONAS[zona]["lon"] + rnd.uniform(-0.006, 0.006), 5),
                "radio_km": rnd.choice([10, 15, 20, 25, 30]),
                "tarifa_hora": rnd.choice([28, 30, 32, 35, 38, 40, 42, 45, 50]),
                "desplazamiento": rnd.choice([15, 20, 25, 30, 35]),
                "margen_materiales": rnd.choice([0.05, 0.10, 0.15, 0.20]),
                "valoracion": round(rnd.uniform(3.6, 4.9), 1),
                "num_resenas": rnd.randint(12, 420),
                "dias": [DIAS[d] for d in dias_laborables],
                "franja": franja,
                "antelacion_dias": rnd.choice([0, 1, 1, 2, 2, 3, 4]),
                "urgencias_24h": urgencias,
                "recargo_urgencia": rnd.choice([0.25, 0.30, 0.40, 0.50]) if urgencias else None,
                "garantia_meses": rnd.choice([3, 6, 6, 12, 12, 24]),
                # Dominio .example reservado (RFC 2606): nunca llega a nadie real.
                "email": f"{_slug(nombre)}@proveedores.example",
                "telefono": f"+34 600 {rnd.randint(100, 999)} {rnd.randint(100, 999)}",
            }
        )

    catalogo = {
        tipo: {
            "nombre": info["nombre"],
            "trabajos": {
                tid: {"descripcion": d, "horas": h, "materiales": m}
                for tid, (d, h, m) in info["trabajos"].items()
            },
        }
        for tipo, info in CATALOGO.items()
    }

    escribir = lambda nombre, obj: (DIR / nombre).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    escribir("proveedores.json", proveedores)
    escribir("catalogo.json", catalogo)
    escribir("zonas.json", ZONAS)
    print(f"Generados {len(proveedores)} proveedores, {sum(len(c['trabajos']) for c in catalogo.values())} trabajos y {len(ZONAS)} zonas.")


if __name__ == "__main__":
    generar()
