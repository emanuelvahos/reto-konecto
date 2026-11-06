"""Benchmark de LLMs y embeddings del catálogo NVIDIA NIM para el asistente Series 76.

Uso (desde la raíz):  python backend/evals/benchmark_nvidia.py [--chat] [--embed]
Lee el perfil nim (LLM_API_KEY_NIM / LLM_BASE_URL_NIM) de .env. Escribe backend/evals/benchmark_results.json
"""
import argparse
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
os.environ["LLM_PROVIDER"] = "nim"
sys.path.insert(0, str(ROOT / "backend"))
from app.config import load_llm_config  # noqa: E402

_CFG = load_llm_config()
BASE = _CFG.base_url
KEY = _CFG.api_key
HEAD = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

CHAT_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-nano-3-30b-a3b",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "openai/gpt-oss-20b",
    "deepseek-ai/deepseek-v4.1-flash",
    "minimaxai/minimax-m3.1-flash",
    "z-ai/glm-5.3-flash",
    "moonshotai/kimi-k2.6",
    "google/gemma-4-31b-it",
    "mistralai/mistral-large-2-instruct",
]
EMBED_MODELS = [
    "nvidia/nemotron-3.5-embed-1b",
    "nvidia/nemotron-3-embed-1b",
    "nvidia/llama-3.2-nv-embedqa-1b-v1",
    "nvidia/nv-embedqa-mistral-7b-v2",
    "nvidia/embed-qa-4",
    "snowflake/arctic-embed-l",
]

TOOLS = [{
    "type": "function",
    "function": {
        "name": "search_actuators",
        "description": "Search the Series 76 actuator catalog (SQL). Use for any numeric/spec/certification question.",
        "parameters": {
            "type": "object",
            "properties": {
                "part_number": {"type": "string"},
                "enclosure_type": {"type": "string", "enum": ["Weatherproof", "Explosionproof"]},
                "power_supply": {"type": "string", "enum": ["110V Single Phase", "220V Single Phase", "220V 3 Phase", "24V AC/DC", "24V DC"]},
                "min_torque_nm": {"type": "number"},
            },
        },
    },
}]
SYSTEM = ("You are a Series 76 electric actuator assistant. Use tools for catalog data. "
          "Never invent data; if information is not available (e.g. prices) say so briefly.")


def check_tool(args_pred):
    def f(msg):
        for tc in msg.get("tool_calls") or []:
            if tc["function"]["name"] != "search_actuators":
                continue
            try:
                a = json.loads(tc["function"]["arguments"] or "{}")
            except Exception:
                return False
            if args_pred(a):
                return True
        return False
    return f


def text(msg):
    return (msg.get("content") or "")


CASES = [
    ("tool_filters", "I need a weatherproof actuator, 220V single phase, with at least 1000 Nm on/off torque.", True,
     check_tool(lambda a: a.get("enclosure_type") == "Weatherproof" and a.get("power_supply") == "220V Single Phase"
                and float(a.get("min_torque_nm", 0) or 0) == 1000)),
    ("tool_part", "Is the 766A00-11320000/A CSA certified?", True,
     check_tool(lambda a: "766A" in str(a.get("part_number", "")).upper())),
    ("tool_hazard", "What explosionproof models run on 24V DC?", True,
     check_tool(lambda a: a.get("enclosure_type") == "Explosionproof" and a.get("power_supply") in (None, "24V DC"))),
    ("math_tolerance", "Context: allowable motor voltage tolerance is +/-10%. What is the minimum allowed supply voltage for a 110V model? Answer with the number.", False,
     lambda m: "99" in text(m)),
    ("math_convert", "Convert 3000 Nm to in-lbs (1 Nm = 8.8507 in-lbs). Answer with the number only.", False,
     lambda m: re.search(r"26[,.\s]?5[45]\d", text(m)) is not None),
    ("no_hallucination", "What is the price in USD of the 761A00-11300000/A actuator?", True,
     lambda m: re.search(r"\$\s?\d", text(m)) is None and not (m.get("tool_calls") and not text(m))),
]


