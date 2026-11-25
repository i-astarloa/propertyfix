"""Cliente del modelo de lenguaje local (Ollama) con salida JSON estructurada y medición de tokens.

Cada llamada devuelve los tokens reales que reporta Ollama:
- prompt_eval_count: tokens de entrada procesados.
- eval_count: tokens de salida generados.
Se fija temperature=0 y seed=42 para que las respuestas sean reproducibles.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import httpx

from . import db
from .config import OLLAMA_MODEL, OLLAMA_URL, TIMEOUT_LLM_S


@dataclass
class RespuestaLLM:
    datos: dict = field(default_factory=dict)
    tokens_entrada: int = 0
    tokens_salida: int = 0
    ms: int = 0
    ok: bool = True
    error: str = ""


def disponible() -> tuple[bool, str]:
    """Comprueba que Ollama está en marcha y que el modelo está descargado."""
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        modelos = [m["name"] for m in r.json().get("models", [])]
        if not any(m == OLLAMA_MODEL or m.startswith(OLLAMA_MODEL + ":") for m in modelos):
            return False, f"Ollama funciona pero falta el modelo {OLLAMA_MODEL} (ollama pull {OLLAMA_MODEL})"
        return True, f"Ollama · {OLLAMA_MODEL}"
    except Exception:
        return False, "Ollama no está en marcha"


def chat_json(incidencia_id: str, agente: str, sistema: str, usuario: str, esquema: dict,
              max_salida: int = 400) -> RespuestaLLM:
    """Llama al modelo pidiendo una respuesta JSON que cumpla `esquema` y registra la traza."""
    cuerpo = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        "format": esquema,
        "stream": False,
        "options": {"temperature": 0, "seed": 42, "num_predict": max_salida, "num_ctx": 4096},
        "keep_alive": "30m",
    }
    t0 = time.perf_counter()
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/chat", json=cuerpo, timeout=TIMEOUT_LLM_S)
        r.raise_for_status()
        j = r.json()
        ms = int((time.perf_counter() - t0) * 1000)
        res = RespuestaLLM(tokens_entrada=j.get("prompt_eval_count", 0), tokens_salida=j.get("eval_count", 0), ms=ms)
        try:
            res.datos = json.loads(j["message"]["content"])
        except (json.JSONDecodeError, KeyError) as e:
            res.ok, res.error = False, f"JSON inválido del modelo: {e}"
    except Exception as e:
        res = RespuestaLLM(ok=False, error=f"{type(e).__name__}: {e}", ms=int((time.perf_counter() - t0) * 1000))

    db.registrar_traza(incidencia_id, agente, "llm", herramienta=OLLAMA_MODEL, permiso="—",
                       detalle=res.error or json.dumps(res.datos, ensure_ascii=False)[:600],
                       tokens_entrada=res.tokens_entrada, tokens_salida=res.tokens_salida, ms=res.ms, ok=res.ok)
    return res
