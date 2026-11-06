package io.konecto.series76

import io.konecto.series76.data.ApiClient
import io.konecto.series76.data.ClarificationOption
import io.konecto.series76.data.ClarificationPayload
import io.konecto.series76.data.ConversationResponse
import io.konecto.series76.data.SuggestedFollowup
import io.konecto.series76.data.UIPayload
import io.konecto.series76.ui.buildEffectiveActionChips
import org.junit.Assert.*
import org.junit.Test

class ContractV2SerializationTest {

    @Test
    fun testDeserializeSingleSpecCardSample() {
        val json = """
        {
          "schema_version": 2,
          "intent": "lookup",
          "verification": {"status": "verified", "numbers_checked": 3, "ungrounded": []},
          "session_id": "00000000-0000-4000-8000-000000000001",
          "answer": "Ficha del modelo solicitado.",
          "ui_payload": {
            "display_type": "SINGLE_SPEC_CARD",
            "actuators": [{"base_part_number": "EXAMPLE-PN-1", "frame_size": 1}],
            "engineering_warnings": [],
            "alerts": [],
            "recommendation": null,
            "clarification": null
          },
          "debug_trace": {
            "model_used": "example-model",
            "total_latency_ms": 1200.5,
            "token_usage": {},
            "active_context_part_numbers": ["EXAMPLE-PN-1"],
            "tool_calls": [],
            "steps": [{"name": "tool:lookup", "start_ms": 10.0, "duration_ms": 25.5}],
            "cost_usd_estimate": 0.0,
            "provider": "example"
          }
        }
        """.trimIndent()

        val resp = ApiClient.jsonFormat.decodeFromString(ConversationResponse.serializer(), json)
        assertEquals(2, resp.schemaVersion)
        assertEquals("lookup", resp.intent)
        assertEquals("verified", resp.verification.status)
        assertEquals("SINGLE_SPEC_CARD", resp.uiPayload.displayType)
        assertEquals(1, resp.uiPayload.actuators.size)
        assertEquals("EXAMPLE-PN-1", resp.uiPayload.actuators.first().basePartNumber)
        assertEquals(1, resp.debugTrace.steps.size)
        assertEquals(10.0, resp.debugTrace.steps.first().startMs, 0.001)
    }

    @Test
    fun testDeserializeComparisonTableSample() {
        val json = """
        {
          "schema_version": 2,
          "intent": "lookup",
          "verification": {"status": "verified", "numbers_checked": 6, "ungrounded": []},
          "session_id": "00000000-0000-4000-8000-000000000002",
          "answer": "Comparativa entre dos actuadores.",
          "ui_payload": {
            "display_type": "COMPARISON_TABLE",
            "actuators": [
              {"base_part_number": "763B00-11300000/A", "frame_size": 3, "on_off_torque_nm": 500.0},
              {"base_part_number": "763C00-11300000/A", "frame_size": 3, "on_off_torque_nm": 650.0}
            ],
            "alerts": [
              {"code": "SINGLE_TORQUE_RATING", "severity": "info", "message": "Info alert"}
            ],
            "suggested_followups": [
              {"label": "Ver valores a 50 Hz", "query": "50 Hz"}
            ]
          },
          "debug_trace": {
            "model_used": "claude-3-7-sonnet",
            "total_latency_ms": 1100.0,
            "provider": "anthropic"
          }
        }
        """.trimIndent()

        val resp = ApiClient.jsonFormat.decodeFromString(ConversationResponse.serializer(), json)
        assertEquals("COMPARISON_TABLE", resp.uiPayload.displayType)
        assertEquals(2, resp.uiPayload.actuators.size)
        assertEquals(1, resp.uiPayload.alerts.size)
        assertEquals("SINGLE_TORQUE_RATING", resp.uiPayload.alerts.first().code)
        assertEquals(1, resp.uiPayload.suggestedFollowups.size)
        assertEquals("Ver valores a 50 Hz", resp.uiPayload.suggestedFollowups.first().label)
    }

