try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import os
import re
import time
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from langchain_core.tools import tool
from openai import OpenAI

from app.database import get_db_cursor, sanitize_rows

# ContextVar para capturar todas las llamadas a herramientas durante un request HTTP
# Se guarda un contenedor MUTABLE por turno: LangChain ejecuta tools síncronas en una copia del
# contexto, así que un ``.set()`` dentro de la tool se perdería; mutar el contenedor sí es visible.
current_turn_tool_traces: ContextVar[List[Dict[str, Any]]] = ContextVar(
    "current_turn_tool_traces", default=[]
)
current_turn_actuators: ContextVar[Dict[Any, Dict[str, Any]]] = ContextVar(
    "current_turn_actuators", default={}
)


def reset_turn_telemetry() -> None:
    current_turn_tool_traces.set([])
    current_turn_actuators.set({})


def record_tool_trace(
    tool_name: str,
    arguments: Dict[str, Any],
    sql_executed: str,
    raw_output: Any,
    elapsed_ms: float,
) -> None:
    current_turn_tool_traces.get().append(
        {
            "tool_name": tool_name,
            "arguments": arguments,
            "sql_executed": sql_executed.strip(),
            "raw_output": raw_output,
            "execution_time_ms": round(elapsed_ms, 2),
        }
    )


def register_ui_actuators(rows: List[Dict[str, Any]]) -> None:
    store = current_turn_actuators.get()
    for r in rows:
        if "id" in r:
            store[r["id"]] = r


# =====================================================================
# TOOL 1: BÚSQUEDA EXACTA Y DIFUSA POR BASE PART NUMBER
# =====================================================================
class LookupPartNumberInput(BaseModel):
    part_number: str = Field(
        ...,
        description="Base Part Number of the Series 76 actuator (e.g., '761A00-11300000/A', '763B00-11320000/A', or partial/typo code).",
    )


