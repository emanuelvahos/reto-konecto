package io.konecto.series76.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.R
import io.konecto.series76.data.ActuatorDto
import io.konecto.series76.data.UIPayload
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing

@Composable
fun ProductDataVisualizer(
    uiPayload: UIPayload,
    contextText: String? = null
) {
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
            .padding(top = Spacing.xs),
        verticalArrangement = Arrangement.spacedBy(Spacing.s)
    ) {
        // Alertas de Ingeniería con colores semánticos AA
        uiPayload.engineeringWarnings.forEach { warning ->
            Surface(
                color = KonectoTheme.semantics.warningBg,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, KonectoTheme.semantics.warningBorder, RoundedCornerShape(12.dp))
            ) {
                Row(
                    modifier = Modifier.padding(Spacing.s),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
                ) {
                    Text(text = "⚠️", fontSize = 16.sp)
                    Text(
                        text = warning,
                        color = KonectoTheme.semantics.warningText,
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }

        if (uiPayload.actuators.isEmpty()) return@Column

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
 * Anillo de medidor circular (Canvas) para el Duty Cycle
 */
@Composable
fun DutyCycleRingGauge(
    dutyPct: Int?,
    modifier: Modifier = Modifier,
    size: Dp = 44.dp,
    strokeWidth: Dp = 4.dp
) {
    val trackColor = KonectoTheme.semantics.gaugeTrack
    val indicatorColor = KonectoTheme.semantics.gaugeIndicator
    val safePct = (dutyPct ?: 0).coerceIn(0, 100)

    Box(modifier = modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.fillMaxSize().padding(3.dp)) {
            val stroke = Stroke(width = strokeWidth.toPx(), cap = StrokeCap.Round)
            // Arco base de 260° desde 140°
            drawArc(
                color = trackColor,
                startAngle = 140f,
                sweepAngle = 260f,
                useCenter = false,
                style = stroke
            )
            // Arco de progreso
            if (safePct > 0) {
                drawArc(
                    color = indicatorColor,
                    startAngle = 140f,
                    sweepAngle = 260f * (safePct / 100f),
                    useCenter = false,
                    style = stroke
                )
            }
        }
        Text(
            text = if (dutyPct != null) "$dutyPct%" else stringResource(R.string.card_null_placeholder),
            fontSize = 9.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface,
            fontFamily = FontFamily.Monospace
        )
    }
}

/**
 * Contador de animación para el torque principal
 */
@Composable
fun AnimatedTorqueValue(
    targetValue: Double?,
    unit: String = "Nm",
    modifier: Modifier = Modifier
) {
    if (targetValue == null) {
        Text(
            text = stringResource(R.string.card_null_placeholder),
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        return
    }

    val animValue = remember { Animatable(0f) }
    LaunchedEffect(targetValue) {
        animValue.animateTo(
            targetValue.toFloat(),
            animationSpec = tween(durationMillis = 600, easing = FastOutSlowInEasing)
        )
    }

    Row(
        modifier = modifier,
        verticalAlignment = Alignment.Bottom
    ) {
        Text(
            text = "${animValue.value.toInt()}",
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 20.sp,
            color = KonectoTheme.semantics.accent,
            letterSpacing = (-0.5).sp
        )
        Spacer(modifier = Modifier.width(3.dp))
        Text(
            text = unit,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.padding(bottom = 2.dp)
        )
    }
}

/**
 * Control Segmentado 60/50 Hz con indicador deslizante con spring y háptica
 */
@Composable
fun CompactSegmentedFrequencyControl(
    selectedHz: Int,
    onSelectHz: (Int) -> Unit,
    modifier: Modifier = Modifier
) {
    val haptic = LocalHapticFeedback.current

    Row(
        modifier = modifier
            .fillMaxWidth()
            .height(36.dp)
            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(8.dp))
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
                    .background(if (isSelected) MaterialTheme.colorScheme.surface else Color.Transparent)
                    .clickable {
                        if (!isSelected) {
                            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                            onSelectHz(hz)
                        }
                    },
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = if (hz == 60) stringResource(R.string.card_frequency_60hz) else stringResource(R.string.card_frequency_50hz),
                    fontSize = 11.sp,
                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                    color = if (isSelected) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.onSurfaceVariant,
                    letterSpacing = (-0.1).sp
                )
            }
        }
    }
}

