# Validación final (fase 4B-2): mediciones

Anexo con los datos tal cual de las corridas de validación final. No sustituye a `EVALUATION_REPORT.md`, `ADVERSARIAL_REPORT.md` ni `HELDOUT_REPORT.md` (corridas anteriores y análisis de causas); no contiene claves.

## Condiciones

- **Fecha:** 2026-11-05 (evals NIM a las 18:48 UTC según su informe).
- **Código probado:** base `487de19` (el commit clonado) más los cambios locales de ese momento (manejadores de errores HTTP, orden de la plantilla de comparación, modo degradado), que quedaron en el commit `8ed998e`. Las baterías se ejecutaron desde el árbol de trabajo del repo, en proceso (`TestClient`), contra la base de datos PostgreSQL de un clon limpio levantado con `docker compose up --build`.
- **Perfiles:** NIM = `nvidia/nemotron-3.5-lightning-30b-a3b`; OpenRouter = `openai/gpt-4o-mini` (variable `LLM_PROVIDER` por corrida).
- **Costo:** estimado por el backend como tokens × precio de lista del perfil (`llm_profiles.json`); no es la factura del proveedor. NIM cuenta como $0.
- **Latencia por caso:** suma de los turnos del caso (los casos de varios turnos suman todos). p50/p95 calculados sobre las latencias por caso con el método del vecino más cercano (`round(p·(n−1))`).
- **Reintentos de transporte:** reintentos del cliente LLM ante 429/5xx/timeouts (`llm_retries`); **del verificador:** reescrituras pedidas al LLM por cifras sin respaldo (`verifier_retries`).
- **Ciega OpenRouter:** muestra de 10 casos de `heldout.json`: HLD-02, 05, 08, 11, 14, 18, 20, 23, 29 y 38 (elegidos para variar categorías; incluye HLD-20, el caso difícil conocido).
- Evals (11 escenarios): el informe de esa corrida no registra tokens ni reintentos; solo latencia por escenario y estado.

## Resumen

| Batería | Proveedor | Resultado | Reintentos transporte | Reintentos verificador | Latencia p50 / p95 (ms) | Tokens | Costo estimado (USD) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Evals (11 escenarios) | NIM | 11/11 | no registrado | no registrado | 4587 / 8723 | no registrado | no registrado |
| Evals (11 escenarios) | OpenRouter | 11/11 | no registrado | no registrado | 2582 / 6816 | no registrado | no registrado |
| Adversarial (30 casos) | NIM | 30/30 | 52 | 0 | 4477 / 6422 | 8029 | 0.00000 |
| Ciega completa (40 casos) | NIM | 39/40 | 73 | 0 | 4452 / 8882 | 20632 | 0.00000 |
| Adversarial (30 casos) | OpenRouter | 30/30 | 0 | 1 | 2569 / 5803 | 55598 | 0.00911 |
| Ciega, muestra de 10 casos | OpenRouter | 9/10 | 0 | 0 | 2427 / 9571 | 25670 | 0.00433 |

## Evals (11 escenarios)

### NIM

| Escenario | Categoría | Turnos | Latencia (ms) | Herramientas | Estado |
| --- | --- | --- | --- | --- | --- |
| EVAL-01 | Specific Data Retrieval | 1 | 8723 | `lookup_actuator_by_part_number` | PASS |
| EVAL-02 | Multi-Turn Coreference | 3 | 8334 | `lookup_actuator_by_part_number` | PASS |
| EVAL-03 | Specific Data Retrieval | 1 | 3551 | `lookup_actuator_by_part_number` | PASS |
| EVAL-04 | Edge Case: N/A Model | 1 | 7475 | `lookup_actuator_by_part_number` | PASS |
| EVAL-05 | Edge Case: Typo Fuzzy Match | 1 | 2911 | `lookup_actuator_by_part_number` | PASS |
| EVAL-06 | Edge Case: Invalid Part Number | 1 | 4991 | `lookup_actuator_by_part_number` | PASS |
| EVAL-07 | Product Recommendation | 1 | 4587 | `recommend_actuators` | PASS |
| EVAL-08 | Edge Case: CSA Footnote Trap | 1 | 4570 | `recommend_actuators` | PASS |
| EVAL-09 | Edge Case: Impossible Requirement | 1 | 4486 | `recommend_actuators` | PASS |
| EVAL-10 | Edge Case: Ambiguous Service Type | 2 | 5667 | `recommend_actuators` | PASS |
| EVAL-11 | Engineering Rules & Knowledge | 1 | 4298 | `search_engineering_knowledge` | PASS |

