package io.konecto.series76.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.data.ActuatorDto
import io.konecto.series76.data.UIPayload

// =====================================================================
// PALETA NATURAL / SWISS INDUSTRIAL TOKENS (Linear / Notion / Apple HIG)
// =====================================================================
val NaturalBg = Color(0xFFF7F7F5)
val NaturalCardBg = Color(0xFFFFFFFF)
val NaturalBorder = Color(0xFFE4E4E7)
val NaturalSurfaceMuted = Color(0xFFF4F4F5)
val NaturalSurfaceSubtle = Color(0xFFFAFAFA)
val NaturalTextPrimary = Color(0xFF18181B)
val NaturalTextSecondary = Color(0xFF71717A)
val NaturalAccentBlue = Color(0xFF2563EB)
val NaturalBadgeGreenBg = Color(0xFFDCFCE7)
val NaturalBadgeGreenText = Color(0xFF166534)
val NaturalBadgeWarningBg = Color(0xFFFEF3C7)
val NaturalBadgeWarningText = Color(0xFF92400E)

@Composable
fun ProductDataVisualizer(
    uiPayload: UIPayload,
    contextText: String? = null
) {
    // Si la consulta o contexto menciona explícitamente 50Hz, inicializar en 50 Hz
    val defaultHz = remember(contextText) {
        if (contextText != null && (
            contextText.contains("50Hz", ignoreCase = true) ||
            contextText.contains("50 Hz", ignoreCase = true)
        )) {
            50
        } else {
            60
        }
    }
    var selectedHz by remember(defaultHz) { mutableStateOf(defaultHz) }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        // 1. Alertas de Ingeniería (Tamaños 6 y 7 sin CSA, modelos N/A, Relajación de restricciones)
        uiPayload.engineeringWarnings.forEach { warning ->
            Surface(
                color = NaturalBadgeWarningBg,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, Color(0xFFFDE68A), RoundedCornerShape(12.dp))
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(text = "⚠️", fontSize = 16.sp)
                    Text(
                        text = warning,
                        color = NaturalBadgeWarningText,
                        fontSize = 12.sp,
                        lineHeight = 17.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }

        if (uiPayload.actuators.isEmpty()) return@Column

        // 2. Renderizado: Tarjeta Técnica Individual (1 modelo) o Tabla Comparativa (2+ modelos)
        if (uiPayload.actuators.size == 1) {
            SingleActuatorSpecCard(
                actuator = uiPayload.actuators.first(),
                selectedHz = selectedHz,
                onSelectHz = { selectedHz = it }
            )
        } else {
            ActuatorComparisonTable(
                actuators = uiPayload.actuators,
                selectedHz = selectedHz,
                onSelectHz = { selectedHz = it }
            )
        }
    }
}

/**
 * Control Segmentado Integrado (Sobrio y minimalista)
 */
@Composable
fun CompactSegmentedFrequencyControl(
    selectedHz: Int,
    onSelectHz: (Int) -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .height(34.dp)
            .background(NaturalSurfaceMuted, RoundedCornerShape(8.dp))
            .border(1.dp, NaturalBorder, RoundedCornerShape(8.dp))
            .padding(2.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        listOf(60, 50).forEach { hz ->
            val isSelected = selectedHz == hz
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .clip(RoundedCornerShape(6.dp))
                    .background(if (isSelected) NaturalTextPrimary else Color.Transparent)
                    .clickable { onSelectHz(hz) },
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "$hz Hz Grid Frequency",
                    fontSize = 11.sp,
                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                    color = if (isSelected) Color.White else NaturalTextSecondary,
                    letterSpacing = (-0.1).sp
                )
            }
        }
    }
}

/**
 * Tarjeta Técnica Sobria estilo Linear / Swiss Industrial Design
 */