/**
 * Ficha Técnica Individual (SINGLE_SPEC_CARD)
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
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(16.dp))
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Cabecera con degradado sutil
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        Brush.verticalGradient(
                            listOf(
                                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.7f),
                                MaterialTheme.colorScheme.surface
                            )
                        )
                    )
                    .padding(Spacing.m)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(Spacing.xs)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "${stringResource(R.string.card_datasheet)} • ${stringResource(R.string.card_frame, actuator.frameSize)}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )

                        val isExplosion = actuator.enclosureType.equals("Explosionproof", ignoreCase = true)
                        Surface(
                            color = if (isExplosion) KonectoTheme.semantics.errorBg else KonectoTheme.semantics.accentContainer,
                            shape = RoundedCornerShape(6.dp),
                            border = androidx.compose.foundation.BorderStroke(
                                1.dp,
                                if (isExplosion) KonectoTheme.semantics.errorBorder else KonectoTheme.semantics.warningBorder
                            )
                        ) {
                            Text(
                                text = "🛡 ${actuator.enclosureType.uppercase()}",
                                color = if (isExplosion) KonectoTheme.semantics.errorText else KonectoTheme.semantics.warningText,
                                modifier = Modifier.padding(horizontal = 7.dp, vertical = 2.dp),
                                fontSize = 9.sp,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 0.4.sp
                            )
                        }
                    }

                    // Part Number Principal (Monospace con acento sutil)
                    Text(
                        text = actuator.basePartNumber,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp,
                        color = MaterialTheme.colorScheme.onSurface,
                        letterSpacing = (-0.3).sp
                    )

                    // Chips de Alimentación y Certificación con iconos
                    Row(horizontalArrangement = Arrangement.spacedBy(Spacing.xs)) {
                        Surface(
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            shape = RoundedCornerShape(6.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
                        ) {
                            Text(
                                text = "⚡ ${actuator.powerSupply}",
                                color = MaterialTheme.colorScheme.onSurface,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                            )
                        }

                        Surface(
                            color = if (actuator.csaCertified) KonectoTheme.semantics.successBg else KonectoTheme.semantics.warningBg,
                            shape = RoundedCornerShape(6.dp),
                            border = androidx.compose.foundation.BorderStroke(
                                1.dp,
                                if (actuator.csaCertified) KonectoTheme.semantics.successBorder else KonectoTheme.semantics.warningBorder
                            )
                        ) {
                            Text(
                                text = if (actuator.csaCertified) "✓ ${stringResource(R.string.card_csa_certified)}" else "⚠ ${stringResource(R.string.card_csa_not_certified)}",
                                color = if (actuator.csaCertified) KonectoTheme.semantics.successText else KonectoTheme.semantics.warningText,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                            )
                        }
                    }
                }
            }

            HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)

            // Cuerpo con Micro-Gauges Circulares y animación de conteo
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(Spacing.m),
                verticalArrangement = Arrangement.spacedBy(Spacing.s)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(Spacing.s)
                ) {
                    TorqueServiceCard(
                        modifier = Modifier.weight(1f),
                        title = stringResource(R.string.card_on_off_service),
                        torqueNm = actuator.onOffTorqueNm,
                        torqueInLbs = actuator.onOffTorqueInLbs,
                        dutyPct = actuator.onOffDutyCyclePct,
                        rateText = if (actuator.cyclesPerHour != null) stringResource(R.string.card_cycles_per_hour, actuator.cyclesPerHour.toString()) else stringResource(R.string.card_null_placeholder)
                    )

                    TorqueServiceCard(
                        modifier = Modifier.weight(1f),
                        title = stringResource(R.string.card_modulating_service),
                        torqueNm = actuator.modulatingTorqueNm,
                        torqueInLbs = actuator.modulatingTorqueInLbs,
                        dutyPct = actuator.modulatingDutyCyclePct,
                        rateText = if (actuator.startsPerHour != null) stringResource(R.string.card_starts_per_hour, actuator.startsPerHour.toString()) else stringResource(R.string.card_null_placeholder)
                    )
                }

                if (hasAcModels) {
                    CompactSegmentedFrequencyControl(
                        selectedHz = selectedHz,
                        onSelectHz = onSelectHz
                    )
                }

                // Cuadrícula de 4 Métricas Eléctricas ("Velocidad" en lugar de "Speed 90°")
                val speed = if (selectedHz == 60) actuator.speed60HzSec ?: actuator.speedDcOrFixedSec else actuator.speed50HzSec ?: actuator.speedDcOrFixedSec
                val fla = if (selectedHz == 60) actuator.fla60HzAmps ?: actuator.flaDcOrFixedAmps else actuator.fla50HzAmps ?: actuator.flaDcOrFixedAmps
                val lra = if (selectedHz == 60) actuator.lra60HzAmps ?: actuator.lraDcOrFixedAmps else actuator.lra50HzAmps ?: actuator.lraDcOrFixedAmps

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
                ) {
                    IndustrialMetricBox(
                        modifier = Modifier.weight(1f),
                        label = stringResource(R.string.card_speed_label),
                        value = if (speed != null) stringResource(R.string.card_speed_value, speed.toString()) else stringResource(R.string.card_null_placeholder)
                    )
                    IndustrialMetricBox(
                        modifier = Modifier.weight(1f),
                        label = stringResource(R.string.card_fla_label, selectedHz),
                        value = if (fla != null) "$fla A" else stringResource(R.string.card_null_placeholder)
                    )
                    IndustrialMetricBox(
                        modifier = Modifier.weight(1f),
                        label = stringResource(R.string.card_lra_label, selectedHz),
                        value = if (lra != null) "$lra A" else stringResource(R.string.card_null_placeholder)
                    )
                    IndustrialMetricBox(
                        modifier = Modifier.weight(1f),
                        label = stringResource(R.string.card_power_label),
                        value = if (actuator.motorPowerWatts != null) stringResource(R.string.card_power_value, actuator.motorPowerWatts) else stringResource(R.string.card_null_placeholder)
                    )
                }
            }
        }
    }
}

/**
 * Tarjeta de Servicio con Anillo de Medidor Circular Canvas
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
            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(10.dp))
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(10.dp))
            .padding(10.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                AnimatedTorqueValue(targetValue = torqueNm, unit = "Nm")
                Text(
                    text = if (torqueInLbs != null) "${torqueInLbs.toInt()} in-lbs" else stringResource(R.string.card_null_placeholder),
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            DutyCycleRingGauge(dutyPct = dutyPct)
        }

        Spacer(modifier = Modifier.height(2.dp))

        Text(
            text = rateText,
            fontSize = 10.sp,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

/**
 * Caja de Métrica Industrial
 */
