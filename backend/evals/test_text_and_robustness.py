"""Respuesta corta y limpia (postprocesado) y robustez ante fallos del LLM (reintentos con retroceso). Sin LLM real."""
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.agent as agent  # noqa: E402
from app.postprocess import clean_text, shorten  # noqa: E402
from app.tools import current_turn_tool_traces, lookup_actuator_by_part_number, recommend_actuators  # noqa: E402

PN = "763B00-11300000/A"


# ------------------------------------------------------------------ postprocesado
@pytest.mark.parametrize("raw,expected", [
    ("The **763B** has **500 Nm**.", "The 763B has 500 Nm."),
    ("# Specs\n## Torque\n500 Nm", "Specs Torque 500 Nm"),
    ("- 500 Nm\n- 380 Nm\n* 90 W", "500 Nm 380 Nm 90 W"),
    ("1. First 500 Nm\n2) Second 380 Nm", "First 500 Nm Second 380 Nm"),
    ("| Field | Value |\n|---|---|\n| Torque | 500 Nm |", "Field, Value Torque, 500 Nm"),
    ("Use `lookup` and __bold__ and *it*.", "Use lookup and bold and it."),
    ("> quoted 4.8 A", "quoted 4.8 A"),
    ("", ""),
])
def test_clean_text_strips_markdown(raw, expected):
    assert clean_text(raw) == expected


def test_clean_text_keeps_numbers_and_units_intact():
    assert clean_text("**26 s** at 60 Hz, 4.8 A, 4,400 in-lbs, 3.5 W") == "26 s at 60 Hz, 4.8 A, 4,400 in-lbs, 3.5 W"


def test_shorten_keeps_at_most_two_sentences_and_45_words():
    text = "It has 500 Nm. It also has 380 Nm. And 90 W more."
    assert shorten(text) == "It has 500 Nm. It also has 380 Nm."
    long_second = "First sentence. Then " + " ".join(["word"] * 60) + "."
    assert shorten(long_second) == "First sentence."
    assert shorten("One only.") == "One only." and shorten("") == ""
    assert shorten("4.8 A at 60 Hz. Next one.") == "4.8 A at 60 Hz. Next one."  # el decimal no corta la frase


# ------------------------------------------------------------------ cliente falso
class Boom(Exception):
    def __init__(self, status_code=None, name=None):
        super().__init__(f"boom {status_code}")
        self.status_code = status_code


class APITimeoutError(Exception):
    pass


class ScriptedExecutor:
    """Cada paso: una excepción a lanzar, o {"tool":..., "answer":..., "content": ...} como el ejecutor falso."""

    def __init__(self, steps):
        self.steps, self.calls, self.states = steps, 0, []

    def invoke(self, state, config=None):
        self.states.append(state)
        step = self.steps[min(self.calls, len(self.steps) - 1)]
        self.calls += 1
        if isinstance(step, Exception):
            raise step
        msgs = list(state["messages"])
        if step.get("tool"):
            name, args = step["tool"]
            {"lookup": lookup_actuator_by_part_number, "recommend": recommend_actuators}[name].invoke(args)
            msgs.append(ToolMessage(content="{}", tool_call_id="t1"))
        usage = {"input_tokens": 50, "output_tokens": 5, "total_tokens": 55}
        ai = AIMessage(content=step["answer"] or "", usage_metadata=usage)
        if step["answer"] is None:
            ai.content = None  # algunos proveedores devuelven content=None (la validación de pydantic no se repite al asignar)
        msgs.append(ai)
        return {"messages": msgs}


@pytest.fixture
def run(monkeypatch):
    monkeypatch.setattr(agent, "build_llm", lambda: None)
    sleeps = []
    monkeypatch.setattr(agent, "_sleep", sleeps.append)
    monkeypatch.setattr(agent, "RETRY_BASE_S", 1.0)

    def _run(steps, query=f"power of {PN}?", locale=None):
        ex = ScriptedExecutor(steps)
        monkeypatch.setattr(agent, "create_react_agent", lambda llm, tools: ex)
        return agent.run_agent_turn(query, [], [], {}, locale=locale), ex, sleeps

    return _run


OK = {"tool": ("lookup", {"part_number": PN}), "answer": f"The {PN} draws 90 W."}


@pytest.mark.parametrize("err", [Boom(500), Boom(503), Boom(429), APITimeoutError("t"), TimeoutError("t"), ConnectionError("c")])
def test_transient_errors_are_retried_with_exponential_backoff(run, err):
    (answer, ui, dbg, _, _, meta), ex, sleeps = run([err, err, OK])
    assert ex.calls == 3 and sleeps == [1.0, 2.0] and dbg["token_usage"]["llm_retries"] == 2
    assert meta["intent"] == "lookup" and meta["verification"]["status"] == "verified" and "90 W" in answer


def test_single_retry_succeeds(run):
    (_, _, dbg, _, _, meta), ex, sleeps = run([Boom(502), OK])
    assert ex.calls == 2 and sleeps == [1.0] and dbg["token_usage"]["llm_retries"] == 1 and meta["intent"] == "lookup"