@Composable
fun SingleActuatorSpecCard(
    actuator: ActuatorDto,
    selectedHz: Int = 60,
    onSelectHz: (Int) -> Unit = {}
) {
    val hasAcModels = actuator.speed60HzSec != null || actuator.speed50HzSec != null

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = NaturalCardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, NaturalBorder, RoundedCornerShape(16.dp))
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // =================================================================
            // 1. CABECERA LIMPIA (Gris piedra sutil, tipografía nítida)
            // =================================================================
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(NaturalSurfaceMuted)
                    .padding(14.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    // Eyebrow & Badge de Enclosure
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "SERIES 76 DATASHEET • FRAME ${actuator.frameSize}",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = NaturalTextSecondary,
                            letterSpacing = 0.8.sp
                        )

                        // Badge de Enclosure (Sutil y sobrio)
                        val isExplosion = actuator.enclosureType == "Explosionproof"
                        Surface(
                            color = if (isExplosion) Color(0xFFFEE2E2) else Color(0xFFE0E7FF),
                            shape = RoundedCornerShape(6.dp),
                            border = androidx.compose.foundation.BorderStroke(
                                1.dp,
                                if (isExplosion) Color(0xFFFECACA) else Color(0xFFC7D2FE)
                            )
                        ) {
                            Text(
                                text = actuator.enclosureType.uppercase(),
                                color = if (isExplosion) Color(0xFF991B1B) else Color(0xFF3730A3),
                                modifier = Modifier.padding(horizontal = 7.dp, vertical = 2.dp),
                                fontSize = 9.sp,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 0.4.sp
                            )
                        }
                    }

                    // Part Number Principal (Monospace grafito profundo)
                    Text(
                        text = actuator.basePartNumber,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp,
                        color = NaturalTextPrimary,
                        letterSpacing = (-0.3).sp
                    )

                    // Fila de Chips de Alimentación y Certificación
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Surface(
                            color = Color.White,
                            shape = RoundedCornerShape(6.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, NaturalBorder)
                        ) {
                            Text(
                                text = "⚡ ${actuator.powerSupply}",
                                color = NaturalTextPrimary,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                            )
                        }

                        Surface(
                            color = if (actuator.csaCertified) NaturalBadgeGreenBg else NaturalBadgeWarningBg,
                            shape = RoundedCornerShape(6.dp),
                            border = androidx.compose.foundation.BorderStroke(
                                1.dp,
                                if (actuator.csaCertified) Color(0xFFBBF7D0) else Color(0xFFFDE68A)
                            )
                        ) {
                            Text(
                                text = if (actuator.csaCertified) "✓ CSA Certified" else "⚠ CE/UKCA Only",
                                color = if (actuator.csaCertified) NaturalBadgeGreenText else NaturalBadgeWarningText,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                            )
                        }
                    }
                }
            }

            HorizontalDivider(thickness = 1.dp, color = NaturalBorder)

            // =================================================================
            // 2. CUERPO DE TORQUE CON MICRO-GAUGES SOBRIOS
            // =================================================================
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    // Tarjeta ON/OFF SERVICE
                    TorqueServiceCard(
                        modifier = Modifier.weight(1f),
                        title = "ON/OFF SERVICE",
                        torqueNm = actuator.onOffTorqueNm,
                        torqueInLbs = actuator.onOffTorqueInLbs,
                        dutyPct = actuator.onOffDutyCyclePct,
                        rateText = "${actuator.cyclesPerHour ?: "-"} cyc/hr"
                    )

                    // Tarjeta MODULATING SERVICE
                    TorqueServiceCard(
                        modifier = Modifier.weight(1f),
                        title = "MODULATING",
                        torqueNm = actuator.modulatingTorqueNm,
                        torqueInLbs = actuator.modulatingTorqueInLbs,
                        dutyPct = actuator.modulatingDutyCyclePct,
                        rateText = "${actuator.startsPerHour ?: "-"} st/hr"
                    )
                }

                // =============================================================
                // 3. CONTROL SEGMENTADO 60 HZ / 50 HZ INTEGRADO
                // =============================================================
                if (hasAcModels) {
                    CompactSegmentedFrequencyControl(
                        selectedHz = selectedHz,
                        onSelectHz = onSelectHz
                    )
                }

                // =============================================================
                // 4. CUADRÍCULA DE 4 MÉTRICAS ELÉCTRICAS (Cajas limpias, sin arcoíris)
                // =============================================================
                val speed = if (selectedHz == 60) actuator.speed60HzSec ?: actuator.speedDcOrFixedSec else actuator.speed50HzSec ?: actuator.speedDcOrFixedSec
                val fla = if (selectedHz == 60) actuator.fla60HzAmps ?: actuator.flaDcOrFixedAmps else actuator.fla50HzAmps ?: actuator.flaDcOrFixedAmps
                val lra = if (selectedHz == 60) actuator.lra60HzAmps ?: actuator.lraDcOrFixedAmps else actuator.lra50HzAmps ?: actuator.lraDcOrFixedAmps

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    IndustrialMetricBox(
                        modifier = Modifier.weight(1f),
                        label = "Speed 90°",
                        value = if (speed != null) "${speed}s" else "-"
                    )
                    IndustrialMetricBox(
                        modifier = Modifier.weight(1f),
                        label = "FLA ($selectedHz Hz)",
                        value = if (fla != null) "$fla A" else "-"
                    )
                    IndustrialMetricBox(
                        modifier = Modifier.weight(1f),
                        label = "LRA ($selectedHz Hz)",
                        value = if (lra != null) "$lra A" else "-"
                    )
                    IndustrialMetricBox(
                        modifier = Modifier.weight(1f),
                        label = "Power",
                        value = if (actuator.motorPowerWatts != null) "${actuator.motorPowerWatts} W" else "-"
                    )
                }
            }
        }
    }
}

