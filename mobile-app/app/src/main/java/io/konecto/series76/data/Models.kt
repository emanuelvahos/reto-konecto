package io.konecto.series76.data

import androidx.compose.runtime.Immutable
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Immutable
@Serializable
data class LoginRequest(
    val email: String,
    val password: String
)

@Immutable
@Serializable
data class UserInfo(
    val id: String = "",
    val email: String = "",
    @SerialName("full_name") val fullName: String = "",
    val role: String = "plant_engineer"
)

@Immutable
@Serializable
data class LoginResponse(
    val token: String,
    @SerialName("access_token") val accessToken: String = "",
    @SerialName("token_type") val tokenType: String = "bearer",
    val user: UserInfo
)

@Immutable
@Serializable
data class ConversationRequest(
    @SerialName("session_id") val sessionId: String? = null,
    val query: String
)

@Immutable
@Serializable
data class ActuatorDto(
    val id: Int? = null,
    @SerialName("base_part_number") val basePartNumber: String = "",
    @SerialName("size_code") val sizeCode: String = "",
    @SerialName("frame_size") val frameSize: Int = 0,
    @SerialName("enclosure_type") val enclosureType: String = "",
    @SerialName("power_supply") val powerSupply: String = "",
    @SerialName("voltage_num") val voltageNum: Int = 0,
    @SerialName("phase_type") val phaseType: String = "",
    @SerialName("service_support") val serviceSupport: String = "",
    @SerialName("is_available") val isAvailable: Boolean = true,
    @SerialName("on_off_torque_in_lbs") val onOffTorqueInLbs: Double? = null,
    @SerialName("on_off_torque_nm") val onOffTorqueNm: Double? = null,
    @SerialName("on_off_duty_cycle_pct") val onOffDutyCyclePct: Int? = null,
    @SerialName("cycles_per_hour") val cyclesPerHour: Int? = null,
    @SerialName("modulating_torque_in_lbs") val modulatingTorqueInLbs: Double? = null,
    @SerialName("modulating_torque_nm") val modulatingTorqueNm: Double? = null,
    @SerialName("modulating_duty_cycle_pct") val modulatingDutyCyclePct: Int? = null,
    @SerialName("starts_per_hour") val startsPerHour: Int? = null,
    @SerialName("speed_60hz_sec") val speed60HzSec: Double? = null,
    @SerialName("speed_50hz_sec") val speed50HzSec: Double? = null,
    @SerialName("speed_dc_or_fixed_sec") val speedDcOrFixedSec: Double? = null,
    @SerialName("fla_60hz_amps") val fla60HzAmps: Double? = null,
    @SerialName("fla_50hz_amps") val fla50HzAmps: Double? = null,
    @SerialName("fla_dc_or_fixed_amps") val flaDcOrFixedAmps: Double? = null,
    @SerialName("lra_60hz_amps") val lra60HzAmps: Double? = null,
    @SerialName("lra_50hz_amps") val lra50HzAmps: Double? = null,
    @SerialName("lra_dc_or_fixed_amps") val lraDcOrFixedAmps: Double? = null,
    @SerialName("motor_power_watts") val motorPowerWatts: Int? = null,
    @SerialName("csa_certified") val csaCertified: Boolean = true,
    @SerialName("ce_ukca_certified") val ceUkcaCertified: Boolean = false,
    @SerialName("hazardous_classification") val hazardousClassification: String? = null
)

@Immutable
@Serializable
data class UIPayload(
    @SerialName("display_type") val displayType: String = "TEXT_ONLY",
    val actuators: List<ActuatorDto> = emptyList(),
    @SerialName("engineering_warnings") val engineeringWarnings: List<String> = emptyList()
)

@Immutable
@Serializable
data class ToolCallTrace(
    @SerialName("tool_name") val toolName: String = "",
    val arguments: JsonElement? = null,
    @SerialName("sql_executed") val sqlExecuted: String? = null,
    @SerialName("raw_output") val rawOutput: JsonElement? = null,
    @SerialName("execution_time_ms") val executionTimeMs: Double = 0.0
)

@Immutable
@Serializable
data class DebugTracePayload(
    @SerialName("model_used") val modelUsed: String = "",
    @SerialName("total_latency_ms") val totalLatencyMs: Double = 0.0,
    @SerialName("token_usage") val tokenUsage: JsonElement? = null,
    @SerialName("active_context_part_numbers") val activeContextPartNumbers: List<String> = emptyList(),
    @SerialName("tool_calls") val toolCalls: List<ToolCallTrace> = emptyList()
)

@Immutable
@Serializable
data class ConversationResponse(
    @SerialName("session_id") val sessionId: String,
    val answer: String,
    @SerialName("ui_payload") val uiPayload: UIPayload = UIPayload(),
    @SerialName("debug_trace") val debugTrace: DebugTracePayload = DebugTracePayload()
)

@Immutable
@Serializable
data class SessionSummary(
    @SerialName("session_id") val sessionId: String,
    val title: String,
    @SerialName("active_part_numbers") val activePartNumbers: List<String> = emptyList(),
    @SerialName("message_count") val messageCount: Int = 0,
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("updated_at") val updatedAt: String = ""
)

@Immutable
@Serializable
data class MessageRecord(
    val id: Int,
    val role: String,
    val content: String,
    @SerialName("ui_payload") val uiPayload: UIPayload? = null,
    @SerialName("debug_trace") val debugTrace: DebugTracePayload? = null,
    @SerialName("created_at") val createdAt: String = ""
)

@Immutable
@Serializable
data class SessionHistoryResponse(
    @SerialName("session_id") val sessionId: String,
    val title: String,
    @SerialName("active_part_numbers") val activePartNumbers: List<String> = emptyList(),
    val messages: List<MessageRecord> = emptyList()
)
