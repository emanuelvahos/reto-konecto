package io.konecto.series76.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
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
                actuator = uiPayload.actuators.first()
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
    size: Dp = 46.dp,
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
    modifier: Modifier = Modifier,
    reduceMotion: Boolean = false
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

    val animValue = remember { Animatable(if (reduceMotion) targetValue.toFloat() else 0f) }
    LaunchedEffect(targetValue) {
        if (!reduceMotion) {
            animValue.animateTo(
                targetValue.toFloat(),
                animationSpec = tween(durationMillis = 550, easing = FastOutSlowInEasing)
            )
        }
    }

    Row(
        modifier = modifier,
        verticalAlignment = Alignment.Bottom
    ) {
        Text(
            text = "${if (reduceMotion) targetValue.toInt() else animValue.value.toInt()}",
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
 * Ficha Técnica Individual (SINGLE_SPEC_CARD)
 * - Muestra frecuencias 60 Hz y 50 Hz a la vez en mini tabla de dos columnas
 * - Detección de trifásico con bloque único de torque y alerta SINGLE_TORQUE_RATING
 * - Copiar con háptica y compartir (Intent.ACTION_SEND)
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun SingleActuatorSpecCard(
    actuator: ActuatorDto
) {
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current

    val reduceMotion = remember {
        try {
            android.provider.Settings.Global.getFloat(
                context.contentResolver,
                android.provider.Settings.Global.TRANSITION_ANIMATION_SCALE,
                1.0f
            ) == 0f
        } catch (e: Exception) {
            false
        }
    }

    // Identificar trifásico: campo phaseType con '3', singleTorque presente, o ausencia de modulante con onOff definido
    val isThreePhase = remember(actuator) {
        actuator.phaseType.contains("3") ||
        actuator.singleTorqueNm != null ||
        (actuator.modulatingTorqueNm == null && actuator.onOffTorqueNm != null)
    }

    fun copyPartNumber() {
        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("part_number", actuator.basePartNumber))
        Toast.makeText(context, context.getString(R.string.card_copied_part), Toast.LENGTH_SHORT).show()
    }

    fun shareDatasheet() {
        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
        val textBuilder = StringBuilder()
        textBuilder.appendLine("KONECTO SERIES 76 DATASHEET")
        textBuilder.appendLine("Part Number: ${actuator.basePartNumber}")
        textBuilder.appendLine("Frame: Frame ${actuator.frameSize} | Enclosure: ${actuator.enclosureType}")
        textBuilder.appendLine("Power Supply: ${actuator.powerSupply}")
        if (isThreePhase) {
            val torque = actuator.singleTorqueNm ?: actuator.onOffTorqueNm
            val torqueInLbs = actuator.singleTorqueInLbs ?: actuator.onOffTorqueInLbs
            textBuilder.appendLine("Output Torque: ${torque?.toInt() ?: "—"} Nm (${torqueInLbs?.toInt() ?: "—"} in-lbs)")
            textBuilder.appendLine("Duty Rating: S4 70%")
        } else {
            textBuilder.appendLine("On/Off Torque: ${actuator.onOffTorqueNm?.toInt() ?: "—"} Nm (${actuator.onOffDutyCyclePct ?: "—"}% duty)")
            textBuilder.appendLine("Modulating Torque: ${actuator.modulatingTorqueNm?.toInt() ?: "—"} Nm (${actuator.modulatingDutyCyclePct ?: "—"}% duty)")
        }
        textBuilder.appendLine("Speed 90°: 60Hz = ${actuator.speed60HzSec ?: actuator.speedDcOrFixedSec ?: "—"}s | 50Hz = ${actuator.speed50HzSec ?: "—"}s")
        textBuilder.appendLine("FLA: 60Hz = ${actuator.fla60HzAmps ?: actuator.flaDcOrFixedAmps ?: "—"}A | 50Hz = ${actuator.fla50HzAmps ?: "—"}A")
        textBuilder.appendLine("LRA: 60Hz = ${actuator.lra60HzAmps ?: actuator.lraDcOrFixedAmps ?: "—"}A | 50Hz = ${actuator.lra50HzAmps ?: "—"}A")
        textBuilder.appendLine("Motor Power: ${actuator.motorPowerWatts ?: "—"} W")
        textBuilder.appendLine("Certification: ${if (actuator.csaCertified) "CSA Certified" else "Not CSA Certified"}")

        val sendIntent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, "Series 76 - ${actuator.basePartNumber}")
            putExtra(Intent.EXTRA_TEXT, textBuilder.toString())
        }
        context.startActivity(Intent.createChooser(sendIntent, context.getString(R.string.card_share_title)))
    }

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(16.dp))
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Cabecera con degradado sutil y acciones
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

                        Row(
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
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

                            // Botón Compartir
                            IconButton(
                                onClick = { shareDatasheet() },
                                modifier = Modifier.size(28.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Share,
                                    contentDescription = stringResource(R.string.card_share_action),
                                    tint = KonectoTheme.semantics.accent,
                                    modifier = Modifier.size(16.dp)
                                )
                            }
                        }
                    }

                    // Part Number Principal (Monospace con icono de copiado y long-press)
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(6.dp))
                            .combinedClickable(
                                onClick = { copyPartNumber() },
                                onLongClick = { copyPartNumber() }
                            )
                            .padding(vertical = 2.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = actuator.basePartNumber,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            fontSize = 17.sp,
                            color = MaterialTheme.colorScheme.onSurface,
                            letterSpacing = (-0.3).sp
                        )

                        IconButton(
                            onClick = { copyPartNumber() },
                            modifier = Modifier.size(26.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.ContentCopy,
                                contentDescription = stringResource(R.string.card_copy_action),
                                tint = KonectoTheme.semantics.accentText,
                                modifier = Modifier.size(15.dp)
                            )
                        }
                    }

                    // Chips de Alimentación y Certificación con iconos
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
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

            // Cuerpo con Secciones Técnicas
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(Spacing.m),
                verticalArrangement = Arrangement.spacedBy(Spacing.s)
            ) {
                // 1. Bloque(s) de Torque
                if (isThreePhase) {
                    // Trifásico: Bloque único "Torque de salida" y alerta SINGLE_TORQUE_RATING
                    val torqueNm = actuator.singleTorqueNm ?: actuator.onOffTorqueNm
                    val torqueInLbs = actuator.singleTorqueInLbs ?: actuator.onOffTorqueInLbs
                    TorqueServiceCard(
                        modifier = Modifier.fillMaxWidth(),
                        title = stringResource(R.string.card_output_torque),
                        torqueNm = torqueNm,
                        torqueInLbs = torqueInLbs,
                        dutyPct = actuator.onOffDutyCyclePct ?: 70,
                        rateText = if (actuator.cyclesPerHour != null) {
                            stringResource(R.string.card_cycles_per_hour, actuator.cyclesPerHour.toString())
                        } else {
                            stringResource(R.string.card_null_placeholder)
                        },
                        reduceMotion = reduceMotion
                    )

                    Surface(
                        color = KonectoTheme.semantics.warningBg,
                        shape = RoundedCornerShape(8.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, KonectoTheme.semantics.warningBorder),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = "ℹ️ ${stringResource(R.string.card_single_torque_alert)}",
                            color = KonectoTheme.semantics.warningText,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)
                        )
                    }
                } else {
                    // Monofásico o DC: Dos bloques lado a lado (On/Off y Modulante)
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
                            rateText = if (actuator.cyclesPerHour != null) {
                                stringResource(R.string.card_cycles_per_hour, actuator.cyclesPerHour.toString())
                            } else {
                                stringResource(R.string.card_null_placeholder)
                            },
                            reduceMotion = reduceMotion
                        )

                        TorqueServiceCard(
                            modifier = Modifier.weight(1f),
                            title = stringResource(R.string.card_modulating_service),
                            torqueNm = actuator.modulatingTorqueNm,
                            torqueInLbs = actuator.modulatingTorqueInLbs,
                            dutyPct = actuator.modulatingDutyCyclePct,
                            rateText = if (actuator.startsPerHour != null) {
                                stringResource(R.string.card_starts_per_hour, actuator.startsPerHour.toString())
                            } else {
                                stringResource(R.string.card_null_placeholder)
                            },
                            reduceMotion = reduceMotion
                        )
                    }
                }

                // 2. Mini Tabla de Frecuencias Side-by-Side (60 Hz | 50 Hz a la vez)
                FrequencySpecMiniTable(actuator = actuator)
            }
        }
    }
}

