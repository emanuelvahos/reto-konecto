package io.konecto.series76.mock

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import io.konecto.series76.data.ApiClient
import io.konecto.series76.data.ConversationResponse
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject

object DebugMockProvider {
    const val isAvailable: Boolean = true
    var isMockEnabled by mutableStateOf(true)
    var selectedSampleKey by mutableStateOf("single_spec_card")

    val sampleKeys = listOf(
        "single_spec_card",
        "degraded_lookup",
        "comparison_table",
        "comparison_table_3",
        "recommendation_with_relaxation",
        "recommendation_no_match",
        "clarification",
        "three_phase_single_torque",
        "model_listed_as_na",
        "typo_correction",
        "out_of_scope",
        "llm_error"
    )

    private var cachedSamples: Map<String, ConversationResponse>? = null

    fun getAvailableSamples(context: Context): Map<String, ConversationResponse> {
        cachedSamples?.let { return it }
        return try {
            val jsonString = context.assets.open("contract_v2_samples.json").bufferedReader().use { it.readText() }
            val rootObj = ApiClient.jsonFormat.parseToJsonElement(jsonString).jsonObject
            val map = mutableMapOf<String, ConversationResponse>()
            rootObj.forEach { (key, element) ->
                try {
                    val resp = ApiClient.jsonFormat.decodeFromJsonElement(ConversationResponse.serializer(), element)
                    map[key] = resp
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
            cachedSamples = map
            map
        } catch (e: Exception) {
            e.printStackTrace()
            emptyMap()
        }
    }

    fun getMockResponse(context: Context, query: String): ConversationResponse? {
        if (!isMockEnabled) return null
        val samples = getAvailableSamples(context)
        val match = when {
            query.contains("degraded", ignoreCase = true) || query.contains("degradad", ignoreCase = true) -> "degraded_lookup"
            query.contains("error", ignoreCase = true) || query.contains("llm", ignoreCase = true) -> "llm_error"
            query.contains("no match", ignoreCase = true) || query.contains("12000", ignoreCase = true) -> "recommendation_no_match"
            query.contains("three", ignoreCase = true) || query.contains("trifas", ignoreCase = true) || query.contains("trifás", ignoreCase = true) -> "three_phase_single_torque"
            query.contains("compare 3", ignoreCase = true) || query.contains("tres", ignoreCase = true) -> "comparison_table_3"
            query.contains("compare", ignoreCase = true) || query.contains("compara", ignoreCase = true) -> "comparison_table"
            query.contains("200 Nm", ignoreCase = true) || query.contains("recomiend", ignoreCase = true) || query.contains("recommend", ignoreCase = true) -> "recommendation_with_relaxation"
            query.contains("aclar", ignoreCase = true) || query.contains("clarif", ignoreCase = true) || query.contains("tensión", ignoreCase = true) -> "clarification"
            query.contains("typo", ignoreCase = true) || query.contains("corrige", ignoreCase = true) -> "typo_correction"
            query.contains("scope", ignoreCase = true) || query.contains("alcance", ignoreCase = true) -> "out_of_scope"
            query.contains(" na", ignoreCase = true) || query.contains("no disponible", ignoreCase = true) -> "model_listed_as_na"
            query.contains("763B", ignoreCase = true) || query.contains("spec", ignoreCase = true) || query.contains("ficha", ignoreCase = true) -> "single_spec_card"
            else -> sampleKeys.firstOrNull { query.contains(it, ignoreCase = true) } ?: selectedSampleKey
        }
        return samples[match] ?: samples.values.firstOrNull()
    }
}

