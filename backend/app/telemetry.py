"""Telemetria por etapas: callback de LangChain que registra llamadas LLM y herramientas con start/duracion."""
import time
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler


class StepRecorder(BaseCallbackHandler):
    """Registra pasos {name, start_ms, duration_ms}; start_ms es relativo al inicio de la peticion (t0)."""

    raise_error = False

    def __init__(self, t0: float):
        self.t0 = t0
        self.steps: List[Dict[str, Any]] = []
        self._open: Dict[Any, Dict[str, Any]] = {}
        self._llm_calls = 0

    def _now_ms(self) -> float:
        return (time.perf_counter() - self.t0) * 1000

    def add_step(self, name: str, start_ms: float, duration_ms: float) -> None:
        self.steps.append({"name": name, "start_ms": round(start_ms, 2), "duration_ms": round(duration_ms, 2)})

    def _start(self, run_id: Any, name: str) -> None:
        self._open[run_id] = {"name": name, "start": self._now_ms()}

    def _end(self, run_id: Any) -> None:
        s = self._open.pop(run_id, None)
        if s:
            self.add_step(s["name"], s["start"], self._now_ms() - s["start"])

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs) -> None:
        self._llm_calls += 1
        self._start(run_id, f"llm_call_{self._llm_calls}")

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs) -> None:
        self._llm_calls += 1
        self._start(run_id, f"llm_call_{self._llm_calls}")

    def on_llm_end(self, response, *, run_id, **kwargs) -> None:
        self._end(run_id)

    def on_llm_error(self, error, *, run_id, **kwargs) -> None:
        self._end(run_id)

    def on_tool_start(self, serialized, input_str, *, run_id, name: Optional[str] = None, **kwargs) -> None:
        self._start(run_id, f"tool:{name or (serialized or {}).get('name', 'tool')}")

    def on_tool_end(self, output, *, run_id, **kwargs) -> None:
        self._end(run_id)

    def on_tool_error(self, error, *, run_id, **kwargs) -> None:
        self._end(run_id)