def run_chat(model):
    res = {"model": model, "cases": {}, "latency": []}
    for name, prompt, use_tools, check in CASES:
        body = {"model": model, "temperature": 0, "max_tokens": 1024,
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
        if use_tools:
            body["tools"] = TOOLS
        t0 = time.time()
        try:
            r = httpx.post(f"{BASE}/chat/completions", headers=HEAD, json=body, timeout=45)
            dt = time.time() - t0
            if r.status_code != 200:
                res["cases"][name] = f"HTTP {r.status_code}"
                continue
            msg = r.json()["choices"][0]["message"]
            ok = bool(check(msg))
            if name == "no_hallucination" and msg.get("tool_calls"):
                ok = True  # consultar el catálogo antes de responder es válido
            res["cases"][name] = ok
            res["latency"].append(dt)
        except Exception as e:  # noqa: BLE001
            res["cases"][name] = f"ERR {type(e).__name__}"
    ok = sum(1 for v in res["cases"].values() if v is True)
    res["score"] = f"{ok}/{len(CASES)}"
    res["avg_latency_s"] = round(sum(res["latency"]) / len(res["latency"]), 2) if res["latency"] else None
    return res


DOCS = [
    "Sizes 6 and 7 (models 766A00, 766B00, 767A00, 767B00, 767C00) are NOT CSA Certified.",
    "Allowable motor voltage tolerance is +/- 10% and power frequency tolerance +/- 5%.",
    "Explosionproof enclosures are certified Class I Division 1 Groups C, D, T4 for hazardous areas with flammable gases.",
    "Locked Rotor Current (LRA) is the current drawn at startup, higher than Full Load Current (FLA).",
    "Modulating actuators stop at any point of the 90-degree rotation and specify Starts per Hour.",
    "Duty cycle S4 percentage is the share of time the actuator can operate per IEC 60034-1 without overheating.",
]
QUERIES = [
    ("which actuators lack CSA certification?", 0),
    ("what voltage range can the motor tolerate?", 1),
    ("can I use it in an area with explosive gas?", 2),
    ("startup current versus rated current", 3),
    ("positioning valve partially open", 4),
    ("how much operating time per hour before overheating", 5),
]


def cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def embed(model, inputs, kind):
    body = {"model": model, "input": inputs, "encoding_format": "float", "input_type": kind}
    r = httpx.post(f"{BASE}/embeddings", headers=HEAD, json=body, timeout=60)
    if r.status_code != 200:
        body.pop("input_type")
        r = httpx.post(f"{BASE}/embeddings", headers=HEAD, json=body, timeout=60)
    r.raise_for_status()
    return [d["embedding"] for d in r.json()["data"]]


def run_embed(model):
    res = {"model": model}
    try:
        t0 = time.time()
        d = embed(model, DOCS, "passage")
        q = embed(model, [x[0] for x in QUERIES], "query")
        res["latency_s"] = round(time.time() - t0, 2)
        res["dims"] = len(d[0])
        hits = 0
        for qi, (_, gold) in enumerate(QUERIES):
            scores = [cos(q[qi], x) for x in d]
            hits += int(scores.index(max(scores)) == gold)
        res["top1"] = f"{hits}/{len(QUERIES)}"
    except Exception as e:  # noqa: BLE001
        res["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", action="store_true")
    ap.add_argument("--embed", action="store_true")
    a = ap.parse_args()
    both = not (a.chat or a.embed)
    out = {}
    if a.chat or both:
        with ThreadPoolExecutor(12) as ex:
            out["chat"] = []
            for r in ex.map(run_chat, CHAT_MODELS):
                out["chat"].append(r)
                print(r["model"], r["score"], r["avg_latency_s"], r["cases"], flush=True)
    if a.embed or both:
        out["embed"] = [run_embed(m) for m in EMBED_MODELS]
        for r in out["embed"]:
            print(r)
    (Path(__file__).parent / "benchmark_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