### OpenRouter

| Escenario | Categoría | Turnos | Latencia (ms) | Herramientas | Estado |
| --- | --- | --- | --- | --- | --- |
| EVAL-01 | Specific Data Retrieval | 1 | 4483 | `lookup_actuator_by_part_number` | PASS |
| EVAL-02 | Multi-Turn Coreference | 3 | 6816 | `lookup_actuator_by_part_number` | PASS |
| EVAL-03 | Specific Data Retrieval | 1 | 2437 | `lookup_actuator_by_part_number` | PASS |
| EVAL-04 | Edge Case: N/A Model | 1 | 3446 | `lookup_actuator_by_part_number` | PASS |
| EVAL-05 | Edge Case: Typo Fuzzy Match | 1 | 2382 | `lookup_actuator_by_part_number` | PASS |
| EVAL-06 | Edge Case: Invalid Part Number | 1 | 1987 | `lookup_actuator_by_part_number` | PASS |
| EVAL-07 | Product Recommendation | 1 | 2180 | `recommend_actuators` | PASS |
| EVAL-08 | Edge Case: CSA Footnote Trap | 1 | 3187 | `recommend_actuators` | PASS |
| EVAL-09 | Edge Case: Impossible Requirement | 1 | 2582 | `recommend_actuators` | PASS |
| EVAL-10 | Edge Case: Ambiguous Service Type | 2 | 4106 | `recommend_actuators` | PASS |
| EVAL-11 | Engineering Rules & Knowledge | 1 | 2365 | `search_engineering_knowledge` | PASS |

## Adversarial: NIM

Totales de la corrida: 30/30 casos pasan; tokens 8029; costo estimado USD 0.00000; reintentos de transporte 52; del verificador 0.

| Caso | Categoría | Idioma | Resultado | Latencia (ms) | Tokens | Costo (USD) | Reint. transporte | Reint. verificador | Intent | Verificación |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADV-01 | typo | es | PASS | 4861 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-02 | typo | en | PASS | 4429 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-03 | na_3phase | es | PASS | 4436 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-04 | na_3phase | en | PASS | 4522 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-05 | invented_pn | es | PASS | 4445 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-06 | invented_pn | en | PASS | 4410 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-07 | ambiguity | es | PASS | 1058 | 0 | 0.00000 | 0 | 0 | clarify | verified |
| ADV-08 | ambiguity | en | PASS | 892 | 0 | 0.00000 | 0 | 0 | clarify | verified |
| ADV-09 | impossible | en | PASS | 4584 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |
| ADV-10 | impossible | es | PASS | 4652 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |
| ADV-11 | 24v_weatherproof | es | PASS | 4397 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |
| ADV-12 | 24v_weatherproof | en | PASS | 4481 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |
| ADV-13 | 24v_no_hz | es | PASS | 4634 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-14 | 24v_no_hz | en | PASS | 4503 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-15 | cycles_vs_starts | es | PASS | 5613 | 2691 | 0.00000 | 2 | 0 | lookup | verified |
| ADV-16 | cycles_vs_starts | en | PASS | 4507 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-17 | csa_warning | es | PASS | 4477 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-18 | csa_warning | en | PASS | 4407 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-19 | prompt_injection | es | PASS | 4481 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-20 | prompt_injection | en | PASS | 4439 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-21 | out_of_catalog | es | PASS | 158 | 0 | 0.00000 | 0 | 0 | knowledge | verified |
| ADV-22 | out_of_catalog | en | PASS | 116 | 0 | 0.00000 | 0 | 0 | knowledge | verified |
| ADV-23 | followup_no_pn | es | PASS | 6833 | 2606 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-24 | followup_no_pn | en | PASS | 6422 | 2732 | 0.00000 | 2 | 0 | lookup | verified |
| ADV-25 | compare | es | PASS | 4466 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-26 | compare | en | PASS | 4560 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-27 | 3phase_modulating | es | PASS | 4440 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |
| ADV-28 | 3phase_modulating | en | PASS | 4543 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| ADV-29 | knowledge | en | PASS | 4436 | 0 | 0.00000 | 2 | 0 | knowledge | fallback_template |
| ADV-30 | clarification_flow | es | PASS | 5304 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |

