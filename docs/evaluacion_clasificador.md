# Evaluación del agente clasificador

Generado por `app/data/evaluacion/evaluar_clasificador.py`. Modelo `qwen2.5:3b` en Ollama, temperature 0, seed 42. Cifras **medidas** y reproducibles ejecutando el script.

- **Conjunto de desarrollo** (`casos_clasificacion.json`): casos que se vieron al diseñar el léxico y los prompts. Su acierto es **optimista** (sesgo de haber visto el examen).
- **Conjunto ciego** (`casos_ciegos.json`): escrito después de congelar v2.0. Sus fallos se usaron para diseñar v2.1, así que para v2.1 **ya no es ciego**.
- **Conjunto ciego 2** (`casos_ciegos_2.json`): escrito después de congelar v2.1 y antes de ejecutarlo. **Es la cifra que se defiende.**

## Conjunto desarrollo (42 casos)

| Variante | Acierto categoría | Acierto trabajo | «No es avería» detectados | Tokens entrada / caso | Tokens salida / caso | Segundos / caso |
|---|---|---|---|---|---|---|
| Solo palabras clave (sin modelo) | 98% | 93% | 3/3 | 0 | 0 | 0.0 |
| v1 · un paso, catálogo antiguo (lo desplegado) | 55% | 45% | 0/3 | 1262 | 95 | 19.9 |
| v2.0 · dos pasos + verificador | 98% | 90% | 3/3 | 918 | 76 | 17.3 |

## Conjunto ciego (30 casos)

| Variante | Acierto categoría | Acierto trabajo | «No es avería» detectados | Tokens entrada / caso | Tokens salida / caso | Segundos / caso |
|---|---|---|---|---|---|---|
| Solo palabras clave (sin modelo) | 63% | 53% | 2/2 | 0 | 0 | 0.0 |
| v1 · un paso, catálogo antiguo (lo desplegado) | 47% | 37% | 0/2 | 1263 | 99 | 17.6 |
| v2.0 · dos pasos + verificador | 67% | 60% | 2/2 | 912 | 76 | 17.1 |

## Conjunto ciego_2 (30 casos)

| Variante | Acierto categoría | Acierto trabajo | «No es avería» detectados | Tokens entrada / caso | Tokens salida / caso | Segundos / caso |
|---|---|---|---|---|---|---|
| Solo palabras clave (sin modelo) | 80% | 70% | 3/3 | 0 | 0 | 0.0 |
| v1 · un paso, catálogo antiguo (lo desplegado) | 50% | 33% | 0/3 | 1262 | 94 | 12.9 |
| **v2.1 · + segunda opinión antes de descartar (actual)** | 93% | 83% | 3/3 | 1047 | 86 | 18.4 |

Fallos de la versión actual (v2.1):

- Caso 204: esperado `fontaneria/atasco_desague`, obtenido `humedades/gotera_tejado`
- Caso 205: esperado `fontaneria/calentador_termo`, obtenido `fontaneria/cambio_grifo`
- Caso 206: esperado `fontaneria/reparacion_cisterna`, obtenido `fontaneria/atasco_inodoro`
- Caso 209: esperado `humedades/humedad_capilaridad`, obtenido `humedades/humedad_condensacion`
- Caso 212: esperado `electricidad/cambio_iluminacion`, obtenido `pintura/pintar_habitacion`

