# Declaración de uso de IA (trazabilidad)

| Herramienta | Para qué |
|---|---|
| Claude Code (Anthropic, modelo Claude Opus 5.5), app de escritorio | Lectura de las instrucciones y de las diapositivas de los días 13–17; diseño de la arquitectura; generación del código de la app, de los servidores MCP, de los tests y de los scripts de evaluación y del modelo financiero; búsqueda de datos de mercado; configuración de Google Cloud (con la sesión iniciada por el equipo); redacción de la memoria y de las diapositivas. |
| Otro asistente de IA conversacional | Primer borrador del plan de negocio de PropertyFix. |
| Qwen 2.5 3B (Ollama) | Es el modelo *dentro* del producto, no una herramienta de desarrollo. |

Los prompts relevantes se guardan en [`../prompts/`](../prompts/).

## Coste de construcción

Leído del registro de uso de Claude Code (no estimado a ojo) con
[`coste_construccion/leer_usage_claude_code.py`](coste_construccion/leer_usage_claude_code.py); el resultado está en
[`coste_construccion/coste_construccion.json`](coste_construccion/coste_construccion.json) y entra en la inversión
inicial del modelo financiero.