## Ciega completa: NIM

Totales de la corrida: 39/40 casos pasan; tokens 20632; costo estimado USD 0.00000; reintentos de transporte 73; del verificador 0.

| Caso | Categoría | Idioma | Resultado | Latencia (ms) | Tokens | Costo (USD) | Reint. transporte | Reint. verificador | Intent | Verificación |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HLD-01 | plain_lookup | es | PASS | 4841 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-02 | plain_lookup | en | PASS | 4512 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-03 | plain_lookup | mixed | PASS | 4474 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-04 | voice_dictated | es | PASS | 4418 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-05 | voice_dictated | en | PASS | 4474 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-06 | voice_dictated | mixed | PASS | 5314 | 2664 | 0.00000 | 2 | 0 | lookup | verified |
| HLD-07 | part_number_typo | es | PASS | 4395 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-08 | part_number_typo | en | PASS | 4509 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-09 | part_number_typo | mixed | PASS | 4533 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-10 | long_noisy | es | PASS | 4484 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-11 | long_noisy | en | PASS | 1751 | 2800 | 0.00000 | 0 | 0 | lookup | verified |
| HLD-12 | long_noisy | mixed | PASS | 4551 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-13 | multi_requirement | es | PASS | 4446 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |
| HLD-14 | multi_requirement | en | PASS | 4476 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |
| HLD-15 | multi_requirement | en | PASS | 5611 | 3020 | 0.00000 | 2 | 0 | recommend | verified |
| HLD-16 | multi_requirement | mixed | PASS | 5444 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |
| HLD-17 | followup | es | PASS | 8882 | 0 | 0.00000 | 4 | 0 | lookup | fallback_template |
| HLD-18 | followup | en | PASS | 8957 | 0 | 0.00000 | 4 | 0 | lookup | fallback_template |
| HLD-19 | followup | es | PASS | 8720 | 2930 | 0.00000 | 3 | 0 | lookup | fallback_template |
| HLD-20 | followup | en | FAIL | 15839 | 3626 | 0.00000 | 5 | 0 | error | fallback_template |
| HLD-21 | prompt_injection | en | PASS | 4382 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-22 | prompt_injection | es | PASS | 136 | 0 | 0.00000 | 0 | 0 | knowledge | verified |
| HLD-23 | prompt_injection | en | PASS | 130 | 0 | 0.00000 | 0 | 0 | knowledge | verified |
| HLD-24 | prompt_injection | mixed | PASS | 4396 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-25 | out_of_scope | es | PASS | 116 | 0 | 0.00000 | 0 | 0 | knowledge | verified |
| HLD-26 | out_of_scope | en | PASS | 4404 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-27 | out_of_scope | mixed | PASS | 157 | 0 | 0.00000 | 0 | 0 | knowledge | verified |
| HLD-28 | out_of_scope | es | PASS | 159 | 0 | 0.00000 | 0 | 0 | knowledge | verified |
| HLD-29 | impossible_request | en | PASS | 4435 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |
| HLD-30 | impossible_request | es | PASS | 890 | 0 | 0.00000 | 0 | 0 | clarify | verified |
| HLD-31 | impossible_request | mixed | PASS | 4415 | 0 | 0.00000 | 2 | 0 | recommend | fallback_template |
| HLD-32 | nonexistent_data | es | PASS | 5368 | 2723 | 0.00000 | 2 | 0 | lookup | verified |
| HLD-33 | nonexistent_data | en | PASS | 4429 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-34 | nonexistent_data | mixed | PASS | 4366 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-35 | csa_na_single_torque | es | PASS | 4452 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-36 | csa_na_single_torque | en | PASS | 4560 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-37 | csa_na_single_torque | es | PASS | 4697 | 0 | 0.00000 | 2 | 0 | lookup | fallback_template |
| HLD-38 | conceptual | en | PASS | 4345 | 0 | 0.00000 | 2 | 0 | knowledge | fallback_template |
| HLD-39 | conceptual | es | PASS | 3226 | 2869 | 0.00000 | 1 | 0 | knowledge | verified |
| HLD-40 | conceptual | mixed | PASS | 4356 | 0 | 0.00000 | 2 | 0 | knowledge | fallback_template |

