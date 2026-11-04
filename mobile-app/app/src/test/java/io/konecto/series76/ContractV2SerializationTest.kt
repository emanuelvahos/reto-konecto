package io.konecto.series76

import io.konecto.series76.data.ApiClient
import io.konecto.series76.data.ConversationResponse
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
}
