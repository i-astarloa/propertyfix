"""Coste de construir PropertyFix: tokens leídos del registro (usage) de Claude Code, no estimados.

Claude Code guarda cada sesión en ~/.claude/projects/<proyecto>/<id-sesión>.jsonl. Cada respuesta del
modelo incluye un bloque `usage` con los tokens reales: entrada sin caché, salida, escritura en caché
(5 min / 1 h) y lectura de caché. Este script suma esos bloques (una vez por mensaje, aunque el
registro repita el mensaje en varias líneas) y los valora a precio de lista de la API.

Uso:  python docs/coste_construccion/leer_usage_claude_code.py <ruta.jsonl> [<ruta2.jsonl> ...]
Escribe el resultado en docs/coste_construccion/coste_construccion.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

# Precios de lista por millón de tokens en USD (Anthropic, noviembre de 2026).
PRECIOS = {
    "claude-opus-5-5": {"entrada": 4.00, "salida": 20.00, "cache_5m": 5.00, "cache_1h": 8.00, "cache_lectura": 0.20},
}
USD_EUR = 0.92  # supuesto de tipo de cambio (estimación), ver memoria


def leer(rutas: list[Path]) -> dict:
    vistos: set[str] = set()
    por_modelo: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for ruta in rutas:
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            try:
                ev = json.loads(linea)
            except json.JSONDecodeError:
                continue
            msg = ev.get("message") or {}
            uso = msg.get("usage")
            if ev.get("type") != "assistant" or not uso:
                continue
            clave = msg.get("id") or ev.get("requestId") or ev.get("uuid")
            if clave in vistos:  # el registro repite el mismo mensaje en varias líneas
                continue
            vistos.add(clave)
            m = por_modelo[msg.get("model", "desconocido")]
            m["mensajes"] += 1
            m["entrada"] += uso.get("input_tokens", 0) or 0
            m["salida"] += uso.get("output_tokens", 0) or 0
            m["cache_lectura"] += uso.get("cache_read_input_tokens", 0) or 0
            det = uso.get("cache_creation") or {}
            c5, c1 = det.get("ephemeral_5m_input_tokens", 0) or 0, det.get("ephemeral_1h_input_tokens", 0) or 0
            total_escritura = uso.get("cache_creation_input_tokens", 0) or 0
            if not det:  # sin desglose: se asume 5 minutos (la opción más barata, conservadora)
                c5 = total_escritura
            m["cache_5m"] += c5
            m["cache_1h"] += c1
    return por_modelo


def valorar(por_modelo: dict) -> dict:
    res = {"modelos": {}, "total_usd": 0.0}
    for modelo, t in por_modelo.items():
        p = PRECIOS.get(modelo)
        coste = None
        if p:
            coste = sum(t[k] * p[k] / 1e6 for k in ("entrada", "salida", "cache_5m", "cache_1h", "cache_lectura"))
            res["total_usd"] += coste
        res["modelos"][modelo] = {**t, "coste_usd": round(coste, 2) if coste is not None else None}
    res["total_usd"] = round(res["total_usd"], 2)
    res["total_eur"] = round(res["total_usd"] * USD_EUR, 2)
    res["tipo_cambio_usd_eur"] = USD_EUR
    return res


if __name__ == "__main__":
    rutas = [Path(a) for a in sys.argv[1:]]
    r = valorar(leer(rutas))
    r["sesiones"] = [p.name for p in rutas]
    salida = Path(__file__).parent / "coste_construccion.json"
    salida.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(r, indent=2, ensure_ascii=False))
