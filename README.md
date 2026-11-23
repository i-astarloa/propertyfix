# PropertyFix

**Gestor de incidencias inmobiliarias impulsado por agentes de IA.** Recibe averías de inquilinos por email, las clasifica, decide quién debe pagar la reparación (propietario o inquilino, con cita a la LAU), busca proveedores, prepara presupuestos, pide aprobación al gestor, agenda la visita y hace el seguimiento — todo desde un dashboard web.

Proyecto final de *Deep Learning para Business Analytics* (ICADE, curso 2026–2027).

> Estado: **en construcción** (esqueleto inicial). Este README se irá completando con cada fase.

## Qué hace el agente que no haría un formulario

Un formulario recoge datos; PropertyFix **decide y actúa**: interpreta un email libre, estima urgencia, detecta información que falta y la pide, elige proveedor comparando precio/zona/valoración, redacta y envía comunicaciones, crea el evento en el calendario y actualiza la base de datos — parando para pedir aprobación humana cuando hay gasto o comunicación externa sensible.

## Arquitectura (resumen)

- **Patrón:** orquestador con trabajadores (1 orquestador + 3 agentes especializados).
- **MCP a tres plataformas:** Gmail, Google Calendar y Google Sheets (lectura y escritura).
- **Barandillas:** aprobación humana (HITL) para gasto y envíos externos, detección de inyección de prompt en emails entrantes, presupuesto máximo de tokens por incidencia, detector de bucles.
- **Modo demo:** si no hay credenciales o una plataforma falla, los servidores MCP funcionan con datos simulados para que la app siempre arranque.

Detalle completo en [`docs/arquitectura.md`](docs/arquitectura.md).

## Estructura del repositorio

```
app/            Código de la aplicación (entregable app/)
docs/           Arquitectura, decisiones técnicas y trazabilidad de IA
prompts/        Prompts relevantes usados durante el desarrollo
```

## Arranque rápido

*(Se completará cuando la app sea ejecutable.)*

```bash
cd app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m propertyfix
```

## Uso de IA

Este proyecto se ha construido con ayuda de Claude Code (Anthropic). Ver [`docs/uso_ia.md`](docs/uso_ia.md).