    @Test
    fun testDeserializeRecommendationSample() {
        val json = """
        {
          "schema_version": 2,
          "intent": "recommend",
          "verification": {"status": "fallback_template", "numbers_checked": 5, "ungrounded": ["token"]},
          "session_id": "00000000-0000-4000-8000-000000000003",
          "answer": "Recomendación basada en torque.",
          "ui_payload": {
            "display_type": "RECOMMENDATION_LIST",
            "recommendation": {
              "ranking": [
                {
                  "part_number": "EXAMPLE-PN-3",
                  "score": 0.94,
                  "why": ["Torque on/off 6000 Nm"],
                  "why_not": ["Mayor peso"]
                }
              ],
              "hard_constraints": ["Torque mínimo 5000 Nm", "24V DC"],
              "relaxed_constraints": ["Velocidad de giro"]
            },
            "suggested_followups": [
              {"label": "Ver ficha", "query": "Specs"}
            ]
          },
          "debug_trace": {
            "model_used": "claude-3-7-sonnet",
            "total_latency_ms": 1400.0,
            "session_cost_usd": 0.0054,
            "language": "es"
          }
        }
        """.trimIndent()

        val resp = ApiClient.jsonFormat.decodeFromString(ConversationResponse.serializer(), json)
        assertEquals("RECOMMENDATION_LIST", resp.uiPayload.displayType)
        assertEquals("fallback_template", resp.verification.status)
        assertNotNull(resp.uiPayload.recommendation)
        val rec = resp.uiPayload.recommendation!!
        assertEquals(1, rec.ranking.size)
        assertEquals("EXAMPLE-PN-3", rec.ranking.first().partNumber)
        assertEquals(0.94, rec.ranking.first().score, 0.001)
        assertEquals("Torque on/off 6000 Nm", rec.ranking.first().why.first())
        assertEquals("Mayor peso", rec.ranking.first().whyNot.first())
        assertEquals(2, rec.hardConstraints.size)
        assertEquals(1, rec.relaxedConstraints.size)
        assertEquals(0.0054, resp.debugTrace.sessionCostUsd, 0.0001)
        assertEquals("es", resp.debugTrace.language)
    }

    @Test
    fun testDeserializeClarificationSample() {
        val json = """
        {
          "schema_version": 2,
          "intent": "clarify",
          "verification": {"status": "unverified", "numbers_checked": 0, "ungrounded": []},
          "session_id": "00000000-0000-4000-8000-000000000004",
          "answer": "¿Qué voltaje necesita?",
          "ui_payload": {
            "display_type": "CLARIFICATION",
            "clarification": {
              "question": "¿Qué voltaje necesita?",
              "options": [
                {"label": "110V Monofásico", "value": "110V"},
                {"label": "220V Trifásico", "value": "220V"}
              ]
            }
          },
          "debug_trace": {
            "model_used": "claude-3-7-sonnet",
            "total_latency_ms": 300.0
          }
        }
        """.trimIndent()

        val resp = ApiClient.jsonFormat.decodeFromString(ConversationResponse.serializer(), json)
        assertEquals("CLARIFICATION", resp.uiPayload.displayType)
        assertNotNull(resp.uiPayload.clarification)
        val clar = resp.uiPayload.clarification!!
        assertEquals("¿Qué voltaje necesita?", clar.question)
        assertEquals(2, clar.options.size)
        assertEquals("110V Monofásico", clar.options[0].label)
        assertEquals("110V", clar.options[0].value)
    }

    @Test
    fun testDeserializeWithUnknownKeys() {
        val json = """
        {
          "schema_version": 2,
          "intent": "lookup",
          "session_id": "sid-test",
          "answer": "ok",
          "unknown_future_field": "some_value",
          "ui_payload": {
            "display_type": "TEXT_ONLY",
            "unknown_nested_obj": {"a": 123}
          }
        }
        """.trimIndent()

        val resp = ApiClient.jsonFormat.decodeFromString(ConversationResponse.serializer(), json)
        assertEquals("sid-test", resp.sessionId)
        assertEquals("TEXT_ONLY", resp.uiPayload.displayType)
    }