/**
 * Micro-tarjeta de Servicio con Barra Visual (Duty Cycle Micro-Gauge)
 */
@Composable
fun TorqueServiceCard(
    modifier: Modifier = Modifier,
    title: String,
    torqueNm: Double?,
    torqueInLbs: Double?,
    dutyPct: Int?,
    rateText: String
) {
    Column(
        modifier = modifier
            .background(NaturalSurfaceSubtle, RoundedCornerShape(10.dp))
            .border(1.dp, NaturalBorder, RoundedCornerShape(10.dp))
            .padding(10.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        Text(
            text = title,
            fontSize = 9.sp,
            fontWeight = FontWeight.Bold,
            color = NaturalTextSecondary,
            letterSpacing = 0.5.sp
        )

        // Torque principal grande
        Text(
            text = if (torqueNm != null) "${torqueNm.toInt()} Nm" else "N/A",
            fontSize = 17.sp,
            fontWeight = FontWeight.Bold,
            color = NaturalTextPrimary,
            letterSpacing = (-0.3).sp
        )

        // Equivalente imperial
        Text(
            text = if (torqueInLbs != null) "${torqueInLbs.toInt()} in-lbs" else "—",
            fontSize = 11.sp,
            fontWeight = FontWeight.Normal,
            color = NaturalTextSecondary
        )

        Spacer(modifier = Modifier.height(2.dp))

        // Micro-Gauge: barra horizontal sobria de progreso de Duty Cycle
        val safePct = (dutyPct ?: 0).coerceIn(0, 100)
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(4.dp)
                .background(NaturalBorder, RoundedCornerShape(2.dp))
        ) {
            Box(
                modifier = Modifier
                    .fillMaxHeight()
                    .fillMaxWidth(fraction = safePct / 100f)
                    .background(NaturalTextPrimary, RoundedCornerShape(2.dp))
            )
        }

        Text(
            text = "Duty ${dutyPct ?: "-"}% • $rateText",
            fontSize = 10.sp,
            fontWeight = FontWeight.Medium,
            color = NaturalTextSecondary
        )
    }
}

/**
 * Caja de Métrica limpia estilo Linear / Swiss (Sin líneas arcoíris)
 */
