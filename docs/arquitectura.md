# Arquitectura de PropertyFix

## Patrón elegido: orquestador con trabajadores

```
                          Gestor (web) / Inquilino (email, tarea en bucle)
                                       │
                          ┌────────────▼────────────┐
                          │       ORQUESTADOR       │
                          │ máquina de estados +    │
                          │ decisión LLM verificada │
                          └──┬──────────┬────────┬──┘
             ┌───────────────┘          │        └────────────────┐
   ┌─────────▼────────┐      ┌──────────▼─────────┐      ┌────────▼──────────┐
   │   CLASIFICADOR   │      │    PROVEEDORES     │      │  COMUNICACIONES   │
   └─────────┬────────┘      └──────────┬─────────┘      └────────┬──────────┘
             │          HubMCP: permisos · HITL · bucles · reintento · respaldo · traza
   directorio.catalogo   directorio.geolocalizar        calendar.consultar_ocupacion
                         directorio.comparar_ofertas    calendar.crear_evento     (HITL)
                                                        drive.crear_documento     (HITL)
                                                        gmail.enviar_email        (HITL)
                                                        sheets.registrar
```

Quién llama a quién: **solo el orquestador llama a los agentes**. Los agentes no se llaman entre sí; cada uno devuelve un resultado estructurado (JSON) al orquestador, que decide el siguiente paso. Todas las herramientas pasan por el `HubMCP`.

## Qué hace cada agente y qué contexto ve

| Agente | Qué decide | Herramientas MCP | Contexto que recibe | Tokens máx. de salida |
|---|---|---|---|---|
| **Orquestador** | continuar / pedir información / escalar a humano | `sheets.registrar` | Solo la clasificación resumida (no el texto original) | 120 |
| **Clasificador** | tipo, trabajo del catálogo, urgencia, datos que faltan, sospecha de inyección | `directorio.catalogo_trabajos` | Solo el texto del problema + catálogo | 250 |
| **Proveedores** | qué proveedor y alternativa, con justificación | `directorio.geolocalizar`, `directorio.comparar_ofertas` | Clasificación + coordenadas. **No** ve el texto, ni el email ni el teléfono | 200 |
| **Comunicaciones** | redacta los mensajes; propone la cita | `calendar.*`, `drive.crear_documento`, `gmail.enviar_email`, `sheets.registrar` | Propuesta aprobada, dirección y email del usuario | 220 |

**Contexto compartido:** ninguno de los agentes comparte historial de conversación. El estado vive en la base de datos (SQLite) y el orquestador pasa a cada agente solo los campos que necesita. Ventajas: menos tokens por llamada (importante con un modelo de 3B y contexto de 4.096 tokens) y menos exposición de datos personales, ya que el agente que elige proveedor nunca ve el nombre, email ni teléfono del cliente.

## Por qué este reparto y no otro

| Alternativa | Por qué se descartó |
|---|---|
| **Un solo agente autónomo** con todas las herramientas y bucle libre (ReAct) | Con un modelo de 3B el bucle libre de herramientas es poco fiable (inventa argumentos, repite llamadas). Además tendría permiso para enviar correos en todo momento, y la traza sería más difícil de auditar. |
| **Programador y verificadores** completo | Se usa en pequeño: las decisiones del orquestador pasan por un verificador de reglas. Un verificador LLM aparte duplicaría el coste y la latencia (en CPU, unos 10–20 s más por llamada). |
| **Orquestador 100 % LLM** (el modelo decide cada transición) | La aprobación humana tiene que ser imposible de saltar. Con una máquina de estados, el paso «reservar» solo existe después de que el gestor pulse «Aprobar», haga lo que haga el modelo. |

## Flujo y estados

`recibida → clasificando → [necesita_info | escalada] → buscando_proveedor → pendiente_aprobacion → (aprobación humana) → reservando → reservada → cerrada` (o `rechazada`).

## Qué pasa cuando algo falla

| Fallo | Comportamiento |
|---|---|
| Ollama apagado o el modelo devuelve JSON inválido | Respaldo por reglas en cada agente (palabras clave, ranking por puntuación, plantillas). Se anota «respaldo» en la traza. |
| Plataforma de Google caída o token caducado | Un reintento y después el paso se ejecuta en modo simulado. La traza muestra el fallo y el respaldo. |
| OpenStreetMap (Nominatim) no responde | Geolocalización por tabla local de códigos postales y municipios. |
| Llamada MCP que no responde | Tiempo máximo de 45 s y error controlado. La incidencia pasa a «error» con el motivo. |
| Misma herramienta con los mismos argumentos 3 veces | Detector de bucles: se detiene. |
| Se supera el presupuesto de tokens (20.000) | Se para y se escala a un humano. |
| Bandeja de Gmail falla 3 veces seguidas | La tarea en bucle se pausa (cortacircuitos) y se avisa en el panel. |

## Datos del cliente: qué ve el modelo y adónde viaja

- El modelo corre **en el propio ordenador** (Ollama): el texto de la incidencia no sale a ningún proveedor de IA.
- Salen a terceros: la dirección del inmueble hacia OpenStreetMap (para geolocalizar) y, con el permiso OAuth del usuario, los datos de la cita, el documento y los correos hacia su propia cuenta de Google.
- Los correos a proveedores (ficticios, dominio `.example`) se redirigen a la bandeja del proyecto: nunca llegan a terceros.