    @Test
    fun testDeserializeAll19SamplesFromAssets() {
        val possiblePaths = listOf(
            java.io.File("src/debug/assets/contract_v2_samples.json"),
            java.io.File("app/src/debug/assets/contract_v2_samples.json"),
            java.io.File("mobile-app/app/src/debug/assets/contract_v2_samples.json")
        )
        val file = possiblePaths.firstOrNull { it.exists() }
        assertNotNull("contract_v2_samples.json file must exist", file)

        val jsonString = file!!.readText()
        val rootObj = ApiClient.jsonFormat.parseToJsonElement(jsonString) as kotlinx.serialization.json.JsonObject

        val expectedKeys = listOf(
            "single_spec_card",
            "comparison_table",
            "comparison_table_3",
            "recommendation_with_relaxation",
            "recommendation_no_match",
            "clarification",
            "three_phase_single_torque",
            "model_listed_as_na",
            "typo_correction",
            "out_of_scope",
            "llm_error",
            "degraded_lookup",
            "greeting",
            "capabilities",
            "help_menu",
            "catalog_overview",
            "ranking",
            "attribute_not_included",
            "size_clarification"
        )

        assertEquals("Expected exactly 19 samples", 19, rootObj.size)
        expectedKeys.forEach { key ->
            assertTrue("Sample key '$key' must exist in fixture", rootObj.containsKey(key))
            val element = rootObj[key]!!
            val resp = ApiClient.jsonFormat.decodeFromJsonElement(ConversationResponse.serializer(), element)
            assertNotNull("ConversationResponse for $key should deserialize", resp)
            assertNotNull("Answer must be non-null for $key", resp.answer)
        }

        // Verify single_spec_card real source data
        val singleSpec = ApiClient.jsonFormat.decodeFromJsonElement(
            ConversationResponse.serializer(),
            rootObj["single_spec_card"]!!
        )
        val actuator = singleSpec.uiPayload.actuators.firstOrNull()
        assertNotNull("Actuator in single_spec_card should exist", actuator)
        assertNotNull("source_page should be present in real data", actuator?.sourcePage)
        assertTrue("source_page should be > 0", (actuator?.sourcePage ?: 0) > 0)

        // Verify llm_error clarification guide
        val llmError = ApiClient.jsonFormat.decodeFromJsonElement(
            ConversationResponse.serializer(),
            rootObj["llm_error"]!!
        )
        assertNotNull("llm_error answer should be present", llmError.answer)
        assertEquals("CLARIFICATION", llmError.uiPayload.displayType)
        assertNotNull("llm_error clarification should be populated", llmError.uiPayload.clarification)
        assertTrue("llm_error options should not be empty", llmError.uiPayload.clarification?.options?.isNotEmpty() == true)

        // Verify degraded_lookup sample with informative mode alert
        val degradedLookup = ApiClient.jsonFormat.decodeFromJsonElement(
            ConversationResponse.serializer(),
            rootObj["degraded_lookup"]!!
        )
        assertEquals("fallback_template", degradedLookup.verification.status)
        assertEquals("SINGLE_SPEC_CARD", degradedLookup.uiPayload.displayType)
        assertEquals(1, degradedLookup.uiPayload.actuators.size)
        assertEquals("763B00-11300000/A", degradedLookup.uiPayload.actuators.first().basePartNumber)
        val degradedAlert = degradedLookup.uiPayload.alerts.firstOrNull()
        assertNotNull("degraded_lookup should contain an alert", degradedAlert)
        assertEquals("LLM_UNAVAILABLE", degradedAlert?.code)
        assertEquals("info", degradedAlert?.severity)
        assertEquals("Modo reducido", degradedAlert?.title)
        assertTrue("degraded_lookup alert message should not be blank", degradedAlert?.message?.isNotBlank() == true)

        // Verify greeting, capabilities, attribute_not_included have numbers_checked=0 and empty actuators
        for (k in listOf("greeting", "capabilities", "attribute_not_included")) {
            val sample = ApiClient.jsonFormat.decodeFromJsonElement(
                ConversationResponse.serializer(),
                rootObj[k]!!
            )
            assertEquals("Sample $k must have 0 numbers_checked", 0, sample.verification.numbersChecked)
            assertTrue("Sample $k must have empty actuators", sample.uiPayload.actuators.isEmpty())
        }
    }

    @Test
    fun testBuildEffectiveActionChipsClarificationAndFollowups() {
        // Test 1: CLARIFICATION options are converted to action chips
        val payloadClarification = UIPayload(
            displayType = "CLARIFICATION",
            clarification = ClarificationPayload(
                question = "¿Qué voltaje?",
                options = listOf(
                    ClarificationOption(label = "110 V monofásico", value = "110V monofásico"),
                    ClarificationOption(label = "220 V trifásico", value = "220V trifásico")
                )
            ),
            suggestedFollowups = emptyList()
        )
        val chipsClar = buildEffectiveActionChips(payloadClarification)
        assertEquals(2, chipsClar.size)
        assertEquals("110 V monofásico", chipsClar[0].label)
        assertEquals("110V monofásico", chipsClar[0].query)
        assertEquals("220 V trifásico", chipsClar[1].label)
        assertEquals("220V trifásico", chipsClar[1].query)

        // Test 2: suggested_followups limited to 3
        val payloadFollowups = UIPayload(
            displayType = "TEXT_ONLY",
            suggestedFollowups = listOf(
                SuggestedFollowup(label = "Chip 1", query = "query 1"),
                SuggestedFollowup(label = "Chip 2", query = "query 2"),
                SuggestedFollowup(label = "Chip 3", query = "query 3"),
                SuggestedFollowup(label = "Chip 4", query = "query 4")
            )
        )
        val chipsFol = buildEffectiveActionChips(payloadFollowups)
        assertEquals(3, chipsFol.size)
        assertEquals("Chip 1", chipsFol[0].label)
        assertEquals("Chip 3", chipsFol[2].label)

        // Test 3: Deduplication when both CLARIFICATION and suggested_followups have same query or label
        val payloadBoth = UIPayload(
            displayType = "CLARIFICATION",
            clarification = ClarificationPayload(
                question = "¿Qué voltaje?",
                options = listOf(
                    ClarificationOption(label = "110 V monofásico", value = "110V monofásico"),
                    ClarificationOption(label = "220 V monofásico", value = "220V monofásico")
                )
            ),
            suggestedFollowups = listOf(
                SuggestedFollowup(label = "110 V monofásico", query = "110V monofásico"), // duplicate
                SuggestedFollowup(label = "Ficha del 761A", query = "Ficha del 761A00-11300000/A") // new
            )
        )
        val chipsBoth = buildEffectiveActionChips(payloadBoth)
        assertEquals(3, chipsBoth.size)
        assertEquals("110 V monofásico", chipsBoth[0].label)
        assertEquals("220 V monofásico", chipsBoth[1].label)
        assertEquals("Ficha del 761A", chipsBoth[2].label)
    }
}