@pytest.mark.parametrize("locale,needle", [("es", "no está disponible temporalmente"), ("en", "temporarily unavailable")])
def test_exhausted_retries_return_localized_error_not_an_exception(run, locale, needle):
    (answer, ui, dbg, parts, _, meta), ex, sleeps = run([Boom(503)], locale=locale)
    assert ex.calls == 3 and sleeps == [1.0, 2.0]
    assert meta["intent"] == "error" and needle in answer and meta["verification"]["numbers_checked"] == 0
    assert ui["display_type"] == "EDGE_CASE_ALERT" and ui["alerts"][0] == {"code": "LLM_UNAVAILABLE", "severity": "error", "message": answer}
    assert dbg["token_usage"]["llm_retries"] == 2 and dbg["language"] == locale


def test_non_transient_error_is_not_retried_but_still_reported(run):
    (answer, _, dbg, _, _, meta), ex, sleeps = run([Boom(401)], locale="en")
    assert ex.calls == 1 and sleeps == [] and meta["intent"] == "error" and dbg["token_usage"]["llm_retries"] == 0


@pytest.mark.parametrize("empty", ["", "   ", None])
def test_empty_or_none_content_is_retried(run, empty):
    (answer, _, dbg, _, _, meta), ex, sleeps = run([{"answer": empty}, OK])
    assert ex.calls == 2 and dbg["token_usage"]["llm_retries"] == 1 and meta["intent"] == "lookup"


def test_empty_after_tools_retries_from_the_tool_results_without_rerunning_tools(run):
    first = {"tool": ("lookup", {"part_number": PN}), "answer": ""}
    (answer, _, dbg, _, _, meta), ex, _ = run([first, {"answer": f"The {PN} draws 90 W."}])
    assert ex.calls == 2 and len(dbg["tool_calls"]) == 1  # una sola ejecución de la tool
    assert any(isinstance(m, ToolMessage) for m in ex.states[1]["messages"])


def test_failed_attempt_leaves_no_duplicate_tool_traces(run):
    class Flaky(ScriptedExecutor):
        def invoke(self, state, config=None):
            if self.calls == 0:
                self.calls += 1
                lookup_actuator_by_part_number.invoke({"part_number": PN})  # la tool corrió y luego falló el modelo
                raise Boom(500)
            return super().invoke(state, config)

    ex = Flaky([OK])
    import app.agent as a

    a.create_react_agent = lambda llm, tools: ex  # noqa: E731  (restaurado por monkeypatch en el fixture)
    out = a.run_agent_turn(f"power of {PN}?", [], [], {})
    assert len(out[2]["tool_calls"]) == 1


def test_llm_construction_failure_is_also_a_clean_error(monkeypatch):
    def boom():
        raise ValueError("no api key")

    monkeypatch.setattr(agent, "build_llm", boom)
    answer, ui, _, _, _, meta = agent.run_agent_turn("hola", [], [], {}, locale="es")
    assert meta["intent"] == "error" and "no está disponible" in answer


def test_retry_during_verifier_rewrite_falls_back_to_template(run):
    steps = [{"tool": ("lookup", {"part_number": PN}), "answer": f"The {PN} draws 120 W."}, Boom(503)]
    (answer, ui, _, _, _, meta), ex, _ = run(steps, locale="en")
    assert meta["verification"]["status"] == "fallback_template" and "90 W" in answer and "120" not in answer


# ------------------------------------------------------------------ respuestas cortas en el pipeline
def test_markdown_from_the_llm_is_removed_before_verification(run):
    steps = [{"tool": ("lookup", {"part_number": PN}), "answer": f"**{PN}**\n- Torque: **500 Nm** on/off\n- Power: 90 W\n\nMore text here."}]
    (answer, ui, _, _, _, meta), _, _ = run(steps)
    assert "*" not in answer and "\n" not in answer and answer.startswith(PN)
    assert meta["verification"]["status"] == "verified"


def test_answer_with_cards_is_truncated_to_two_sentences(run):
    steps = [{"tool": ("lookup", {"part_number": PN}), "answer": f"The {PN} draws 90 W. Its torque is 500 Nm. Its modulating torque is 380 Nm. Done."}]
    (answer, ui, _, _, _, _), _, _ = run(steps)
    assert answer == f"The {PN} draws 90 W. Its torque is 500 Nm." and ui["display_type"] == "SINGLE_SPEC_CARD"


def test_strict_verifier_runs_inside_the_pipeline(run):
    # 180 W es un valor real del catalogo, pero de otra fila y no de este turno -> ni siquiera esta en las salidas
    steps = [{"tool": ("lookup", {"part_number": PN}), "answer": f"The {PN} draws 180 W."}, {"answer": f"The {PN} turns in 90 s."}]
    (answer, _, dbg, _, _, meta), ex, _ = run(steps, locale="en")
    assert ex.calls == 2 and meta["verification"]["status"] == "fallback_template"
    assert meta["verification"]["ungrounded"] == ["90 s"] and "90 W" in answer