@tool("lookup_actuator_by_part_number", args_schema=LookupPartNumberInput)
def lookup_actuator_by_part_number(part_number: str) -> Dict[str, Any]:
    """
    Looks up technical specifications for a specific Series 76 actuator by its Base Part Number.
    Handles exact matches, missing '/A' suffixes, N/A models in 220V 3-Phase, and OCR/user typos via fuzzy matching.
    """
    t0 = time.perf_counter()
    clean_input = part_number.strip().upper()
    norm_input = re.sub(r"[^A-Z0-9]", "", clean_input)
    # Si el usuario omitió el '/A' al final, también probamos agregando 'A' al normalizado
    norm_with_a = norm_input if norm_input.endswith("A") else norm_input + "A"

    # Solo se busca por tamaño si el input es un código de tamaño puro (ej. "761A")
    size_param = clean_input if re.fullmatch(r"76[1-7][A-Z]", clean_input) else None

    sql_exact = """
        SELECT * FROM actuators
        WHERE UPPER(base_part_number) = %s
           OR normalized_part_number IN (%s, %s)
           OR size_code = %s
        ORDER BY is_available DESC, voltage_num ASC;
    """
    with get_db_cursor() as cur:
        cur.execute(sql_exact, (clean_input, norm_input, norm_with_a, size_param))
        exact_rows = sanitize_rows(cur.fetchall())

        # Caso 1: Encontramos coincidencia exacta
        if exact_rows:
            available_rows = [r for r in exact_rows if r["is_available"]]
            na_rows = [r for r in exact_rows if not r["is_available"]]

            # Si el usuario preguntó específicamente por un modelo que es N/A (ej. 761A00-11330000/A en 220V 3-Phase)
            if not available_rows and na_rows:
                target_size = na_rows[0]["size_code"]
                cur.execute(
                    "SELECT * FROM actuators WHERE size_code = %s AND is_available = TRUE ORDER BY voltage_num ASC;",
                    (target_size,),
                )
                alternatives = sanitize_rows(cur.fetchall())
                register_ui_actuators(alternatives)
                result = {
                    "status": "MODEL_LISTED_AS_NA",
                    "queried_part_number": part_number,
                    "na_records": na_rows,
                    "message": (
                        f"Part number {na_rows[0]['base_part_number']} is listed in the {na_rows[0]['power_supply']} "
                        f"catalog table as N/A (Not Available). Sizes 1 and 2 (761A, 761B, 762A, 762B) are not available "
                        f"in 220V 3-Phase. Returning available single-phase alternatives of size {target_size}."
                    ),
                    "available_alternatives_same_size": alternatives,
                }
                record_tool_trace(
                    "lookup_actuator_by_part_number",
                    {"part_number": part_number},
                    sql_exact,
                    result,
                    (time.perf_counter() - t0) * 1000,
                )
                return result

            register_ui_actuators(available_rows)
            result = {
                "status": "EXACT_MATCH",
                "count": len(exact_rows),
                "actuators": exact_rows,
            }
            record_tool_trace(
                "lookup_actuator_by_part_number",
                {"part_number": part_number},
                sql_exact,
                result,
                (time.perf_counter() - t0) * 1000,
            )
            return result

        # Caso 2: No hubo coincidencia exacta -> Búsqueda difusa con pg_trgm
        sql_fuzzy = """
            SELECT *, similarity(base_part_number, %s) AS sim_score
            FROM actuators
            WHERE similarity(base_part_number, %s) > 0.42
            ORDER BY sim_score DESC, is_available DESC
            LIMIT 4;
        """
        cur.execute(sql_fuzzy, (clean_input, clean_input))
        fuzzy_rows = sanitize_rows(cur.fetchall())

    if fuzzy_rows:
        register_ui_actuators([r for r in fuzzy_rows if r["is_available"]])
        result = {
            "status": "TYPO_OR_CLOSEST_MATCH_FOUND",
            "queried_part_number": part_number,
            "message": (
                f"Exact part number '{part_number}' does not exist in the Series 76 tables. "
                f"However, close matches were found (likely a typo such as 8 vs B or 0 vs C)."
            ),
            "suggested_actuators": fuzzy_rows,
        }
        record_tool_trace(
            "lookup_actuator_by_part_number",
            {"part_number": part_number},
            sql_fuzzy,
            result,
            (time.perf_counter() - t0) * 1000,
        )
        return result

    result = {
        "status": "INVALID_PART_NUMBER",
        "queried_part_number": part_number,
        "message": (
            f"No Series 76 actuator matches '{part_number}'. Valid Series 76 part numbers follow patterns "
            f"like 76[1-7][A,B,C,X,Y][00 or 30]-113[0,2,3,7,8]0000/A."
        ),
    }
    record_tool_trace(
        "lookup_actuator_by_part_number",
        {"part_number": part_number},
        sql_fuzzy,
        result,
        (time.perf_counter() - t0) * 1000,
    )
    return result


# =====================================================================
# TOOL 2: MOTOR DE RECOMENDACIÓN CON RELAJACIÓN DE RESTRICCIONES
# =====================================================================
class RecommendActuatorsInput(BaseModel):
    min_torque_nm: Optional[float] = Field(None, description="Minimum required output torque in Nm.")
    min_torque_in_lbs: Optional[float] = Field(None, description="Minimum required output torque in in-lbs.")
    application_type: Optional[str] = Field(
        None,
        description="Service application type: 'On/Off', 'Modulating', or None if not specified by the user.",
    )
    enclosure_type: Optional[str] = Field(
        None,
        description="Enclosure type: 'Weatherproof' or 'Explosionproof'.",
    )
    voltage_num: Optional[int] = Field(
        None,
        description="Supply voltage: 24, 110, or 220.",
    )
    phase_type: Optional[str] = Field(
        None,
        description="Phase or current type: 'Single Phase', '3 Phase', 'AC/DC', or 'DC'.",
    )
    frequency_hz: Optional[int] = Field(
        None,
        description="Operating power frequency: 50 or 60 (Hz) when checking speed or current.",
    )
    max_speed_sec: Optional[float] = Field(
        None,
        description="Maximum acceptable operating time in seconds for a 90-degree turn.",
    )
    max_fla_amps: Optional[float] = Field(
        None,
        description="Maximum acceptable Full Load Current (FLA) in Amps.",
    )
    min_duty_cycle_pct: Optional[int] = Field(
        None,
        description="Minimum required duty cycle (S4%) percentage.",
    )
    require_csa_certification: Optional[bool] = Field(
        None,
        description="Set to True if the user explicitly requires CSA certification.",
    )


