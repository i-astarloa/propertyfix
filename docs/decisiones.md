# Registro de decisiones técnicas

Cada decisión con su alternativa descartada y el porqué, para poder defenderla en la ronda de preguntas sin «lo dijo el modelo».

| # | Decisión | Alternativa descartada | Por qué |
|---|---|---|---|
| 1 | Python + FastAPI + plantillas HTML | Streamlit | FastAPI permite un flujo con estados, aprobaciones y actualización en vivo; Streamlit re-ejecuta todo el script en cada clic y complica el estado de las incidencias. |
| 2 | Servidores MCP propios para Gmail, Calendar, Drive, Sheets y directorio | Llamar a las APIs de Google directamente desde los agentes | MCP separa herramientas de agentes: cada agente solo ve sus herramientas (permisos), cada llamada queda registrada (traza) y se puede cambiar una implementación sin tocar los agentes. |
| 3 | Modo simulado en cada servidor de Google | Solo modo real | La app tiene que arrancar en el portátil del profesor aunque no haya credenciales, y seguir funcionando si una plataforma falla. |
| 4 | Presupuestos calculados con las tarifas de la base | Esperar respuestas reales de proveedores o que el LLM estime precios | No hay proveedores reales. Además, si el modelo pusiera los precios podría alucinarlos o ser manipulado por inyección. |
| 5 | Cuenta de Google dedicada al proyecto | Cuentas personales | Separa datos personales y limita el daño si algo falla. |
| 6 | **Modelo abierto local (Qwen 2.5 3B en Ollama)** | API de pago (Claude, GPT) | Coste cero por token para el equipo y privacidad (los datos no salen del ordenador). Coste: menos calidad y más latencia (~1 min por incidencia en CPU). Se compensa con salida JSON con esquema, ejemplos *few-shot*, pista de un preclasificador y respaldo por reglas. |
| 7 | 3B y no 7B | Qwen 2.5 7B | En el portátil de desarrollo (CPU i7-1355U, 16 GB, sin GPU) el 7B tarda unas 2,5 veces más. Configurable con `OLLAMA_MODEL`. |
| 8 | Orquestador híbrido (máquina de estados + decisión LLM verificada) | Orquestador 100 % LLM | La aprobación humana no debe depender de que el modelo «decida» pedirla. |
| 9 | Contexto no compartido entre agentes | Historial común | Menos tokens y menos datos personales expuestos. |
| 10 | `temperature=0` y `seed=42` | Valores por defecto | Reproducibilidad: la misma incidencia da la misma clasificación (requisito: semillas fijadas). |
| 11 | Pista del preclasificador + ejemplos few-shot en el clasificador | Solo instrucciones | En la primera prueba el 3B clasificó una gotera como «humedad por condensación». Con la pista y los ejemplos la clasificó bien. Es aprendizaje en contexto (día 16), sin reentrenar. |
| 12 | Verificador sobre «pedir información» | Aceptar siempre la decisión del modelo | El modelo pequeño pedía datos innecesarios. Solo se pregunta si hay algo concreto que pedir **y** la incidencia es dudosa (texto corto o confianza < 0,6). |
| 13 | Correos a proveedores redirigidos a la bandeja del proyecto (sandbox) | Enviar a direcciones de proveedores | Los proveedores son ficticios (dominio `.example`); nunca se debe escribir a terceros reales. |
| 14 | Geolocalización con OpenStreetMap + tabla local de respaldo | Google Maps API | Nominatim es gratuito y sin clave. Si cae, la app sigue con la tabla de códigos postales. |
| 16 | Inicio de sesión con Google en modo prueba, con una sola cuenta autorizada (la del proyecto) | Publicar la app para cualquier cuenta | Google exige una verificación larga para publicar apps que leen Gmail. En modo prueba solo entran los usuarios autorizados; el código ya trabaja con la cuenta que inicia sesión, así que en producción bastaría con verificar la app. |
| 17 | **Clasificador en dos pasos** (categoría → trabajo) | Un paso eligiendo entre 35 trabajos | En las pruebas reales el 3B confundió un lavavajillas con «pintar» y un retrete con una lavadora. Con 10 opciones y luego 3–6, la tarea es más fácil para un modelo pequeño. Medido en [`evaluacion_clasificador.md`](evaluacion_clasificador.md). |
| 18 | Categoría «no es una avería» → revisión humana | Forzar siempre una categoría | Un mensaje fuera de ámbito («mi novia me grita») acababa en un presupuesto de pintura. Ahora se escala a una persona. |
| 19 | Verificador léxico que corrige al modelo solo ante contradicción fuerte | Confiar siempre en el modelo / usar solo palabras clave | Las palabras clave solas dan 93 % en el conjunto de desarrollo pero 53 % en el ciego (sobreajuste): no sirven como clasificador principal, sí como red de seguridad cuando el texto nombra un objeto inequívoco. |
| 20 | Confianza calculada (acuerdo modelo ↔ evidencia) | Pedir la confianza al modelo | El 3B se asignaba siempre 1,0, incluso cuando se equivocaba. Un número que nunca cambia no sirve para decidir. |
| 21 | Dos conjuntos de evaluación: desarrollo y ciego | Uno solo | El léxico y los prompts se diseñaron viendo el primero; medir solo con él inflaría el acierto. El ciego se escribió después de congelarlos. |
| 22 | El buzón excluye los correos propios (`-from:me` + prefijos de asunto) | Filtrar solo por asunto | El buzón leía las confirmaciones que enviaba la propia app («Reparación reservada…») y creaba incidencias falsas: un bucle de retroalimentación real detectado en pruebas. |
| 15 | SDK de MCP fijado en la versión 1.x | MCP 2.x (recién publicado) | La 2.x cambió la API (FastMCP → MCPServer); la 1.x es estable y está documentada. |
