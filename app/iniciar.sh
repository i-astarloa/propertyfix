#!/usr/bin/env bash
# Arranque de PropertyFix en macOS / Linux:  bash iniciar.sh
set -e
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "[!] No se encuentra Python 3. Instálalo desde https://www.python.org/downloads/"; exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creando el entorno virtual e instalando dependencias (solo la primera vez, 1-2 minutos)..."
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt
fi

if command -v ollama >/dev/null 2>&1; then
  ollama list | grep -q "qwen2.5:3b" || { echo "Descargando el modelo qwen2.5:3b (1,9 GB, solo la primera vez)..."; ollama pull qwen2.5:3b; }
else
  echo "[!] Ollama no está instalado: los agentes usarán reglas de respaldo."
  echo "    Instálalo desde https://ollama.com/download y ejecuta: ollama pull qwen2.5:3b"
fi

.venv/bin/python -m propertyfix
