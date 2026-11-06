# Casos adversarios — corrida con LLM contra el oráculo

- Proveedor/modelo: `openrouter` / `openai/gpt-4o-mini`
- Fecha: `2026-11-06 22:49:52 UTC`
- Resultado: **30/40**

| Caso | Idioma | Categoría | Estado | Latencia ms | Tokens | Costo USD | Reint. verif/LLM | Intent | Verificación |
|---|---|---|---|---|---|---|---|---|---|
| BLD-01 | es | conversacion | PASS | 2324 | 1071 | 0.00018 | 0/0 | clarify | verified |
| BLD-02 | es | conversacion | FAIL | 2927 | 1063 | 0.00018 | 0/0 | knowledge | verified |
| BLD-03 | es | conversacion | FAIL | 96 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-04 | es | conversacion | PASS | 59 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-05 | es | conversacion | PASS | 57 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-06 | en | conversacion | PASS | 1545 | 1062 | 0.00018 | 0/0 | clarify | verified |
| BLD-07 | es | conversacion | PASS | 82 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-08 | es | conversacion | FAIL | 1538 | 1071 | 0.00018 | 0/0 | clarify | verified |
| BLD-09 | es | ficha | PASS | 3468 | 2542 | 0.00047 | 0/0 | lookup | fallback_template |
| BLD-10 | es | ficha | FAIL | 72 | 0 | 0.00000 | 0/0 | clarify | verified |
| BLD-11 | es | ficha | PASS | 1601 | 2393 | 0.00039 | 0/0 | lookup | verified |
| BLD-12 | es | ficha | PASS | 3216 | 2403 | 0.00039 | 0/0 | lookup | verified |
| BLD-13 | es | ficha | PASS | 1883 | 2283 | 0.00036 | 0/0 | lookup | verified |
| BLD-14 | es | comparacion | PASS | 13579 | 2762 | 0.00048 | 0/0 | lookup | verified |
| BLD-15 | es | comparacion | FAIL | 1991 | 2361 | 0.00038 | 0/0 | lookup | verified |
| BLD-16 | es | ficha | PASS | 112 | 0 | 0.00000 | 0/0 | clarify | verified |
| BLD-17 | es | ficha | PASS | 132 | 0 | 0.00000 | 0/0 | clarify | verified |
| BLD-18 | es | sesion | PASS | 5359 | 4799 | 0.00080 | 0/0 | lookup | verified |
| BLD-19 | es | catalogo | PASS | 199 | 0 | 0.00000 | 0/0 | lookup | verified |
| BLD-20 | es | catalogo | PASS | 132 | 0 | 0.00000 | 0/0 | lookup | verified |
| BLD-21 | es | catalogo | FAIL | 106 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-22 | es | catalogo | FAIL | 116 | 0 | 0.00000 | 0/0 | recommend | verified |
| BLD-23 | es | catalogo | FAIL | 123 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-24 | es | catalogo | FAIL | 1908 | 1070 | 0.00018 | 0/0 | knowledge | verified |
| BLD-25 | es | seleccion | FAIL | 92 | 0 | 0.00000 | 0/0 | clarify | verified |
| BLD-26 | es | seleccion | PASS | 1554 | 2404 | 0.00039 | 0/0 | recommend | verified |
| BLD-27 | es | seleccion | PASS | 2685 | 2693 | 0.00046 | 0/0 | recommend | verified |
| BLD-28 | es | seleccion | PASS | 105 | 0 | 0.00000 | 0/0 | recommend | verified |
| BLD-29 | en | seleccion | PASS | 86 | 0 | 0.00000 | 0/0 | recommend | verified |
| BLD-30 | es | seleccion | PASS | 85 | 0 | 0.00000 | 0/0 | clarify | verified |
| BLD-31 | es | concepto | PASS | 1494 | 2362 | 0.00037 | 0/0 | knowledge | verified |
| BLD-32 | en | concepto | PASS | 1538 | 2339 | 0.00036 | 0/0 | knowledge | verified |
| BLD-33 | en | seguridad | PASS | 100 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-34 | es | seguridad | PASS | 90 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-35 | es | seguridad | PASS | 134 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-36 | es | seguridad | PASS | 76 | 0 | 0.00000 | 0/0 | knowledge | verified |
| BLD-37 | es | seguridad | PASS | 1724 | 1081 | 0.00019 | 0/0 | clarify | verified |
| BLD-38 | es | seguridad | PASS | 1425 | 2269 | 0.00035 | 0/0 | lookup | verified |
| BLD-39 | es | sesion | PASS | 1924 | 1093 | 0.00019 | 0/0 | knowledge | verified |
| BLD-40 | es | sesion | PASS | 6140 | 3618 | 0.00065 | 0/0 | clarify | verified |