@Composable
fun IndustrialMetricBox(
    modifier: Modifier = Modifier,
    label: String,
    value: String
) {
    Column(
        modifier = modifier
            .background(NaturalSurfaceSubtle, RoundedCornerShape(8.dp))
            .border(1.dp, NaturalBorder, RoundedCornerShape(8.dp))
            .padding(horizontal = 4.dp, vertical = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        Text(
            text = value,
            fontSize = 14.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            color = NaturalTextPrimary,
            textAlign = TextAlign.Center,
            maxLines = 1
        )
        Text(
            text = label,
            fontSize = 9.sp,
            fontWeight = FontWeight.Medium,
            color = NaturalTextSecondary,
            textAlign = TextAlign.Center,
            maxLines = 1
        )
    }
}

/** Alias de compatibilidad */
@Composable
fun ActuatorSpecCard(actuator: ActuatorDto, selectedHz: Int = 60) {
    SingleActuatorSpecCard(actuator = actuator, selectedHz = selectedHz)
}

/**
 * Tabla Comparativa Side-by-Side con paleta Swiss Industrial
 */
@Composable
fun ActuatorComparisonTable(
    actuators: List<ActuatorDto>,
    selectedHz: Int = 60,
    onSelectHz: (Int) -> Unit = {}
) {
    val scrollState = rememberScrollState()
    val hasAcModels = actuators.any { it.speed60HzSec != null || it.speed50HzSec != null }

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = NaturalCardBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, NaturalBorder, RoundedCornerShape(16.dp))
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Header limpio
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(NaturalSurfaceMuted)
                    .padding(14.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "SERIES 76 COMPARISON",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = NaturalTextSecondary,
                            letterSpacing = 0.8.sp
                        )
                        Text(
                            text = "${actuators.size} Actuators Selected",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = NaturalTextPrimary
                        )
                    }
                    if (hasAcModels) {
                        Surface(
                            color = NaturalTextPrimary,
                            shape = RoundedCornerShape(6.dp),
                            modifier = Modifier.clickable { onSelectHz(if (selectedHz == 60) 50 else 60) }
                        ) {
                            Text(
                                text = "$selectedHz Hz (Tap to toggle)",
                                color = Color.White,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp)
                            )
                        }
                    }
                }
            }

            HorizontalDivider(thickness = 1.dp, color = NaturalBorder)

            // Cuerpo desplazable
            Column(modifier = Modifier.padding(10.dp)) {
                Row(modifier = Modifier.horizontalScroll(scrollState)) {
                    // Columna fija de etiquetas
                    Column(
                        modifier = Modifier
                            .width(115.dp)
                            .background(NaturalSurfaceSubtle, RoundedCornerShape(8.dp))
                            .border(1.dp, NaturalBorder, RoundedCornerShape(8.dp))
                            .padding(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text("Part Number", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = NaturalTextPrimary)
                        Text("Enclosure", fontSize = 11.sp, color = NaturalTextSecondary)
                        Text("Power Supply", fontSize = 11.sp, color = NaturalTextSecondary)
                        Text("On/Off Torque", fontSize = 11.sp, color = NaturalTextSecondary)
                        Text("Mod. Torque", fontSize = 11.sp, color = NaturalTextSecondary)
                        Text("Duty (On/Mod)", fontSize = 11.sp, color = NaturalTextSecondary)
                        Text("Speed ($selectedHz Hz)", fontSize = 11.sp, color = NaturalTextSecondary)
                        Text("FLA ($selectedHz Hz)", fontSize = 11.sp, color = NaturalTextSecondary)
                        Text("LRA ($selectedHz Hz)", fontSize = 11.sp, color = NaturalTextSecondary)
                        Text("Motor Power", fontSize = 11.sp, color = NaturalTextSecondary)
                        Text("Certification", fontSize = 11.sp, color = NaturalTextSecondary)
                    }

                    // Columnas de actuadores
                    actuators.forEach { act ->
                        val speed = if (selectedHz == 60) act.speed60HzSec ?: act.speedDcOrFixedSec else act.speed50HzSec ?: act.speedDcOrFixedSec
                        val fla = if (selectedHz == 60) act.fla60HzAmps ?: act.flaDcOrFixedAmps else act.fla50HzAmps ?: act.flaDcOrFixedAmps
                        val lra = if (selectedHz == 60) act.lra60HzAmps ?: act.lraDcOrFixedAmps else act.lra50HzAmps ?: act.lraDcOrFixedAmps

                        Column(
                            modifier = Modifier
                                .width(150.dp)
                                .padding(horizontal = 8.dp, vertical = 8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text(
                                text = act.basePartNumber,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                fontSize = 11.sp,
                                color = NaturalTextPrimary
                            )
                            Text(act.enclosureType, fontSize = 11.sp, color = NaturalTextPrimary)
                            Text(act.powerSupply, fontSize = 11.sp, color = NaturalTextPrimary)
                            Text(
                                text = if (act.onOffTorqueNm != null) "${act.onOffTorqueNm.toInt()} Nm" else "N/A",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = NaturalTextPrimary
                            )
                            Text(
                                text = if (act.modulatingTorqueNm != null) "${act.modulatingTorqueNm.toInt()} Nm" else "N/A",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = NaturalTextPrimary
                            )
                            Text("${act.onOffDutyCyclePct ?: "-"}% / ${act.modulatingDutyCyclePct ?: "-"}%", fontSize = 11.sp, color = NaturalTextPrimary)
                            Text(if (speed != null) "$speed s" else "-", fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold, color = NaturalTextPrimary)
                            Text(if (fla != null) "$fla A" else "-", fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold, color = NaturalTextPrimary)
                            Text(if (lra != null) "$lra A" else "-", fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold, color = NaturalTextPrimary)
                            Text(if (act.motorPowerWatts != null) "${act.motorPowerWatts} W" else "-", fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = NaturalTextPrimary)
                            Text(
                                text = if (act.csaCertified) "CSA Certified" else "CE Only",
                                fontSize = 11.sp,
                                color = if (act.csaCertified) NaturalBadgeGreenText else NaturalBadgeWarningText,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            }
        }
    }
}