/**
 * Mini Tabla Técnica de Frecuencias Side-by-Side (60 Hz y 50 Hz a la vez)
 */
@Composable
fun FrequencySpecMiniTable(
    actuator: ActuatorDto,
    modifier: Modifier = Modifier
) {
    val speed60 = actuator.speed60HzSec?.let { "$it s" } ?: actuator.speedDcOrFixedSec?.let { "$it s" } ?: stringResource(R.string.card_null_placeholder)
    val speed50 = actuator.speed50HzSec?.let { "$it s" } ?: stringResource(R.string.card_null_placeholder)

    val fla60 = actuator.fla60HzAmps?.let { "$it A" } ?: actuator.flaDcOrFixedAmps?.let { "$it A" } ?: stringResource(R.string.card_null_placeholder)
    val fla50 = actuator.fla50HzAmps?.let { "$it A" } ?: stringResource(R.string.card_null_placeholder)

    val lra60 = actuator.lra60HzAmps?.let { "$it A" } ?: actuator.lraDcOrFixedAmps?.let { "$it A" } ?: stringResource(R.string.card_null_placeholder)
    val lra50 = actuator.lra50HzAmps?.let { "$it A" } ?: stringResource(R.string.card_null_placeholder)

    val motorPower = if (actuator.motorPowerWatts != null) {
        stringResource(R.string.card_power_value, actuator.motorPowerWatts)
    } else {
        stringResource(R.string.card_null_placeholder)
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(10.dp))
            .padding(10.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        // Encabezado de la mini tabla
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = stringResource(R.string.card_col_metric),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.weight(1.4f)
            )
            Text(
                text = stringResource(R.string.card_col_60hz),
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = KonectoTheme.semantics.accentText,
                textAlign = TextAlign.Center,
                modifier = Modifier.weight(1f)
            )
            Text(
                text = stringResource(R.string.card_col_50hz),
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.weight(1f)
            )
        }

        HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline)

        // Fila 1: Tiempo de giro 90° (Speed)
        FrequencyMetricRow(
            label = stringResource(R.string.card_speed_label),
            val60 = speed60,
            val50 = speed50
        )

        // Fila 2: Corriente nominal (FLA)
        FrequencyMetricRow(
            label = stringResource(R.string.card_fla_metric),
            val60 = fla60,
            val50 = fla50
        )

        // Fila 3: Corriente de arranque (LRA)
        FrequencyMetricRow(
            label = stringResource(R.string.card_lra_metric),
            val60 = lra60,
            val50 = lra50
        )

        HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline)

        // Fila de Potencia del Motor
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = stringResource(R.string.card_power_label),
                fontSize = 11.sp,
                fontWeight = FontWeight.Medium,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                text = motorPower,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