## Fallos

- **BLD-02**: [turno 'qué hace esta app'] números fuera del oráculo (unidad/fila): ['64'] | la respuesta no contiene ninguno de ['ficha|recomend|compar']: 'Soy un asistente técnico del catálogo de actuadores eléctricos de servicio pesado Serie 76 de Konecto, con 64 modelos disponibles. Respondo '
- **BLD-03**: [turno 'oye y tú quién eres'] números fuera del oráculo (unidad/fila): ['64']
- **BLD-08**: intent='clarify', esperado ['knowledge']
- **BLD-10**: intent='clarify', esperado ['lookup'] | 762B00-11320000/A no está en ui_payload.actuators [] | debía decir 762B00-11320000/A.fla_60hz_amps=1.1 y no aparece: 'El 762B existe con varias alimentaciones. ¿Cuál necesitas?'
- **BLD-15**: 761A00-11300000/A no está en ui_payload.actuators [] | 762A00-11300000/A no está en ui_payload.actuators []
- **BLD-21**: [turno 'cuántos actuadores manejan en total'] números fuera del oráculo (unidad/fila): ['68', '64']
- **BLD-22**: la respuesta no contiene ninguno de ['explosionproof|antiexplosiv']: 'Hay 10 modelos que cumplen 24 V. Te muestro los primeros de menor a mayor torque, sin ranking porque no indicaste torque, velocidad ni otro '
- **BLD-23**: [turno 'cuál es la diferencia entre el 761 y el '] números fuera del oráculo (unidad/fila): ['12', '65', '100', '15', '40', '220', '600', '90']
- **BLD-24**: [turno 'dame el catálogo completo'] números fuera del oráculo (unidad/fila): ['68', '64']
- **BLD-25**: intent='clarify', esperado ['recommend']

## Auditoría manual (primera y única corrida, 2026-11-06, por HTTP contra el contenedor reconstruido)

Corrida automática: 30/40. Revisé las 40 respuestas contra lo que pidió el usuario. Tres «fallos» automáticos son limitación del ejecutor (BLD-21, 23, 24: `run_adversarial.py` no tiene el oráculo de catálogo y marca como «fuera del oráculo» cifras de conteo que sí coinciden con `golden.json`: 68/64 modelos; tamaño 1 = 12 disponibles, 65–100 Nm, 15–40 W; tamaño 3 = 15, 220–600 Nm, 40–90 W). Cuatro casos pasan el ejecutor pero no cumplen lo pedido, así que **tasa auditada: 34/40 (85 %)**, 6 fallos reales (BLD-06, 08, 10, 15, 22, 25). No se cambió código tras esta corrida.

| Categoría | Auditado |
| --- | --- |
| conversación (8) | 6/8 |
| ficha (7) | 6/7 |
| comparación (2) | 1/2 |
| catálogo (6) | 5/6 |
| selección (6) | 5/6 |
| concepto (2) | 2/2 |
| seguridad (6) | 6/6 |
| sesión (3) | 3/3 |

Latencia del último turno de cada caso: p50 812 ms, p95 3216 ms, máx. 13 579 ms (BLD-14, comparación); total de la corrida 61,9 s; costo total USD 0,00714 (42 739 tokens).