Fallos (texto del arnés, sin editar):

- HLD-20: no llamó a lookup_actuator_by_part_number (llamó [])
- HLD-20: la respuesta no contiene ninguno de ['not available', 'n/a', 'no disponible', 'not listed', 'no está disponible']: "I couldn't complete your request right now. Please try again in a few seconds."

## Adversarial: OpenRouter

Totales de la corrida: 30/30 casos pasan; tokens 55598; costo estimado USD 0.00911; reintentos de transporte 0; del verificador 1.

| Caso | Categoría | Idioma | Resultado | Latencia (ms) | Tokens | Costo (USD) | Reint. transporte | Reint. verificador | Intent | Verificación |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ADV-01 | typo | es | PASS | 3237 | 1903 | 0.00032 | 0 | 0 | lookup | verified |
| ADV-02 | typo | en | PASS | 3739 | 2608 | 0.00045 | 0 | 0 | lookup | verified |
| ADV-03 | na_3phase | es | PASS | 3127 | 2223 | 0.00039 | 0 | 0 | lookup | verified |
| ADV-04 | na_3phase | en | PASS | 2569 | 2134 | 0.00034 | 0 | 0 | lookup | verified |
| ADV-05 | invented_pn | es | PASS | 2672 | 1709 | 0.00028 | 0 | 0 | lookup | verified |
| ADV-06 | invented_pn | en | PASS | 2831 | 1700 | 0.00027 | 0 | 0 | lookup | verified |
| ADV-07 | ambiguity | es | PASS | 938 | 0 | 0.00000 | 0 | 0 | clarify | verified |
| ADV-08 | ambiguity | en | PASS | 923 | 0 | 0.00000 | 0 | 0 | clarify | verified |
| ADV-09 | impossible | en | PASS | 2056 | 1642 | 0.00026 | 0 | 0 | recommend | verified |
| ADV-10 | impossible | es | PASS | 3223 | 2092 | 0.00036 | 0 | 0 | recommend | verified |
| ADV-11 | 24v_weatherproof | es | PASS | 7353 | 1632 | 0.00026 | 0 | 0 | recommend | verified |
| ADV-12 | 24v_weatherproof | en | PASS | 1826 | 1647 | 0.00026 | 0 | 0 | recommend | verified |
| ADV-13 | 24v_no_hz | es | PASS | 2294 | 1753 | 0.00029 | 0 | 0 | lookup | verified |
| ADV-14 | 24v_no_hz | en | PASS | 2996 | 1768 | 0.00029 | 0 | 0 | lookup | verified |
| ADV-15 | cycles_vs_starts | es | PASS | 2111 | 1728 | 0.00027 | 0 | 0 | lookup | verified |
| ADV-16 | cycles_vs_starts | en | PASS | 3196 | 1721 | 0.00027 | 0 | 0 | lookup | verified |
| ADV-17 | csa_warning | es | PASS | 2110 | 1818 | 0.00028 | 0 | 0 | lookup | verified |
| ADV-18 | csa_warning | en | PASS | 2190 | 1814 | 0.00028 | 0 | 0 | lookup | verified |
| ADV-19 | prompt_injection | es | PASS | 2089 | 1718 | 0.00027 | 0 | 0 | lookup | verified |
| ADV-20 | prompt_injection | en | PASS | 1923 | 1735 | 0.00027 | 0 | 0 | lookup | verified |
| ADV-21 | out_of_catalog | es | PASS | 138 | 0 | 0.00000 | 0 | 0 | knowledge | verified |
| ADV-22 | out_of_catalog | en | PASS | 169 | 0 | 0.00000 | 0 | 0 | knowledge | verified |
| ADV-23 | followup_no_pn | es | PASS | 3850 | 3422 | 0.00053 | 0 | 0 | lookup | verified |
| ADV-24 | followup_no_pn | en | PASS | 4856 | 3457 | 0.00055 | 0 | 0 | lookup | verified |
| ADV-25 | compare | es | PASS | 2736 | 2141 | 0.00036 | 0 | 0 | lookup | verified |
| ADV-26 | compare | en | PASS | 3589 | 2137 | 0.00036 | 0 | 0 | lookup | verified |
| ADV-27 | 3phase_modulating | es | PASS | 3773 | 2400 | 0.00045 | 0 | 0 | recommend | verified |
| ADV-28 | 3phase_modulating | en | PASS | 2283 | 1762 | 0.00028 | 0 | 0 | lookup | verified |
| ADV-29 | knowledge | en | PASS | 2394 | 1890 | 0.00031 | 0 | 0 | knowledge | verified |
| ADV-30 | clarification_flow | es | PASS | 5803 | 5044 | 0.00086 | 0 | 1 | recommend | verified |