@Composable
fun FrequencyMetricRow(
    label: String,
    val60: String,
    val50: String
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            fontSize = 11.sp,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.weight(1.4f)
        )
        Text(
            text = val60,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center,
            modifier = Modifier.weight(1f)
        )
        Text(
            text = val50,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.weight(1f)
        )
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
    rateText: String,
    reduceMotion: Boolean = false
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
                AnimatedTorqueValue(targetValue = torqueNm, unit = "Nm", reduceMotion = reduceMotion)
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
 * Esqueleto Shimmer de Carga para Fichas y Respuestas Técnicas
 */
@Composable
fun ShimmerSkeletonCard(
    modifier: Modifier = Modifier
) {
    val transition = rememberInfiniteTransition(label = "shimmer")
    val translateAnim by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1000f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1200, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "shimmerX"
    )

    val shimmerColors = listOf(
        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.9f),
        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
    )

    val brush = Brush.linearGradient(
        colors = shimmerColors,
        start = Offset(x = translateAnim - 300f, y = translateAnim - 300f),
        end = Offset(x = translateAnim, y = translateAnim)
    )

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(16.dp))
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(Spacing.m),
            verticalArrangement = Arrangement.spacedBy(Spacing.s)
        ) {
            // Header skeleton
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .width(130.dp)
                        .height(14.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(brush)
                )
                Box(
                    modifier = Modifier
                        .width(70.dp)
                        .height(18.dp)
                        .clip(RoundedCornerShape(6.dp))
                        .background(brush)
                )
            }

            Box(
                modifier = Modifier
                    .width(200.dp)
                    .height(20.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .background(brush)
            )

            HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)

            // Torque boxes skeleton
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(Spacing.s)
            ) {
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(72.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(brush)
                )
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(72.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(brush)
                )
            }

            // Table rows skeleton
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(84.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(brush)
            )
        }
    }
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
                            text = stringResource(R.string.table_title),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = stringResource(R.string.table_selected_count, actuators.size),
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
                                text = stringResource(R.string.table_hz_toggle, selectedHz),
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
                            .width(125.dp)
                            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(8.dp))
                            .padding(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text(stringResource(R.string.table_col_part), fontWeight = FontWeight.Bold, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                        Text(stringResource(R.string.table_col_enclosure), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(stringResource(R.string.table_col_power_supply), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(stringResource(R.string.table_col_on_off_torque), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(stringResource(R.string.table_col_mod_torque), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(stringResource(R.string.table_col_duty), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(stringResource(R.string.card_speed_label), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(stringResource(R.string.card_fla_label, selectedHz), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(stringResource(R.string.card_lra_label, selectedHz), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(stringResource(R.string.card_power_label), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(stringResource(R.string.table_col_cert), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                                color = KonectoTheme.semantics.accentText
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
