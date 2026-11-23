# Registro de decisiones técnicas

Cada decisión con su alternativa descartada y el porqué, para poder defenderla en la ronda de preguntas sin «lo dijo el modelo».

| # | Decisión | Alternativa descartada | Por qué |
|---|---|---|---|
| 1 | Python + FastAPI para la web | Streamlit | FastAPI permite un dashboard con flujo de aprobaciones y API propia; Streamlit re-ejecuta todo el script en cada clic y complica el estado de las incidencias. |
| 2 | Servidores MCP propios para Gmail, Calendar y Sheets | Conectar las APIs de Google directamente desde los agentes | MCP separa herramientas de agentes: cada agente solo ve las herramientas que le tocan (permisos) y cada llamada queda registrada (traza). |
| 3 | Modo demo con MCP simulados | Solo modo real | La app tiene que arrancar en el portátil del profesor aunque no haya credenciales de Google o una plataforma falle. |
| 4 | Presupuestos estimados con las tarifas de la base de proveedores | Esperar respuestas reales de proveedores | En el MVP no hay proveedores reales que respondan; la solicitud sí se envía de verdad a una dirección de prueba. |
| 5 | Cuenta de Google dedicada (propertyfix.demo) | Cuenta personal | Separa datos personales de los del proyecto y limita el daño si algo falla. |
