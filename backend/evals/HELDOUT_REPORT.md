# Casos adversarios — corrida con LLM contra el oráculo

- Proveedor/modelo: `openrouter` / `openai/gpt-4o-mini`
- Fecha: `2026-11-06 22:15:18 UTC`
- Resultado: **39/40**

| Caso | Idioma | Categoría | Estado | Latencia ms | Tokens | Costo USD | Reint. verif/LLM | Intent | Verificación |
|---|---|---|---|---|---|---|---|---|---|
| HLD-01 | es | plain_lookup | PASS | 2168 | 2265 | 0.00035 | 0/0 | lookup | verified |
| HLD-02 | en | plain_lookup | PASS | 1562 | 2263 | 0.00036 | 0/0 | lookup | verified |
| HLD-03 | mixed | plain_lookup | PASS | 1692 | 2345 | 0.00037 | 0/0 | lookup | verified |
| HLD-04 | es | voice_dictated | PASS | 6189 | 5782 | 0.00099 | 1/0 | lookup | fallback_template |
| HLD-05 | en | voice_dictated | PASS | 1354 | 2285 | 0.00036 | 0/0 | lookup | verified |
| HLD-06 | mixed | voice_dictated | PASS | 3526 | 2257 | 0.00035 | 0/0 | lookup | verified |
| HLD-07 | es | part_number_typo | PASS | 4563 | 2465 | 0.00041 | 0/0 | lookup | verified |
| HLD-08 | en | part_number_typo | PASS | 3558 | 2533 | 0.00046 | 0/0 | lookup | fallback_template |
| HLD-09 | mixed | part_number_typo | PASS | 2088 | 2527 | 0.00041 | 0/0 | lookup | verified |
| HLD-10 | es | long_noisy | PASS | 1236 | 2341 | 0.00037 | 0/0 | lookup | verified |
| HLD-11 | en | long_noisy | PASS | 1159 | 2384 | 0.00037 | 0/0 | lookup | verified |
| HLD-12 | mixed | long_noisy | PASS | 1219 | 2308 | 0.00036 | 0/0 | lookup | verified |
| HLD-13 | es | multi_requirement | PASS | 2980 | 2939 | 0.00050 | 0/0 | recommend | verified |
| HLD-14 | en | multi_requirement | PASS | 2632 | 2782 | 0.00047 | 0/0 | recommend | verified |
| HLD-15 | en | multi_requirement | PASS | 2095 | 2574 | 0.00043 | 0/0 | recommend | verified |
| HLD-16 | mixed | multi_requirement | PASS | 1922 | 2671 | 0.00044 | 0/0 | recommend | verified |
| HLD-17 | es | followup | PASS | 4761 | 4853 | 0.00083 | 0/0 | lookup | verified |
| HLD-18 | en | followup | PASS | 6222 | 5392 | 0.00098 | 0/0 | lookup | fallback_template |
| HLD-19 | es | followup | PASS | 3635 | 4861 | 0.00078 | 0/0 | lookup | verified |
| HLD-20 | en | followup | PASS | 9900 | 10332 | 0.00176 | 0/0 | lookup | verified |
| HLD-21 | en | prompt_injection | PASS | 1767 | 2280 | 0.00036 | 0/0 | lookup | verified |
| HLD-22 | es | prompt_injection | PASS | 50 | 0 | 0.00000 | 0/0 | knowledge | verified |
| HLD-23 | en | prompt_injection | PASS | 50 | 0 | 0.00000 | 0/0 | knowledge | verified |
| HLD-24 | mixed | prompt_injection | PASS | 1437 | 2256 | 0.00035 | 0/0 | lookup | verified |
| HLD-25 | es | out_of_scope | PASS | 53 | 0 | 0.00000 | 0/0 | knowledge | verified |
| HLD-26 | en | out_of_scope | PASS | 10012 | 4835 | 0.00075 | 0/0 | knowledge | verified |
| HLD-27 | mixed | out_of_scope | PASS | 52 | 0 | 0.00000 | 0/0 | knowledge | verified |
| HLD-28 | es | out_of_scope | PASS | 50 | 0 | 0.00000 | 0/0 | knowledge | verified |
| HLD-29 | en | impossible_request | PASS | 1225 | 2187 | 0.00034 | 0/0 | recommend | verified |
| HLD-30 | es | impossible_request | PASS | 76 | 0 | 0.00000 | 0/0 | clarify | verified |
| HLD-31 | mixed | impossible_request | PASS | 1230 | 2201 | 0.00034 | 0/0 | recommend | verified |
| HLD-32 | es | nonexistent_data | FAIL | 2173 | 2293 | 0.00036 | 0/0 | lookup | verified |
| HLD-33 | en | nonexistent_data | PASS | 2556 | 4601 | 0.00072 | 0/0 | lookup | verified |
| HLD-34 | mixed | nonexistent_data | PASS | 1477 | 2254 | 0.00036 | 0/0 | lookup | verified |
| HLD-35 | es | csa_na_single_torque | PASS | 1158 | 2374 | 0.00037 | 0/0 | lookup | verified |
| HLD-36 | en | csa_na_single_torque | PASS | 5447 | 2899 | 0.00055 | 0/0 | lookup | verified |
| HLD-37 | es | csa_na_single_torque | PASS | 1580 | 2327 | 0.00037 | 0/0 | lookup | verified |
| HLD-38 | en | conceptual | PASS | 1381 | 2356 | 0.00037 | 0/0 | knowledge | verified |
| HLD-39 | es | conceptual | PASS | 1703 | 2471 | 0.00040 | 0/0 | knowledge | verified |
| HLD-40 | mixed | conceptual | PASS | 1836 | 2420 | 0.00040 | 0/0 | knowledge | verified |

## Fallos

- **HLD-32**: la respuesta no contiene ninguno de ['no (tiene|existe|aplica|hay|cuenta)', 'fixed|fijo|única|single', 'no 50']: 'La velocidad del modelo 761X30-11380000/A de 24V es fija y toma 17 segundos para un giro de 90 grados.'