@Composable
fun IndustrialMetricBox(
    modifier: Modifier = Modifier,
    label: String,
    value: String
) {
    Column(
        modifier = modifier
            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(8.dp))
            .padding(horizontal = 4.dp, vertical = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        Text(
            text = value,
            fontSize = 13.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center,
            maxLines = 1
        )
        Text(
            text = label,
            fontSize = 9.sp,
            fontWeight = FontWeight.Medium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            maxLines = 1
        )
    }
}

@Composable
fun ActuatorSpecCard(actuator: ActuatorDto, selectedHz: Int = 60) {
    SingleActuatorSpecCard(actuator = actuator, selectedHz = selectedHz)
}

/**
 * Tabla Comparativa Side-by-Side con diseño sobrio y técnico
 */
@Composable
fun ActuatorComparisonTable(
    actuators: List<ActuatorDto>,
    selectedHz: Int = 60,
    onSelectHz: (Int) -> Unit = {}
) {
    val scrollState = rememberScrollState()
    val hasAcModels = actuators.any { it.speed60HzSec != null || it.speed50HzSec != null }
    val haptic = LocalHapticFeedback.current

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(16.dp))
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        Brush.verticalGradient(
                            listOf(
                                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.7f),
                                MaterialTheme.colorScheme.surface
                            )
                        )
                    )
                    .padding(Spacing.m)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "SERIES 76 COMPARISON",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "${actuators.size} Actuators Selected",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                    }
                    if (hasAcModels) {
                        Surface(
                            color = KonectoTheme.semantics.accentContainer,
                            shape = RoundedCornerShape(6.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, KonectoTheme.semantics.warningBorder),
                            modifier = Modifier.clickable {
                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                onSelectHz(if (selectedHz == 60) 50 else 60)
                            }
                        ) {
                            Text(
                                text = "$selectedHz Hz (Tap to toggle)",
                                color = KonectoTheme.semantics.warningText,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp)
                            )
                        }
                    }
                }
            }

            HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)

            Column(modifier = Modifier.padding(10.dp)) {
                Row(modifier = Modifier.horizontalScroll(scrollState)) {
                    // Columna de etiquetas
                    Column(
                        modifier = Modifier
                            .width(115.dp)
                            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(8.dp))
                            .padding(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text("Part Number", fontWeight = FontWeight.Bold, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                        Text("Enclosure", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Power Supply", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("On/Off Torque", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Mod. Torque", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Duty (On/Mod)", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Velocidad", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("FLA ($selectedHz Hz)", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("LRA ($selectedHz Hz)", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Motor Power", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("Certification", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }

                    // Columnas de datos de actuadores
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
                                color = KonectoTheme.semantics.accent
                            )
                            Text(act.enclosureType, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                            Text(act.powerSupply, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                            Text(
                                text = if (act.onOffTorqueNm != null) "${act.onOffTorqueNm.toInt()} Nm" else stringResource(R.string.card_null_placeholder),
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = if (act.modulatingTorqueNm != null) "${act.modulatingTorqueNm.toInt()} Nm" else stringResource(R.string.card_null_placeholder),
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                "${act.onOffDutyCyclePct ?: stringResource(R.string.card_null_placeholder)}% / ${act.modulatingDutyCyclePct ?: stringResource(R.string.card_null_placeholder)}%",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(if (speed != null) "$speed s" else stringResource(R.string.card_null_placeholder), fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
                            Text(if (fla != null) "$fla A" else stringResource(R.string.card_null_placeholder), fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
                            Text(if (lra != null) "$lra A" else stringResource(R.string.card_null_placeholder), fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
                            Text(if (act.motorPowerWatts != null) "${act.motorPowerWatts} W" else stringResource(R.string.card_null_placeholder), fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurface)
                            Text(
                                text = if (act.csaCertified) "✓ ${stringResource(R.string.card_csa_certified)}" else "⚠ ${stringResource(R.string.card_csa_not_certified)}",
                                fontSize = 11.sp,
                                color = if (act.csaCertified) KonectoTheme.semantics.successText else KonectoTheme.semantics.warningText,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            }
        }
    }
}