@tool("recommend_actuators", args_schema=RecommendActuatorsInput)
def recommend_actuators(
    min_torque_nm: Optional[float] = None,
    min_torque_in_lbs: Optional[float] = None,
    application_type: Optional[str] = None,
    enclosure_type: Optional[str] = None,
    voltage_num: Optional[int] = None,
    phase_type: Optional[str] = None,
    frequency_hz: Optional[int] = None,
    max_speed_sec: Optional[float] = None,
    max_fla_amps: Optional[float] = None,
    min_duty_cycle_pct: Optional[int] = None,
    require_csa_certification: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Recommends suitable Series 76 actuators based on technical engineering requirements.
    If no model meets all requirements simultaneously, automatically runs constraint relaxation
    to explain why and suggest the closest viable alternatives.
    """
    t0 = time.perf_counter()
    args_dict = {
        k: v
        for k, v in locals().items()
        if k != "t0" and v is not None
    }

    conditions = ["is_available = TRUE"]
    params: List[Any] = []
    ambiguity_notes: List[str] = []

    app_mode = (application_type or "").strip().lower()
    if app_mode in ("on/off", "on_off", "onoff"):
        if min_torque_nm is not None:
            conditions.append("on_off_torque_nm >= %s")
            params.append(min_torque_nm)
        if min_torque_in_lbs is not None:
            conditions.append("on_off_torque_in_lbs >= %s")
            params.append(min_torque_in_lbs)
        if min_duty_cycle_pct is not None:
            conditions.append("on_off_duty_cycle_pct >= %s")
            params.append(min_duty_cycle_pct)
        conditions.append("on_off_torque_nm IS NOT NULL")
    elif app_mode == "modulating":
        if min_torque_nm is not None:
            conditions.append("modulating_torque_nm >= %s")
            params.append(min_torque_nm)
        if min_torque_in_lbs is not None:
            conditions.append("modulating_torque_in_lbs >= %s")
            params.append(min_torque_in_lbs)
        if min_duty_cycle_pct is not None:
            conditions.append("modulating_duty_cycle_pct >= %s")
            params.append(min_duty_cycle_pct)
        conditions.append("modulating_torque_nm IS NOT NULL")
    else:
        # Si el usuario no especificó On/Off vs Modulating, filtramos si cumple en CUALQUIERA de los dos
        if min_torque_nm is not None or min_torque_in_lbs is not None:
            ambiguity_notes.append(
                "Application service type (On/Off vs Modulating) was not specified. "
                "Note that Modulating torque ratings are typically lower than On/Off torque ratings for the same actuator."
            )
        if min_torque_nm is not None:
            conditions.append("(COALESCE(on_off_torque_nm, 0) >= %s OR COALESCE(modulating_torque_nm, 0) >= %s)")
            params.extend([min_torque_nm, min_torque_nm])
        if min_torque_in_lbs is not None:
            conditions.append("(COALESCE(on_off_torque_in_lbs, 0) >= %s OR COALESCE(modulating_torque_in_lbs, 0) >= %s)")
            params.extend([min_torque_in_lbs, min_torque_in_lbs])
        if min_duty_cycle_pct is not None:
            conditions.append("(COALESCE(on_off_duty_cycle_pct, 0) >= %s OR COALESCE(modulating_duty_cycle_pct, 0) >= %s)")
            params.extend([min_duty_cycle_pct, min_duty_cycle_pct])

    if enclosure_type:
        conditions.append("LOWER(enclosure_type) = LOWER(%s)")
        params.append(enclosure_type.strip())

    if voltage_num is not None:
        conditions.append("voltage_num = %s")
        params.append(voltage_num)

    if phase_type:
        p_clean = phase_type.strip().lower()
        if "3" in p_clean or "three" in p_clean:
            conditions.append("phase_type = '3 Phase'")
        elif "single" in p_clean or "1" in p_clean:
            conditions.append("phase_type = 'Single Phase'")
        elif p_clean == "dc":
            conditions.append("phase_type IN ('DC', 'AC/DC')")
        else:
            conditions.append("LOWER(phase_type) = LOWER(%s)")
            params.append(phase_type.strip())

    if max_speed_sec is not None:
        if frequency_hz == 50:
            conditions.append("COALESCE(speed_50hz_sec, speed_dc_or_fixed_sec) <= %s")
            params.append(max_speed_sec)
        elif frequency_hz == 60:
            conditions.append("COALESCE(speed_60hz_sec, speed_dc_or_fixed_sec) <= %s")
            params.append(max_speed_sec)
        else:
            conditions.append(
                "(COALESCE(speed_60hz_sec, 9999) <= %s OR COALESCE(speed_50hz_sec, 9999) <= %s OR COALESCE(speed_dc_or_fixed_sec, 9999) <= %s)"
            )
            params.extend([max_speed_sec, max_speed_sec, max_speed_sec])

    if max_fla_amps is not None:
        if frequency_hz == 50:
            conditions.append("COALESCE(fla_50hz_amps, fla_dc_or_fixed_amps) <= %s")
            params.append(max_fla_amps)
        elif frequency_hz == 60:
            conditions.append("COALESCE(fla_60hz_amps, fla_dc_or_fixed_amps) <= %s")
            params.append(max_fla_amps)
        else:
            conditions.append(
                "(COALESCE(fla_60hz_amps, 9999) <= %s OR COALESCE(fla_50hz_amps, 9999) <= %s OR COALESCE(fla_dc_or_fixed_amps, 9999) <= %s)"
            )
            params.extend([max_fla_amps, max_fla_amps, max_fla_amps])

    if require_csa_certification is True:
        conditions.append("csa_certified = TRUE")

    where_clause = " AND ".join(conditions)
    order_col = (
        "modulating_torque_nm"
        if app_mode == "modulating"
        else "COALESCE(on_off_torque_nm, modulating_torque_nm)"
    )
    sql_query = f"""
        SELECT * FROM actuators
        WHERE {where_clause}
        ORDER BY {order_col} ASC, voltage_num ASC
        LIMIT 6;
    """

    with get_db_cursor() as cur:
        cur.execute(sql_query, tuple(params))
        matches = sanitize_rows(cur.fetchall())

        if matches:
            register_ui_actuators(matches)
            result = {
                "status": "MATCHES_FOUND",
                "count": len(matches),
                "ambiguity_warnings": ambiguity_notes,
                "recommended_actuators": matches,
            }
            record_tool_trace(
                "recommend_actuators",
                args_dict,
                sql_query,
                result,
                (time.perf_counter() - t0) * 1000,
            )
            return result

        # =================================================================
        # MOTOR DE RELAJACIÓN DE RESTRICCIONES (CUANDO 0 MODELOS CUMPLEN)
        # =================================================================
        relaxation_diagnostics: List[str] = []
        relaxed_candidates: List[Dict[str, Any]] = []

        # Diagnóstico 1: ¿Pidió más torque del que existe en ese voltaje o enclosure?
        cur.execute(
            """
            SELECT enclosure_type, power_supply,
                   MAX(on_off_torque_nm) AS max_onoff_nm,
                   MAX(modulating_torque_nm) AS max_mod_nm,
                   MAX(CASE WHEN csa_certified THEN on_off_torque_nm ELSE 0 END) AS max_csa_nm
            FROM actuators
            WHERE is_available = TRUE
            GROUP BY enclosure_type, power_supply
            ORDER BY max_onoff_nm DESC;
            """
        )
        limits_summary = sanitize_rows(cur.fetchall())

        if require_csa_certification and (min_torque_nm and min_torque_nm > 3000):
            relaxation_diagnostics.append(
                "Maximum CSA-certified torque in Series 76 is 3,000 Nm (5,000+ Nm models are Sizes 6 and 7, "
                "which are only available in 220V Single Phase Weatherproof and are NOT CSA Certified per table notes)."
            )

        if voltage_num == 24 and (min_torque_nm and min_torque_nm > 240):
            relaxation_diagnostics.append(
                "In 24V power supply, Series 76 only offers Explosionproof models up to 240 Nm (On/Off) and 220 Nm (Modulating)."
            )

        if enclosure_type and enclosure_type.lower() == "explosionproof" and (min_torque_nm and min_torque_nm > 3000):
            relaxation_diagnostics.append(
                "Explosionproof models have a maximum torque of 3,000 Nm On/Off (2,400 Nm Modulating). "
                "Torques between 3,500 Nm and 9,000 Nm are only available in Weatherproof 220V Single Phase."
            )

        # Buscar los 3 modelos más cercanos en torque general sin restringir voltaje/CSA
        target_nm = min_torque_nm or ((min_torque_in_lbs / 8.85) if min_torque_in_lbs else 500)
        cur.execute(
            """
            SELECT * FROM actuators
            WHERE is_available = TRUE
            ORDER BY ABS(COALESCE(on_off_torque_nm, modulating_torque_nm) - %s) ASC
            LIMIT 4;
            """,
            (target_nm,),
        )
        relaxed_candidates = sanitize_rows(cur.fetchall())

    register_ui_actuators(relaxed_candidates)
    result = {
        "status": "NO_EXACT_MATCH_CONSTRAINT_RELAXATION",
        "count": 0,
        "message": "No single Series 76 actuator satisfies all requested constraints simultaneously.",
        "diagnostics": relaxation_diagnostics,
        "catalog_capability_limits": limits_summary,
        "closest_alternative_actuators": relaxed_candidates,
    }
    record_tool_trace(
        "recommend_actuators",
        args_dict,
        sql_query,
        result,
        (time.perf_counter() - t0) * 1000,
    )
    return result


# =====================================================================
# TOOL 3: BÚSQUEDA SEMÁNTICA EN DOCUMENTACIÓN Y NOTAS (pgvector)
# =====================================================================
class SearchKnowledgeInput(BaseModel):
    query: str = Field(
        ...,
        description="Technical question about Series 76 concepts, voltage/frequency tolerances, certifications (CSA, ATEX, Class I Div 1), or definitions (FLA, LRA, Duty Cycle S4%).",
    )


@tool("search_engineering_knowledge", args_schema=SearchKnowledgeInput)
def search_engineering_knowledge(query: str) -> Dict[str, Any]:
    """
    Searches Series 76 business summary and footnote engineering rules using pgvector semantic similarity.
    Use this for questions about voltage tolerance (+/-10%), frequency tolerance (+/-5%), hazardous area certifications,
    CSA exceptions for Sizes 6 and 7, or definitions of electrical metrics.
    """
    t0 = time.perf_counter()
    base_url = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    api_key = os.getenv("LLM_API_KEY", "")
    embed_model = os.getenv("EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b")

    sql_used = ""
    rows: List[Dict[str, Any]] = []
    retrieval_mode = "vector_similarity"

    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        extra_body = {"input_type": "query"} if "nvidia" in embed_model.lower() else {}
        emb_resp = client.embeddings.create(
            model=embed_model,
            input=[query],
            extra_body=extra_body if extra_body else None,
        )
        vec_str = "[" + ",".join(f"{x:.6f}" for x in emb_resp.data[0].embedding) + "]"

        sql_used = """
            SELECT chunk_key, source_document, category, title, content,
                   1 - (embedding <=> %s::vector) AS cosine_similarity
            FROM knowledge_chunks
            ORDER BY embedding <=> %s::vector ASC
            LIMIT 3;
        """
        with get_db_cursor() as cur:
            cur.execute(sql_used, (vec_str, vec_str))
            rows = sanitize_rows(cur.fetchall())
    except Exception:
        # Fallback determinista si la API de embeddings da timeout o rate limit
        retrieval_mode = "sql_fallback"
        sql_used = "SELECT chunk_key, source_document, category, title, content FROM knowledge_chunks;"
        with get_db_cursor() as cur:
            cur.execute(sql_used)
            rows = sanitize_rows(cur.fetchall())

    result = {
        "status": "KNOWLEDGE_RETRIEVED",
        "retrieval_mode": retrieval_mode,
        "chunks": rows,
    }
    record_tool_trace(
        "search_engineering_knowledge",
        {"query": query},
        sql_used,
        result,
        (time.perf_counter() - t0) * 1000,
    )
    return result


ALL_SERIES76_TOOLS = [
    lookup_actuator_by_part_number,
    recommend_actuators,
    search_engineering_knowledge,
]