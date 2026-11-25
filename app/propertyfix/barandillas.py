"""Barandillas (guardrails) del sistema multi-agente.

Defensa en profundidad contra inyección de prompt y errores del modelo:
1. Detección: patrones típicos de inyección en el texto del usuario o de un email.
2. Aislamiento: el texto externo se pasa al modelo entre etiquetas <datos_usuario> y se le
   indica que es información, nunca instrucciones.
3. Salida acotada: el modelo responde con JSON contra un esquema con enumeraciones cerradas.
4. Permisos por agente: cada agente solo puede llamar a sus herramientas MCP (lista blanca).
5. Lista blanca de destinatarios en el servidor de Gmail.
6. Cifras fuera del modelo: los precios salen de la base de datos, no del LLM.
7. Presupuesto de tokens por incidencia y detector de bucles.
"""
from __future__ import annotations

import re

from . import db
from .config import MAX_TOKENS_POR_INCIDENCIA

PATRONES_INYECCION = [
    r"ignora (todas )?(las |tus )?(instrucciones|reglas|indicaciones)",
    r"olvida (todo|las instrucciones|lo anterior)",
    r"ignore (all |previous |the )?(instructions|rules)",
    r"(system|sistema) ?prompt",
    r"act[uú]a como|eres ahora|you are now|pretend to be",
    r"(env[ií]a|manda|reenv[ií]a|forward).{0,40}(a|to) [\w.+-]+@[\w-]+\.[\w.]+",
    r"(aprueba|approve).{0,30}(autom[aá]ticamente|sin (revisi[oó]n|confirmaci[oó]n))",
    r"(precio|presupuesto|importe).{0,20}(de|=|:) ?0 ?(€|euros)",
    r"</?(system|datos_usuario|instrucciones)>",
    r"developer mode|modo desarrollador|jailbreak",
]

# Qué herramientas MCP puede usar cada agente, y con qué permiso.
PERMISOS: dict[str, dict[str, str]] = {
    "clasificador": {"directorio.catalogo_trabajos": "lectura"},
    "proveedores": {"directorio.geolocalizar": "lectura (API externa)",
                    "directorio.comparar_ofertas": "lectura",
                    "directorio.ficha_proveedor": "lectura"},
    "comunicaciones": {"calendar.consultar_ocupacion": "lectura",
                       "calendar.crear_evento": "escritura · requiere aprobación",
                       "drive.crear_documento": "escritura · requiere aprobación",
                       "gmail.enviar_email": "escritura externa · requiere aprobación",
                       "sheets.registrar": "escritura interna"},
    "orquestador": {"sheets.registrar": "escritura interna"},
    "buzon": {"gmail.buscar_emails": "lectura", "gmail.marcar_procesado": "escritura interna"},
}
REQUIEREN_APROBACION = {"calendar.crear_evento", "drive.crear_documento", "gmail.enviar_email"}


def detectar_inyeccion(texto: str) -> list[str]:
    t = texto.lower()
    return [p for p in PATRONES_INYECCION if re.search(p, t)]


def envolver(texto: str) -> str:
    """Aísla el texto externo para que el modelo lo trate como datos."""
    limpio = re.sub(r"</?datos_usuario>", "", texto)
    return f"<datos_usuario>\n{limpio}\n</datos_usuario>"


def permiso(agente: str, herramienta: str) -> str | None:
    return PERMISOS.get(agente, {}).get(herramienta)


def tokens_consumidos(iid: str) -> int:
    inc = db.incidencia(iid) or {}
    return (inc.get("tokens_entrada") or 0) + (inc.get("tokens_salida") or 0)


def presupuesto_superado(iid: str) -> bool:
    return tokens_consumidos(iid) > MAX_TOKENS_POR_INCIDENCIA


class DetectorBucles:
    """Detiene la ejecución si se repite la misma llamada (herramienta + argumentos) 3 veces."""

    def __init__(self, limite: int = 3) -> None:
        self.limite = limite
        self.vistos: dict[str, int] = {}

    def registrar(self, herramienta: str, args: dict) -> bool:
        clave = f"{herramienta}:{sorted(args.items())}"
        self.vistos[clave] = self.vistos.get(clave, 0) + 1
        return self.vistos[clave] >= self.limite