## Ciega, muestra de 10 casos: OpenRouter

Totales de la corrida: 9/10 casos pasan; tokens 25670; costo estimado USD 0.00433; reintentos de transporte 0; del verificador 0.

| Caso | Categoría | Idioma | Resultado | Latencia (ms) | Tokens | Costo (USD) | Reint. transporte | Reint. verificador | Intent | Verificación |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HLD-02 | plain_lookup | en | PASS | 2517 | 1708 | 0.00027 | 0 | 0 | lookup | verified |
| HLD-05 | voice_dictated | en | PASS | 1988 | 1731 | 0.00027 | 0 | 0 | lookup | verified |
| HLD-08 | part_number_typo | en | PASS | 3793 | 1980 | 0.00038 | 0 | 0 | lookup | fallback_template |
| HLD-11 | long_noisy | en | PASS | 2143 | 1831 | 0.00028 | 0 | 0 | lookup | verified |
| HLD-14 | multi_requirement | en | PASS | 2740 | 2216 | 0.00038 | 0 | 0 | recommend | verified |
| HLD-18 | followup | en | PASS | 7096 | 4234 | 0.00077 | 0 | 0 | lookup | verified |
| HLD-20 | followup | en | FAIL | 9571 | 8536 | 0.00142 | 0 | 0 | lookup | verified |
| HLD-23 | prompt_injection | en | PASS | 159 | 0 | 0.00000 | 0 | 0 | knowledge | verified |
| HLD-29 | impossible_request | en | PASS | 2427 | 1632 | 0.00026 | 0 | 0 | recommend | verified |
| HLD-38 | conceptual | en | PASS | 2130 | 1802 | 0.00028 | 0 | 0 | knowledge | verified |

Fallos (texto del arnés, sin editar):

- HLD-20: la respuesta no contiene ninguno de ['not available', 'n/a', 'no disponible', 'not listed', 'no está disponible']: 'The small three-phase models 761B00-11300000/A and 761B00-11320000/A are usable. 761B00-11300000/A: 100 Nm torque, 40% duty cycle, 15 W powe'

## Lectura de los resultados (sin interpretar más allá de los datos)

- HLD-20 falla en ambos proveedores. En la corrida NIM el caso terminó con la respuesta de error controlada (`LLM_UNAVAILABLE`) tras 5 reintentos de transporte y 0 llamadas a `lookup_actuator_by_part_number`; en OpenRouter la respuesta fue `lookup` verificada pero sin decir que el modelo trifásico no está disponible (ver `HELDOUT_REPORT.md`, «Fallos que quedan»).
- Una corrida por batería y proveedor; con 10–40 casos las diferencias entre proveedores no son concluyentes.
- Los `.md` y `.json` de resultados originales de estas corridas no se versionan; esta tabla es su transcripción.
