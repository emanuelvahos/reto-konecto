"""Configuracion de proveedor LLM por entorno (sin modelos ni URLs escritos en el codigo).

LLM_PROVIDER=openrouter|nim selecciona un perfil de config/llm_profiles.json.
  openrouter: LLM_BASE_URL, LLM_CHAT_MODEL, LLM_API_KEY      (compatibles con las variables previas)
  nim:        LLM_BASE_URL_NIM, LLM_CHAT_MODEL_NIM, LLM_API_KEY_NIM
Si LLM_PROVIDER no esta definido se usa el perfil por defecto del JSON (openrouter).
"""
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from pathlib import Path

PROFILES_PATH = Path(__file__).resolve().parent.parent / "config" / "llm_profiles.json"


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    base_url: str
    chat_model: str
    api_key: str = ""
    extra_body: Optional[Dict[str, Any]] = None
    pricing: Optional[Dict[str, Dict[str, float]]] = None

    def __repr__(self) -> str:  # nunca exponer la clave en logs
        return f"LLMConfig(provider={self.provider!r}, base_url={self.base_url!r}, chat_model={self.chat_model!r}, api_key={'***' if self.api_key else ''})"


def load_llm_config() -> LLMConfig:
    spec = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    profiles = spec["profiles"]
    provider = (os.getenv("LLM_PROVIDER") or spec["default_provider"]).strip().lower()
    if provider not in profiles:
        raise ValueError(f"LLM_PROVIDER={provider!r} invalido; opciones: {sorted(profiles)}")
    p = profiles[provider]
    return LLMConfig(
        provider=provider,
        base_url=(os.getenv(p["base_url_env"]) or p["base_url"]).rstrip("/"),
        chat_model=os.getenv(p["chat_model_env"]) or p["chat_model"],
        api_key=os.getenv(p["api_key_env"], ""),
        extra_body=p.get("extra_body"),
        pricing=p.get("pricing_per_1m_usd") or {},
    )


def estimate_cost_usd(cfg: LLMConfig, prompt_tokens: int, completion_tokens: int) -> float:
    """Costo estimado con precios de lista del perfil (NIM = 0). Modelo sin precio listado = 0."""
    price = (cfg.pricing or {}).get(cfg.chat_model)
    if not price:
        return 0.0
    return round((prompt_tokens * price["input"] + completion_tokens * price["output"]) / 1_000_000, 8)
