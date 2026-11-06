# Casos adversarios — corrida con LLM contra el oráculo

- Proveedor/modelo: `openrouter` / `openai/gpt-4o-mini`
- Fecha: `2026-11-06 23:32:14 UTC`
- Resultado: **30/30**

| Caso | Idioma | Categoría | Estado | Latencia ms | Tokens | Costo USD | Reint. verif/LLM | Intent | Verificación |
|---|---|---|---|---|---|---|---|---|---|
| ADV-01 | es | typo | PASS | 2181 | 2457 | 0.00040 | 0/0 | lookup | verified |
| ADV-02 | en | typo | PASS | 3696 | 3214 | 0.00057 | 0/0 | lookup | fallback_template |
| ADV-03 | es | na_3phase | PASS | 5474 | 2929 | 0.00057 | 0/0 | lookup | verified |
| ADV-04 | en | na_3phase | PASS | 2060 | 2701 | 0.00043 | 0/0 | lookup | verified |
| ADV-05 | es | invented_pn | PASS | 2212 | 2266 | 0.00036 | 0/0 | lookup | verified |
| ADV-06 | en | invented_pn | PASS | 1699 | 2256 | 0.00036 | 0/0 | lookup | verified |
| ADV-07 | es | ambiguity | PASS | 185 | 0 | 0.00000 | 0/0 | clarify | verified |
| ADV-08 | en | ambiguity | PASS | 147 | 0 | 0.00000 | 0/0 | clarify | verified |
| ADV-09 | en | impossible | PASS | 1518 | 2197 | 0.00034 | 0/0 | recommend | verified |
| ADV-10 | es | impossible | PASS | 2931 | 2650 | 0.00045 | 0/0 | recommend | verified |
| ADV-11 | es | 24v_weatherproof | PASS | 2643 | 2192 | 0.00034 | 0/0 | recommend | verified |
| ADV-12 | en | 24v_weatherproof | PASS | 1325 | 2201 | 0.00034 | 0/0 | recommend | verified |
| ADV-13 | es | 24v_no_hz | PASS | 5024 | 2283 | 0.00036 | 0/0 | lookup | verified |
| ADV-14 | en | 24v_no_hz | PASS | 2216 | 2329 | 0.00037 | 0/0 | lookup | verified |
| ADV-15 | es | cycles_vs_starts | PASS | 1869 | 2281 | 0.00036 | 0/0 | lookup | verified |
| ADV-16 | en | cycles_vs_starts | PASS | 2889 | 2275 | 0.00036 | 0/0 | lookup | verified |
| ADV-17 | es | csa_warning | PASS | 1547 | 2374 | 0.00037 | 0/0 | lookup | verified |
| ADV-18 | en | csa_warning | PASS | 1516 | 2370 | 0.00036 | 0/0 | lookup | verified |
| ADV-19 | es | prompt_injection | PASS | 2093 | 2283 | 0.00036 | 0/0 | lookup | verified |
| ADV-20 | en | prompt_injection | PASS | 2330 | 2283 | 0.00035 | 0/0 | lookup | verified |
| ADV-21 | es | out_of_catalog | PASS | 119 | 0 | 0.00000 | 0/0 | knowledge | verified |
| ADV-22 | en | out_of_catalog | PASS | 105 | 0 | 0.00000 | 0/0 | knowledge | verified |
| ADV-23 | es | followup_no_pn | PASS | 11511 | 4542 | 0.00071 | 0/0 | lookup | verified |
| ADV-24 | en | followup_no_pn | PASS | 4537 | 4592 | 0.00072 | 0/0 | lookup | verified |
| ADV-25 | es | compare | PASS | 2654 | 2697 | 0.00044 | 0/0 | lookup | verified |
| ADV-26 | en | compare | PASS | 2345 | 2695 | 0.00044 | 0/0 | lookup | verified |
| ADV-27 | es | 3phase_modulating | PASS | 6155 | 2940 | 0.00052 | 0/0 | recommend | verified |
| ADV-28 | en | 3phase_modulating | PASS | 2418 | 2317 | 0.00037 | 0/0 | lookup | verified |
| ADV-29 | en | knowledge | PASS | 4235 | 2460 | 0.00040 | 0/0 | knowledge | verified |
| ADV-30 | es | clarification_flow | PASS | 4481 | 2998 | 0.00050 | 0/0 | recommend | verified |
