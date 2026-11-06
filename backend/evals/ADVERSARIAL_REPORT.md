# Casos adversarios — corrida con LLM contra el oráculo

- Proveedor/modelo: `openrouter` / `openai/gpt-4o-mini`
- Fecha: `2026-11-06 20:37:46 UTC`
- Resultado: **30/30**

| Caso | Idioma | Categoría | Estado | Latencia ms | Tokens | Costo USD | Reint. verif/LLM | Intent | Verificación |
|---|---|---|---|---|---|---|---|---|---|
| ADV-01 | es | typo | PASS | 3396 | 2457 | 0.00040 | 0/0 | lookup | verified |
| ADV-02 | en | typo | PASS | 3754 | 3183 | 0.00055 | 0/0 | lookup | fallback_template |
| ADV-03 | es | na_3phase | PASS | 5405 | 2908 | 0.00056 | 0/0 | lookup | verified |
| ADV-04 | en | na_3phase | PASS | 2708 | 2716 | 0.00044 | 0/0 | lookup | verified |
| ADV-05 | es | invented_pn | PASS | 2778 | 2278 | 0.00037 | 0/0 | lookup | verified |
| ADV-06 | en | invented_pn | PASS | 3128 | 2258 | 0.00036 | 0/0 | lookup | verified |
| ADV-07 | es | ambiguity | PASS | 197 | 0 | 0.00000 | 0/0 | clarify | verified |
| ADV-08 | en | ambiguity | PASS | 171 | 0 | 0.00000 | 0/0 | clarify | verified |
| ADV-09 | en | impossible | PASS | 2422 | 2197 | 0.00034 | 0/0 | recommend | verified |
| ADV-10 | es | impossible | PASS | 3573 | 2662 | 0.00045 | 0/0 | recommend | verified |
| ADV-11 | es | 24v_weatherproof | PASS | 2435 | 2192 | 0.00034 | 0/0 | recommend | verified |
| ADV-12 | en | 24v_weatherproof | PASS | 2239 | 2201 | 0.00034 | 0/0 | recommend | verified |
| ADV-13 | es | 24v_no_hz | PASS | 2620 | 2296 | 0.00036 | 0/0 | lookup | verified |
| ADV-14 | en | 24v_no_hz | PASS | 2326 | 2331 | 0.00038 | 0/0 | lookup | verified |
| ADV-15 | es | cycles_vs_starts | PASS | 2264 | 2281 | 0.00036 | 0/0 | lookup | verified |
| ADV-16 | en | cycles_vs_starts | PASS | 2113 | 2275 | 0.00036 | 0/0 | lookup | verified |
| ADV-17 | es | csa_warning | PASS | 2373 | 2374 | 0.00037 | 0/0 | lookup | verified |
| ADV-18 | en | csa_warning | PASS | 2236 | 2370 | 0.00036 | 0/0 | lookup | verified |
| ADV-19 | es | prompt_injection | PASS | 2301 | 2269 | 0.00035 | 0/0 | lookup | verified |
| ADV-20 | en | prompt_injection | PASS | 2203 | 2283 | 0.00035 | 0/0 | lookup | verified |
| ADV-21 | es | out_of_catalog | PASS | 115 | 0 | 0.00000 | 0/0 | knowledge | verified |
| ADV-22 | en | out_of_catalog | PASS | 135 | 0 | 0.00000 | 0/0 | knowledge | verified |
| ADV-23 | es | followup_no_pn | PASS | 4257 | 4542 | 0.00071 | 0/0 | lookup | verified |
| ADV-24 | en | followup_no_pn | PASS | 4762 | 4592 | 0.00072 | 0/0 | lookup | verified |
| ADV-25 | es | compare | PASS | 3053 | 2697 | 0.00044 | 0/0 | lookup | verified |
| ADV-26 | en | compare | PASS | 2933 | 2706 | 0.00045 | 0/0 | lookup | verified |
| ADV-27 | es | 3phase_modulating | PASS | 4038 | 2955 | 0.00053 | 0/0 | recommend | verified |
| ADV-28 | en | 3phase_modulating | PASS | 2752 | 2317 | 0.00037 | 0/0 | lookup | verified |
| ADV-29 | en | knowledge | PASS | 2348 | 2460 | 0.00040 | 0/0 | knowledge | verified |
| ADV-30 | es | clarification_flow | PASS | 3403 | 2990 | 0.00050 | 0/0 | recommend | verified |
