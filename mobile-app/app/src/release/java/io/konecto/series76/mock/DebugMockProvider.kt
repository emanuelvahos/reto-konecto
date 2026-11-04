package io.konecto.series76.mock

import android.content.Context
import io.konecto.series76.data.ConversationResponse

object DebugMockProvider {
    const val isAvailable: Boolean = false
    var isMockEnabled: Boolean = false
    var selectedSampleKey: String = ""

    val sampleKeys: List<String> = emptyList()

    fun getAvailableSamples(context: Context): Map<String, ConversationResponse> = emptyMap()

    fun getMockResponse(context: Context, query: String): ConversationResponse? = null
}

