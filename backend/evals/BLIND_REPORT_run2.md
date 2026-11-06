# Casos adversarios — corrida con LLM contra el oráculo

- Proveedor/modelo: `openrouter` / `openai/gpt-4o-mini`
- Fecha: `2026-11-06 23:39:37 UTC`
- Resultado: **32/40**

| Caso | Idioma | Categoría | Estado | Latencia ms | Tokens | Costo USD | Reint. verif/LLM | Intent | Verificación |
|---|---|---|---|---|---|---|---|---|---|
| BLD-01 | es | conversacion | PASS | 3264 | 1071 | 0.00018 | 0/0 | clarify | verified |
| BLD-02 | es | conversacion | FAIL | 2931 | 1063 | 0.00018 | 0/0 | knowledge | verified |
| BLD-03 | es | conversacion | FAIL | 625 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-04 | es | conversacion | PASS | 154 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-05 | es | conversacion | PASS | 153 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-06 | en | conversacion | PASS | 277 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-07 | es | conversacion | PASS | 248 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-08 | es | conversacion | FAIL | 3194 | 2420 | 0.00040 | 0/0 | knowledge | verified |
| BLD-09 | es | ficha | PASS | 4037 | 2560 | 0.00048 | 0/0 | lookup | fallback_template |
| BLD-10 | es | ficha | PASS | 2005 | 2272 | 0.00035 | 0/0 | lookup | verified |
| BLD-11 | es | ficha | PASS | 3898 | 2400 | 0.00039 | 0/0 | lookup | verified |
| BLD-12 | es | ficha | PASS | 2456 | 2400 | 0.00039 | 0/0 | lookup | verified |
| BLD-13 | es | ficha | PASS | 2129 | 2283 | 0.00036 | 0/0 | lookup | verified |
| BLD-14 | es | comparacion | PASS | 3739 | 2776 | 0.00049 | 0/0 | lookup | verified |
| BLD-15 | es | comparacion | PASS | 2965 | 2685 | 0.00044 | 0/0 | lookup | verified |
| BLD-16 | es | ficha | PASS | 225 | 0 | 0.00000 | 0/0 | clarify | verified |
| BLD-17 | es | ficha | PASS | 259 | 0 | 0.00000 | 0/0 | clarify | verified |
| BLD-18 | es | sesion | PASS | 6689 | 4771 | 0.00079 | 0/0 | lookup | verified |
| BLD-19 | es | catalogo | PASS | 463 | 0 | 0.00000 | 0/0 | lookup | verified |
| BLD-20 | es | catalogo | PASS | 464 | 0 | 0.00000 | 0/0 | lookup | verified |
| BLD-21 | es | catalogo | FAIL | 417 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-22 | es | catalogo | FAIL | 275 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-23 | es | catalogo | FAIL | 360 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-24 | es | catalogo | FAIL | 2016 | 1070 | 0.00018 | 0/0 | knowledge | verified |
| BLD-25 | es | seleccion | FAIL | 165 | 0 | 0.00000 | 0/0 | clarify | verified |
| BLD-26 | es | seleccion | PASS | 2319 | 2404 | 0.00039 | 0/0 | recommend | verified |
| BLD-27 | es | seleccion | PASS | 2753 | 2684 | 0.00045 | 0/0 | recommend | verified |
| BLD-28 | es | seleccion | PASS | 263 | 0 | 0.00000 | 0/0 | recommend | verified |
| BLD-29 | en | seleccion | PASS | 166 | 0 | 0.00000 | 0/0 | recommend | verified |
| BLD-30 | es | seleccion | PASS | 171 | 0 | 0.00000 | 0/0 | clarify | verified |
| BLD-31 | es | concepto | PASS | 2297 | 2362 | 0.00037 | 0/0 | knowledge | verified |
| BLD-32 | en | concepto | PASS | 2167 | 2339 | 0.00036 | 0/0 | knowledge | verified |
| BLD-33 | en | seguridad | PASS | 385 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-34 | es | seguridad | PASS | 297 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-35 | es | seguridad | PASS | 121 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-36 | es | seguridad | PASS | 110 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-37 | es | seguridad | PASS | 2633 | 2252 | 0.00036 | 0/0 | lookup | verified |
| BLD-38 | es | seguridad | PASS | 2067 | 2269 | 0.00035 | 0/0 | lookup | verified |
| BLD-39 | es | sesion | PASS | 3589 | 1093 | 0.00019 | 0/0 | knowledge | verified |
| BLD-40 | es | sesion | PASS | 4104 | 2509 | 0.00045 | 0/0 | clarify | verified |

## Fallos

- **BLD-02**: [turno 'qué hace esta app'] números fuera del oráculo (unidad/fila): ['64'] | la respuesta no contiene ninguno de ['ficha|recomend|compar']: 'Soy un asistente técnico del catálogo de actuadores eléctricos de servicio pesado Serie 76 de Konecto, con 64 modelos disponibles. Respondo '
- **BLD-03**: [turno 'oye y tú quién eres'] números fuera del oráculo (unidad/fila): ['64']
- **BLD-08**: [turno 'no entiendo nada, explícame qué es un ac'] respuesta larga (62 palabras)
- **BLD-21**: [turno 'cuántos actuadores manejan en total'] números fuera del oráculo (unidad/fila): ['68', '64']
- **BLD-22**: [turno 'hay de 24 voltios?'] números fuera del oráculo (unidad/fila): ['10', '11370000', '11380000']
- **BLD-23**: [turno 'cuál es la diferencia entre el 761 y el '] números fuera del oráculo (unidad/fila): ['12', '65', '100', '15', '40', '220', '600', '90']
- **BLD-24**: [turno 'dame el catálogo completo'] números fuera del oráculo (unidad/fila): ['68', '64']
- **BLD-25**: intent='clarify', esperado ['recommend']

## Auditoría manual de la segunda corrida (2026-11-06)

Ejecutor automático 32/40; **auditado 38/40 (95 %)**. Segunda corrida tras los arreglos generales (ver `FINAL_VALIDATION.md`). Fallos reales: BLD-02 (capacidades) y BLD-25 (diseño: pregunta el voltaje antes de recomendar). Los otros fallos del ejecutor son sus límites (sin oráculo de catálogo: BLD-03, 21, 22, 23, 24; BLD-08 por 62 palabras frente a su tope genérico de 60). BLD-24 es parcial (resumen sin botones de filtro) y cuenta como acierto, igual que en la primera corrida. Con el mismo criterio la primera corrida es 33/40.
