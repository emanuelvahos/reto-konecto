# Casos adversarios — corrida con LLM contra el oráculo

- Proveedor/modelo: `openrouter` / `openai/gpt-4o-mini`
- Fecha: `2026-11-06 23:57:55 UTC`
- Resultado: **30/30**

| Caso | Idioma | Categoría | Estado | Latencia ms | Tokens | Costo USD | Reint. verif/LLM | Intent | Verificación |
|---|---|---|---|---|---|---|---|---|---|
| ADV-01 | es | typo | PASS | 3703 | 2496 | 0.00042 | 0/0 | lookup | fallback_template |
| ADV-02 | en | typo | PASS | 9240 | 3183 | 0.00055 | 0/0 | lookup | fallback_template |
| ADV-03 | es | na_3phase | PASS | 4744 | 2886 | 0.00054 | 0/0 | lookup | verified |
| ADV-04 | en | na_3phase | PASS | 2334 | 2699 | 0.00043 | 0/0 | lookup | verified |
| ADV-05 | es | invented_pn | PASS | 2050 | 2274 | 0.00037 | 0/0 | lookup | verified |
| ADV-06 | en | invented_pn | PASS | 2537 | 2256 | 0.00036 | 0/0 | lookup | verified |
| ADV-07 | es | ambiguity | PASS | 93 | 0 | 0.00000 | 0/0 | clarify | verified |
| ADV-08 | en | ambiguity | PASS | 101 | 0 | 0.00000 | 0/0 | clarify | verified |
| ADV-09 | en | impossible | PASS | 1542 | 2197 | 0.00034 | 0/0 | recommend | verified |
| ADV-10 | es | impossible | PASS | 2925 | 2650 | 0.00045 | 0/0 | recommend | verified |
| ADV-11 | es | 24v_weatherproof | PASS | 1828 | 2192 | 0.00034 | 0/0 | recommend | verified |
| ADV-12 | en | 24v_weatherproof | PASS | 1894 | 2201 | 0.00034 | 0/0 | recommend | verified |
| ADV-13 | es | 24v_no_hz | PASS | 1832 | 2296 | 0.00036 | 0/0 | lookup | verified |
| ADV-14 | en | 24v_no_hz | PASS | 1878 | 2329 | 0.00037 | 0/0 | lookup | verified |
| ADV-15 | es | cycles_vs_starts | PASS | 1445 | 2281 | 0.00036 | 0/0 | lookup | verified |
| ADV-16 | en | cycles_vs_starts | PASS | 1524 | 2275 | 0.00036 | 0/0 | lookup | verified |
| ADV-17 | es | csa_warning | PASS | 1428 | 2374 | 0.00037 | 0/0 | lookup | verified |
| ADV-18 | en | csa_warning | PASS | 1422 | 2370 | 0.00036 | 0/0 | lookup | verified |
| ADV-19 | es | prompt_injection | PASS | 1935 | 2269 | 0.00035 | 0/0 | lookup | verified |
| ADV-20 | en | prompt_injection | PASS | 1452 | 2283 | 0.00035 | 0/0 | lookup | verified |
| ADV-21 | es | out_of_catalog | PASS | 56 | 0 | 0.00000 | 0/0 | knowledge | verified |
| ADV-22 | en | out_of_catalog | PASS | 64 | 0 | 0.00000 | 0/0 | knowledge | verified |
| ADV-23 | es | followup_no_pn | PASS | 2721 | 4542 | 0.00071 | 0/0 | lookup | verified |
| ADV-24 | en | followup_no_pn | PASS | 4879 | 4592 | 0.00072 | 0/0 | lookup | verified |
| ADV-25 | es | compare | PASS | 2057 | 2697 | 0.00044 | 0/0 | lookup | verified |
| ADV-26 | en | compare | PASS | 2265 | 2695 | 0.00044 | 0/0 | lookup | verified |
| ADV-27 | es | 3phase_modulating | PASS | 3436 | 2925 | 0.00051 | 0/0 | recommend | verified |
| ADV-28 | en | 3phase_modulating | PASS | 2187 | 2317 | 0.00037 | 0/0 | lookup | verified |
| ADV-29 | en | knowledge | PASS | 2074 | 2460 | 0.00040 | 0/0 | knowledge | verified |
| ADV-30 | es | clarification_flow | PASS | 4017 | 3010 | 0.00051 | 0/0 | recommend | verified |
