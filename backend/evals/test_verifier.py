"""Verificador numérico (REGLA 4), plantillas de respaldo, idioma, alertas localizadas, costo y títulos. Sin LLM."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import LLMConfig, estimate_cost_usd  # noqa: E402
from app.fallback import build_fallback_answer  # noqa: E402
from app.i18n import ALERTS, detect_language, make_short_title, render_alert  # noqa: E402
from app.verifier import extract_numbers, extract_quantities, known_part_keys, load_known_parts, verify_answer  # noqa: E402

PN = "763B00-11300000/A"
ROW = {
    "base_part_number": PN,
    "size_code": "763B",
    "power_supply": "110V Single Phase",
    "enclosure_type": "Weatherproof",
    "on_off_torque_nm": 500,
    "on_off_torque_in_lbs": 4400,
    "modulating_torque_nm": 380,
    "modulating_torque_in_lbs": 3350,
    "fla_60hz_amps": 4.8,
    "motor_power_watts": 90,
}
TOOL_OUT = [{"status": "EXACT_MATCH", "actuators": [ROW]}]
KNOWN = known_part_keys([ROW, {"base_part_number": "766A00-11320000/A", "size_code": "766A"}])


def check(answer, user="specs of 763B00-11300000/A", outs=TOOL_OUT):
    return verify_answer(answer, outs, user, KNOWN)


# ----------------------------------------------------------------- extracción
def test_extraction_ignores_part_numbers_codes_and_list_markers():
    toks = [r for r, _ in extract_numbers("763B00-11300000/A, T4, S4, IIB.\n1) first 25 %", apply_exceptions=True)]
    assert toks == ["25"]


@pytest.mark.parametrize("tok,expected", [("4,800", 4800.0), ("4,8", 4.8), ("1.500", 1500.0), ("6 650", 6650.0)])
def test_separator_candidates(tok, expected):
    (_, cands), = extract_numbers(tok)
    assert expected in cands


# ----------------------------------------------------------------- respuestas adversarias
def test_correct_answer_is_verified():
    r = check(f"The {PN} delivers 500 Nm (4,400 in-lbs) on/off, 380 Nm modulating, 90 W and 4.8 A FLA at 60 Hz.")
    assert r.ok and r.status == "verified" and r.numbers_checked >= 6


def test_invented_number_is_flagged():
    r = check(f"The {PN} draws 120 W of motor power.")
    assert not r.ok and r.ungrounded == ["120"]


def test_model_converted_number_is_flagged():
    # 500 Nm -> ~369 ft-lbs: conversión hecha por el modelo, no presente en la salida de herramientas
    r = check(f"The {PN} gives 500 Nm, about 369 ft-lbs.")
    assert r.ungrounded == ["369"]


def test_conversion_already_in_tool_output_is_allowed():
    assert check(f"{PN}: 500 Nm = 4400 in-lbs.").ok


def test_user_number_is_allowed():
    r = check("A 750 Nm requirement is above this model.", user="I need 750 Nm")
    assert r.ok


def test_user_number_does_not_justify_other_numbers():
    r = check("750 Nm is above the 500 Nm maximum and the 999 Nm option.", user="I need 750 Nm")
    assert r.ungrounded == ["999"]


def test_fake_part_number_is_flagged_and_real_one_is_not():
    r = check("Compare 761B00-11399999/A with 763B00-11300000/A: 500 Nm.")
    assert r.ungrounded == ["PN:761B00-11399999/A"]


def test_part_number_echoed_from_user_is_allowed_even_if_unknown():
    r = check("The code 761800-11300000/A does not exist.", user="specs of 761800-11300000/A")
    assert r.ok


def test_size_codes_validated():
    assert check("Sizes 766A00 and 763B are in the catalog.", user="x").ok
    assert check("Size 769Z is great.", user="x").ungrounded == ["PN:769Z"]


def test_no_numbers_no_tools_is_verified_with_zero_checked():
    r = check("Which voltage do you need?", user="recommend an actuator", outs=[])
    assert r.ok and r.numbers_checked == 0


def test_numbers_without_any_tool_are_flagged():
    r = check("It delivers 500 Nm.", user="hola", outs=[])
    assert r.ungrounded == ["500"]


def test_spanish_decimal_comma_matches():
    assert check("Consume 4,8 A a 60 Hz y 90 W.", user="y su corriente").ok  # 60 Hz respaldado por el campo fla_60hz_amps
    assert check("Consume 4,8 A a 50 Hz.", user="y su corriente").ungrounded == ["50"]  # no hay campo de 50 Hz
    assert check("Consume 4,8 A y 90 W.", user="y su corriente").ok


def test_designation_tokens_and_ninety_degrees_are_free():
    assert check("Giro de 90° con servicio S4 y clase T4.", user="x", outs=[]).ok


def test_numbers_from_tool_string_fields_are_allowed():
    # "110V" sólo aparece dentro de power_supply
    assert check("It runs on 110V single phase.").ok


def test_known_parts_from_database():
    keys = load_known_parts()
    assert "763B0011300000A" in keys and "763B00" in keys and "763B" in keys


# ----------------------------------------------------------------- plantillas de respaldo (cortas)
@pytest.mark.parametrize("lang,torque", [("en", "on/off torque 500 Nm (4400 in-lbs)"), ("es", "torque on/off 500 Nm (4400 in-lbs)")])
def test_fallback_template_is_short_and_covers_only_default_groups(lang, torque):
    text = build_fallback_answer(lang, [ROW], [], [])
    assert text.startswith(PN) and torque in text and "90 W" in text
    assert "FLA" not in text and chr(10) not in text and len(text.split()) <= 40


def test_fallback_follows_requested_groups():
    text = build_fallback_answer("en", [ROW], [], [], groups=["current"])
    assert "FLA 4.8 A at 60 Hz" in text and "torque" not in text and "90 W" not in text


def test_infer_groups_from_query_and_focus():
    from app.fallback import infer_groups

    assert infer_groups("¿cuánta corriente consume?") == ["current"]
    assert infer_groups("potencia y velocidad") == ["speed", "power"]
    assert infer_groups("specs please") == ["torque", "power"]
    assert infer_groups("anything", ["duty"]) == ["duty"]


def test_fallback_template_numbers_are_all_in_the_row():
    for groups in (None, ["current"], ["torque", "duty", "speed", "current", "power"]):
        text = build_fallback_answer("es", [ROW], [], [], groups=groups)
        allowed = verify_answer(text, [ROW], "", KNOWN)
        assert allowed.ok, allowed.ungrounded


def test_fallback_single_torque_row_is_not_labeled_onoff_or_modulating():
    row = {**ROW, "phase_type": "3 Phase", "modulating_torque_nm": None, "modulating_torque_in_lbs": None}
    en = build_fallback_answer("en", [row], [], [])
    es = build_fallback_answer("es", [row], [], [])
    assert "single output torque 500 Nm" in en and "on/off torque" not in en
    assert "torque de salida único 500 Nm" in es and "torque on/off" not in es


def test_fallback_names_only_the_first_row_and_first_alert():
    rows = [{**ROW, "base_part_number": f"763B00-1130000{i}/A"} for i in range(5)]
    text = build_fallback_answer("en", rows, ["Alert text.", "Second."], [])
    assert text.count("763B00-") == 1 and "+4 more" in text and text.endswith("Alert text.")
    assert build_fallback_answer("es", rows[:2], [], [], recommend=True).startswith("Mejor opción: 763B00-")


def test_fallback_without_rows_uses_alerts_knowledge_or_generic_message():
    assert build_fallback_answer("es", [], ["Aviso."], []) == "Aviso."
    kb = [{"status": "KNOWLEDGE_RETRIEVED", "chunks": [{"title": "T", "content": "C"}]}]
    assert build_fallback_answer("en", [], [], kb) == "C"
    assert "No pude verificar" in build_fallback_answer("es", [], [], [])
    assert "could not verify" in build_fallback_answer("en", [], [], [])


# ----------------------------------------------------------------- verificador por unidad y fila (bloque B)
PN_B = "764A00-11320000/A"
ROW_B = {
    "base_part_number": PN_B, "size_code": "764A", "power_supply": "220V Single Phase", "enclosure_type": "Weatherproof",
    "on_off_torque_nm": 750, "on_off_torque_in_lbs": 6650, "modulating_torque_nm": 680, "modulating_torque_in_lbs": 6000,
    "speed_60hz_sec": 28, "speed_50hz_sec": 33, "fla_60hz_amps": 3.0, "fla_50hz_amps": 3.0, "lra_60hz_amps": 3.6,
    "on_off_duty_cycle_pct": 40, "cycles_per_hour": 36, "modulating_duty_cycle_pct": 40, "starts_per_hour": 960,
    "motor_power_watts": 180,
}
OUT2 = [{"status": "EXACT_MATCH", "actuators": [ROW, ROW_B]}]
KNOWN2 = known_part_keys([ROW, ROW_B])


def check2(answer, user="compare them"):
    return verify_answer(answer, OUT2, user, KNOWN2)


def test_correct_value_in_wrong_row_fails():
    # 180 W es la potencia de 764A, no de 763B
    r = check2(f"The {PN} draws 180 W.")
    assert r.ungrounded == ["180 W"]
    # y 90 W es de 763B, no de 764A
    assert check2(f"The {PN_B} draws 90 W.").ungrounded == ["90 W"]


def test_correct_value_in_right_row_passes():
    assert check2(f"The {PN} draws 90 W and the {PN_B} draws 180 W.").ok
    assert check2(f"{PN}: 500 Nm on/off, 4.8 A FLA at 60 Hz. {PN_B}: 28 s at 60 Hz.").ok


def test_wrong_unit_fails_even_if_the_number_exists():
    assert check2(f"The {PN} turns in 90 s.").ungrounded == ["90 s"]       # 90 es W
    assert check2(f"The {PN_B} has 28 A FLA.").ungrounded == ["28 A"]    # 28 existe, pero en velocidad
    assert check2(f"{PN}: 4.8 W.").ungrounded == ["4.8 W"]


def test_same_number_in_two_families_passes_for_the_right_one_only():
    row = {**ROW, "speed_60hz_sec": 90}  # 90 s y 90 W en la misma fila
    out = [{"actuators": [row]}]
    assert verify_answer(f"{PN} turns in 90 s and draws 90 W.", out, "", KNOWN).ok
    row2 = {**ROW, "speed_60hz_sec": 26}
    assert verify_answer(f"{PN} turns in 90 s.", [{"actuators": [row2]}], "", KNOWN).ungrounded == ["90 s"]


def test_legit_conversion_already_in_tool_output_passes_but_other_unit_does_not():
    assert check2(f"{PN}: 500 Nm, which is 4400 in-lbs.").ok
    assert check2(f"{PN}: 500 in-lbs.").ungrounded == ["500 in-lbs"]   # 500 existe, pero en Nm
    assert check2(f"{PN}: 4400 Nm.").ungrounded == ["4400 Nm"]


def test_sentence_with_several_parts_accepts_value_from_any_cited_row():
    assert check2(f"{PN} and {PN_B} differ: 90 W versus 180 W.").ok
    assert check2(f"Both {PN} and {PN_B} list 500 Nm.").ok  # no atribuible: existe en una de las citadas


def test_sentence_without_part_number_uses_any_row_of_the_turn_family():
    assert check2("The second one draws 180 W.").ok
    assert check2("The second one draws 181 W.").ungrounded == ["181"]
    assert check2("It turns in 180 s.").ungrounded == ["180 s"]


def test_ranges_and_lists_share_the_trailing_unit():
    assert check2(f"{PN_B}: 28 s at 60 Hz and 33 s at 50 Hz.").ungrounded == []
    r = check2(f"{PN_B}: 28/33 s.")
    assert r.ok
    assert check2(f"{PN_B}: 28/34 s.").ungrounded == ["34"]


def test_percent_and_rates_belong_to_their_family():
    assert check2(f"{PN_B}: S4 40%, 36 cycles/h and 960 starts/h.").ok
    assert check2(f"{PN_B}: 36 starts/h.").ungrounded == ["36 starts/h"]
    assert check2(f"{PN_B}: 960 cycles per hour.").ungrounded == ["960 cycles/h"]
    assert check2(f"{PN_B}: 36 ciclos/h y 960 arranques/h.").ok


def test_voltage_and_frequency_families():
    assert check2(f"{PN} runs on 110V and 60 Hz.").ok
    assert check2(f"{PN} runs on 220V.").ungrounded == ["220 V"]        # 220V es de la otra fila (power_supply)
    assert check2(f"{PN_B} at 50 Hz: 3.0 A.").ok


def test_designations_are_not_quantities():
    assert extract_quantities_units("S4 duty, T4, IIB") == []


# ----------------------------------------------------------------- idioma y alertas
@pytest.mark.parametrize("text,locale,expected", [
    ("¿Cuál es la potencia del motor 763B00-11300000/A?", None, "es"),
    ("What is the motor power of 763B00-11300000/A?", None, "en"),
    ("Necesito un actuador para 24 V con al menos 200 Nm", None, "es"),
    ("Give me the specs of the 764A", None, "en"),
    ("What is the motor power?", "es", "es"),
    ("¿Cuál es la potencia?", "en", "en"),
])
def test_language_detection_and_locale_priority(text, locale, expected):
    assert detect_language(text, locale) == expected


def test_language_falls_back_to_previous_user_messages():
    assert detect_language("763B00-11300000/A", None, ["Dame las especificaciones de este actuador"]) == "es"
    assert detect_language("763B00-11300000/A") == "en"


@pytest.mark.parametrize("code", sorted(ALERTS))
def test_every_alert_code_has_both_languages_and_a_severity(code):
    entry = ALERTS[code]
    assert entry["severity"] in ("info", "warning", "error") and entry["es"] and entry["en"]


def test_alert_rendering_is_localized_with_parameters():
    a = {"code": "TORQUE_ABOVE_CEILING", "params": {"filter_kind": "voltage", "filter_value": 24, "ceiling": 240, "requested": 1000}}
    en, es = render_alert(a, "en"), render_alert(a, "es")
    assert en["message"] == "The highest torque listed for 24V models is 240 Nm, below the requested 1000 Nm."
    assert "modelos de 24V" in es["message"] and "240 Nm" in es["message"]
    assert en["severity"] == es["severity"] == "warning" and en["code"] == "TORQUE_ABOVE_CEILING"
    single = render_alert({"code": "SINGLE_TORQUE_RATING", "params": {}}, "es")["message"]
    assert single.startswith("La hoja de datos da un único torque de salida para trifásico")


# ----------------------------------------------------------------- títulos de sesión y costo
def test_short_titles():
    assert make_short_title([PN], {}, "es") == PN
    assert make_short_title([PN, "764A00-11320000/A"], {}, "en") == f"{PN} +1"
    assert make_short_title([], {"min_torque_nm": 200.0, "voltage_num": 24, "enclosure_type": "Explosionproof"}, "es") == "Recomendación ≥200 Nm · 24V · Explosionproof"
    assert make_short_title([], {"min_torque_nm": 200.0}, "en") == "Recommendation ≥200 Nm"
    assert make_short_title([PN, "x"], {"min_torque_nm": 200.0}, "en", recommend=True) == "Recommendation ≥200 Nm"
    assert make_short_title([PN], {}, "en", recommend=True) == PN
    assert make_short_title([], {}, "en") is None


def test_cost_estimate_uses_listed_prices_and_nim_is_free():
    pricing = {"openai/gpt-4o-mini": {"input": 0.15, "output": 0.60}}
    cfg = LLMConfig("openrouter", "https://x", "openai/gpt-4o-mini", pricing=pricing)
    assert estimate_cost_usd(cfg, 1_000_000, 1_000_000) == pytest.approx(0.75)
    assert estimate_cost_usd(cfg, 4000, 200) == pytest.approx(0.00072)
    assert estimate_cost_usd(LLMConfig("nim", "https://x", "nvidia/m", pricing={}), 10**6, 10**6) == 0.0


def extract_quantities_units(text):
    return [(q.raw, q.unit) for q in extract_quantities(text)]
