# Casos adversarios — corrida con LLM contra el oráculo

- Proveedor/modelo: `openrouter` / `openai/gpt-4o-mini`
- Fecha: `2026-11-06 18:09:58 UTC`
- Resultado: **30/30**

| Caso | Idioma | Categoría | Estado | Latencia ms | Tokens | Costo USD | Reint. verif/LLM | Intent | Verificación |
|---|---|---|---|---|---|---|---|---|---|
| ADV-01 | es | typo | PASS | 3386 | 1903 | 0.00032 | 0/0 | lookup | verified |
| ADV-02 | en | typo | PASS | 3906 | 2608 | 0.00045 | 0/0 | lookup | verified |
| ADV-03 | es | na_3phase | PASS | 3549 | 2223 | 0.00039 | 0/0 | lookup | verified |
| ADV-04 | en | na_3phase | PASS | 2624 | 2134 | 0.00034 | 0/0 | lookup | verified |
| ADV-05 | es | invented_pn | PASS | 2231 | 1709 | 0.00028 | 0/0 | lookup | verified |
| ADV-06 | en | invented_pn | PASS | 2081 | 1700 | 0.00027 | 0/0 | lookup | verified |
| ADV-07 | es | ambiguity | PASS | 162 | 0 | 0.00000 | 0/0 | clarify | verified |
| ADV-08 | en | ambiguity | PASS | 182 | 0 | 0.00000 | 0/0 | clarify | verified |
| ADV-09 | en | impossible | PASS | 2279 | 1643 | 0.00026 | 0/0 | recommend | verified |
| ADV-10 | es | impossible | PASS | 3473 | 2098 | 0.00036 | 0/0 | recommend | verified |
| ADV-11 | es | 24v_weatherproof | PASS | 2061 | 1638 | 0.00026 | 0/0 | recommend | verified |
| ADV-12 | en | 24v_weatherproof | PASS | 1873 | 1647 | 0.00026 | 0/0 | recommend | verified |
| ADV-13 | es | 24v_no_hz | PASS | 2288 | 1753 | 0.00029 | 0/0 | lookup | verified |
| ADV-14 | en | 24v_no_hz | PASS | 2365 | 1768 | 0.00029 | 0/0 | lookup | verified |
| ADV-15 | es | cycles_vs_starts | PASS | 2522 | 1728 | 0.00027 | 0/0 | lookup | verified |
| ADV-16 | en | cycles_vs_starts | PASS | 4318 | 1721 | 0.00027 | 0/0 | lookup | verified |
| ADV-17 | es | csa_warning | PASS | 1985 | 1818 | 0.00028 | 0/0 | lookup | verified |
| ADV-18 | en | csa_warning | PASS | 2758 | 1814 | 0.00028 | 0/0 | lookup | verified |
| ADV-19 | es | prompt_injection | PASS | 3882 | 1718 | 0.00027 | 0/0 | lookup | verified |
| ADV-20 | en | prompt_injection | PASS | 2099 | 1734 | 0.00027 | 0/0 | lookup | verified |
| ADV-21 | es | out_of_catalog | PASS | 90 | 0 | 0.00000 | 0/0 | knowledge | verified |
| ADV-22 | en | out_of_catalog | PASS | 123 | 0 | 0.00000 | 0/0 | knowledge | verified |
| ADV-23 | es | followup_no_pn | PASS | 4634 | 3425 | 0.00054 | 0/0 | lookup | verified |
| ADV-24 | en | followup_no_pn | PASS | 4370 | 3457 | 0.00055 | 0/0 | lookup | verified |
| ADV-25 | es | compare | PASS | 2935 | 2141 | 0.00036 | 0/0 | lookup | verified |
| ADV-26 | en | compare | PASS | 3124 | 2135 | 0.00036 | 0/0 | lookup | verified |
| ADV-27 | es | 3phase_modulating | PASS | 3826 | 2372 | 0.00043 | 0/0 | recommend | verified |
| ADV-28 | en | 3phase_modulating | PASS | 2544 | 1764 | 0.00029 | 0/0 | lookup | verified |
| ADV-29 | en | knowledge | PASS | 2853 | 1890 | 0.00031 | 0/0 | knowledge | verified |
| ADV-30 | es | clarification_flow | PASS | 6630 | 5060 | 0.00086 | 1/0 | recommend | verified |
