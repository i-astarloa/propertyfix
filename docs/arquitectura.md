# Arquitectura de PropertyFix

## Patrón: orquestador con trabajadores

```
                 Inquilino (email)
                        │
                ┌───────▼────────┐
                │  Orquestador   │  decide qué agente interviene, valida resultados,
                │                │  aplica presupuesto de tokens y pide aprobación humana
                └─┬──────┬─────┬─┘
        ┌─────────┘      │     └──────────┐
┌───────▼──────┐ ┌───────▼──────┐ ┌───────▼────────────┐
│ Clasificador │ │ Coordinador  │ │ Comunicaciones y   │
│ incidencias  │ │ proveedores  │ │ seguimiento        │
│ (+ RAG LAU)  │ │              │ │                    │
└──────┬───────┘ └──────┬───────┘ └──────┬─────────────┘
       │                │                │
   Gmail (leer)    Sheets (leer/      Gmail (enviar), Calendar
                   escribir)          (crear), Sheets (estado)
```

| Agente | Qué hace | Herramientas MCP permitidas | Contexto que recibe |
|---|---|---|---|
| Orquestador | Coordina, decide el siguiente paso, para o escala al humano | Ninguna directa: llama a los agentes | Estado resumido de la incidencia |
| Clasificador | Tipo de avería, inmueble, urgencia, datos que faltan, quién paga (RAG) | Gmail lectura, Sheets lectura (inmuebles) | Solo el email y la ficha del inmueble |
| Coordinador de proveedores | Selecciona candidatos, estima y compara presupuestos | Sheets lectura/escritura (proveedores, presupuestos) | Clasificación + zona del inmueble |
| Comunicaciones | Redacta y envía mensajes, propone citas, actualiza estados | Gmail envío, Calendar, Sheets escritura (estado) | Proveedor elegido + disponibilidad |

**Contexto no compartido:** cada agente recibe solo lo que necesita (menos tokens y menos exposición de datos del inquilino). Alternativa descartada: un único agente autónomo con todas las herramientas (más simple, pero mayor superficie de error y peor trazabilidad).

*(Documento vivo: se completará con la traza de una sesión, tokens medidos y comportamiento ante fallos.)*
