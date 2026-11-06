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
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Info
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.R
import io.konecto.series76.data.*
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing

@Composable
fun ProductDataVisualizer(
    uiPayload: UIPayload,
    contextText: String? = null,
    onSendQuery: (String) -> Unit = {},
    onRetry: () -> Unit = {},
    onOpenFullDatasheet: (ActuatorDto) -> Unit = {}
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = Spacing.xs),
        verticalArrangement = Arrangement.spacedBy(Spacing.s)
    ) {
        // Alertas estructuradas (Contract v2) con colores por severidad y botón de reintento
        if (uiPayload.alerts.isNotEmpty()) {
            UIAlertsView(alerts = uiPayload.alerts, onRetry = onRetry)
        }

        // Warnings de ingeniería no cubiertos por alertas estructuradas (evita duplicados con Contract v2)
        val alertMessages = uiPayload.alerts.map { it.message }
        uiPayload.engineeringWarnings.filter { it !in alertMessages }.forEach { warning ->
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

        // Enrutamiento según display_type
        when (uiPayload.displayType) {
            "RECOMMENDATION_LIST" -> {
                uiPayload.recommendation?.let { rec ->
                    RecommendationListView(
                        recommendation = rec,
                        actuators = uiPayload.actuators,
                        onOpenFullDatasheet = onOpenFullDatasheet
                    )
                }
            }
            "CLARIFICATION" -> {
                uiPayload.clarification?.let { clar ->
                    ClarificationView(
                        clarification = clar,
                        onSelectOption = onSendQuery
                    )
                }
            }
            "COMPARISON_TABLE" -> {
                if (uiPayload.actuators.isNotEmpty()) {
                    ActuatorComparisonTable(actuators = uiPayload.actuators)
                }
            }
            "SINGLE_SPEC_CARD" -> {
                if (uiPayload.actuators.isNotEmpty()) {
                    SingleActuatorSpecCard(
                        actuator = uiPayload.actuators.first(),
                        onOpenFullDatasheet = onOpenFullDatasheet
                    )
                }
            }
            else -> {
                // TEXT_ONLY o EDGE_CASE_ALERT: si viene 1 actuador se muestra la ficha, si son varios la comparativa
                if (uiPayload.actuators.size == 1) {
                    SingleActuatorSpecCard(
                        actuator = uiPayload.actuators.first(),
                        onOpenFullDatasheet = onOpenFullDatasheet
                    )
                } else if (uiPayload.actuators.size > 1) {
                    ActuatorComparisonTable(actuators = uiPayload.actuators)
                }
            }
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
    actuator: ActuatorDto,
    onOpenFullDatasheet: ((ActuatorDto) -> Unit)? = null
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
            .semantics {
                contentDescription = context.getString(R.string.card_spec_semantics, actuator.basePartNumber)
            }
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

                // 3. Acción para desplegar Ficha Técnica Completa (ModalBottomSheet)
                if (onOpenFullDatasheet != null) {
                    FilledTonalButton(
                        onClick = { onOpenFullDatasheet(actuator) },
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.filledTonalButtonColors(
                            containerColor = MaterialTheme.colorScheme.surfaceVariant,
                            contentColor = MaterialTheme.colorScheme.onSurface
                        ),
                        border = BorderStroke(1.dp, KonectoTheme.semantics.accent.copy(alpha = 0.5f)),
                        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 4.dp)
                            .semantics {
                                contentDescription = context.getString(R.string.btn_view_full_datasheet)
                            }
                    ) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = null,
                            tint = KonectoTheme.semantics.accent,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = stringResource(R.string.btn_view_full_datasheet),
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
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

private fun copyComparisonTableToClipboard(context: Context, actuators: List<ActuatorDto>) {
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    val sb = StringBuilder()
    sb.appendLine("KONECTO SERIES 76 - ACTUATOR COMPARISON")
    sb.appendLine("Actuadores: " + actuators.joinToString(", ") { it.basePartNumber })
    sb.appendLine("=".repeat(50))
    actuators.forEach { act ->
        val isThreePhase = act.phaseType.contains("3") || act.singleTorqueNm != null
        val t = act.singleTorqueNm ?: act.onOffTorqueNm
        sb.appendLine("• ${act.basePartNumber}:")
        sb.appendLine("  Enclosure: ${act.enclosureType} | Power: ${act.powerSupply}")
        if (isThreePhase) {
            sb.appendLine("  Torque: ${t?.toInt() ?: "—"} Nm (S4 70%)")
        } else {
            sb.appendLine("  On/Off Torque: ${act.onOffTorqueNm?.toInt() ?: "—"} Nm (${act.onOffDutyCyclePct ?: "—"}%)")
            sb.appendLine("  Modulating Torque: ${act.modulatingTorqueNm?.toInt() ?: "—"} Nm (${act.modulatingDutyCyclePct ?: "—"}%)")
        }
        sb.appendLine("  Velocidad 90°: 60Hz = ${act.speed60HzSec ?: act.speedDcOrFixedSec ?: "—"}s | 50Hz = ${act.speed50HzSec ?: "—"}s")
        sb.appendLine("  FLA: 60Hz = ${act.fla60HzAmps ?: act.flaDcOrFixedAmps ?: "—"}A | 50Hz = ${act.fla50HzAmps ?: "—"}A")
        sb.appendLine("  CSA: ${if (act.csaCertified) "Certificado" else "No certificado"}")
    }
    clipboard.setPrimaryClip(ClipData.newPlainText("Series 76 Comparison", sb.toString()))
    Toast.makeText(context, context.getString(R.string.comparison_copied_toast), Toast.LENGTH_SHORT).show()
}

/**
 * Tabla Comparativa Side-by-Side con primera columna fija y ambas frecuencias (60 y 50 Hz)
 */
/**
 * Determina marcadores neutros (▲ mayor / ▼ menor) para filas numéricas.
 * No marca empates ni cuando todos los valores son iguales. Tolera nulos.
 */
private fun computeMinMaxMarkers(values: List<Double?>): List<String> {
    val nonNulls = values.filterNotNull()
    if (nonNulls.size < 2) return List(values.size) { "" }
    val max = nonNulls.maxOrNull() ?: return List(values.size) { "" }
    val min = nonNulls.minOrNull() ?: return List(values.size) { "" }
    if (max == min) return List(values.size) { "" }

    val hasSingleMax = nonNulls.count { it == max } == 1
    val hasSingleMin = nonNulls.count { it == min } == 1

    return values.map { v ->
        when {
            v == null -> ""
            hasSingleMax && v == max -> "▲ "
            hasSingleMin && v == min -> "▼ "
            else -> ""
        }
    }
}

@Composable
fun ActuatorComparisonTable(
    actuators: List<ActuatorDto>
) {
    val context = LocalContext.current
    val scrollState = rememberScrollState()
    val hasThreePhase = actuators.any {
        it.phaseType.contains("3") ||
        it.singleTorqueNm != null ||
        (it.modulatingTorqueNm == null && it.onOffTorqueNm != null)
    }

    val onOffTorqueValues = actuators.map { (it.singleTorqueNm ?: it.onOffTorqueNm) }
    val onOffMarkers = computeMinMaxMarkers(onOffTorqueValues)

    val modTorqueValues = actuators.map { if (it.phaseType.contains("3") || it.singleTorqueNm != null) null else it.modulatingTorqueNm }
    val modMarkers = computeMinMaxMarkers(modTorqueValues)

    val speed60Values = actuators.map { it.speed60HzSec ?: it.speedDcOrFixedSec }
    val speed60Markers = computeMinMaxMarkers(speed60Values)

    val powerValues = actuators.map { it.motorPowerWatts?.toDouble() }
    val powerMarkers = computeMinMaxMarkers(powerValues)

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Header bar
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
                    Surface(
                        color = KonectoTheme.semantics.accentContainer,
                        shape = RoundedCornerShape(6.dp),
                        border = BorderStroke(1.dp, KonectoTheme.semantics.warningBorder)
                    ) {
                        Text(
                            text = "60 Hz | 50 Hz",
                            color = KonectoTheme.semantics.warningText,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                        )
                    }
                }
            }

            if (hasThreePhase) {
                Surface(
                    color = KonectoTheme.semantics.warningBg,
                    border = BorderStroke(1.dp, KonectoTheme.semantics.warningBorder),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = stringResource(R.string.card_single_torque_alert),
                        color = KonectoTheme.semantics.warningText,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.padding(horizontal = Spacing.m, vertical = 6.dp)
                    )
                }
            }

            HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)

            // Table content: Fixed Parameter Column on left, Horizontal Scroll on right
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(10.dp)
            ) {
                // 1. Columna de etiquetas FIJA
                Column(
                    modifier = Modifier
                        .width(115.dp)
                        .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                        .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(8.dp))
                        .padding(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Box(modifier = Modifier.height(28.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.table_col_part), fontWeight = FontWeight.Bold, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                    }
                    Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.table_col_enclosure), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(modifier = Modifier.height(28.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.table_col_power_supply), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.table_col_on_off_torque), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.table_col_mod_torque), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.table_col_duty), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.card_speed_label), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.table_col_fla_freq), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.table_col_lra_freq), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.card_power_label), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                        Text(stringResource(R.string.table_col_cert), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }

                Spacer(modifier = Modifier.width(6.dp))

                // 2. Columnas de actuadores con scroll horizontal
                Row(
                    modifier = Modifier
                        .weight(1f)
                        .horizontalScroll(scrollState),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    actuators.forEachIndexed { index, act ->
                        val isActThreePhase = act.phaseType.contains("3") ||
                            act.singleTorqueNm != null ||
                            (act.modulatingTorqueNm == null && act.onOffTorqueNm != null)

                        val speedStr = when {
                            act.speed60HzSec != null && act.speed50HzSec != null -> "${act.speed60HzSec}s | ${act.speed50HzSec}s"
                            act.speed60HzSec != null -> "${act.speed60HzSec}s (60Hz)"
                            act.speed50HzSec != null -> "${act.speed50HzSec}s (50Hz)"
                            act.speedDcOrFixedSec != null -> "${act.speedDcOrFixedSec}s"
                            else -> "—"
                        }

                        val flaStr = when {
                            act.fla60HzAmps != null && act.fla50HzAmps != null -> "${act.fla60HzAmps} | ${act.fla50HzAmps} A"
                            act.fla60HzAmps != null -> "${act.fla60HzAmps} A"
                            act.fla50HzAmps != null -> "${act.fla50HzAmps} A"
                            act.flaDcOrFixedAmps != null -> "${act.flaDcOrFixedAmps} A"
                            else -> "—"
                        }

                        val lraStr = when {
                            act.lra60HzAmps != null && act.lra50HzAmps != null -> "${act.lra60HzAmps} | ${act.lra50HzAmps} A"
                            act.lra60HzAmps != null -> "${act.lra60HzAmps} A"
                            act.lra50HzAmps != null -> "${act.lra50HzAmps} A"
                            act.lraDcOrFixedAmps != null -> "${act.lraDcOrFixedAmps} A"
                            else -> "—"
                        }

                        Column(
                            modifier = Modifier
                                .width(150.dp)
                                .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(8.dp))
                                .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(8.dp))
                                .padding(8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Box(modifier = Modifier.height(28.dp), contentAlignment = Alignment.CenterStart) {
                                Text(
                                    text = act.basePartNumber,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 11.sp,
                                    color = KonectoTheme.semantics.accentText,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                            Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                                Text(act.enclosureType, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface, maxLines = 1)
                            }
                            Box(modifier = Modifier.height(28.dp), contentAlignment = Alignment.CenterStart) {
                                Text(act.powerSupply, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface, maxLines = 2, lineHeight = 13.sp)
                            }
                            Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                                val rawTorque = (act.singleTorqueNm ?: act.onOffTorqueNm)
                                val marker = onOffMarkers.getOrElse(index) { "" }
                                val isMarked = marker.isNotEmpty()
                                val onOff = if (isActThreePhase) {
                                    if (rawTorque != null) "${marker}${rawTorque.toInt()} Nm" else "—"
                                } else {
                                    if (act.onOffTorqueNm != null) "${marker}${act.onOffTorqueNm.toInt()} Nm" else "—"
                                }
                                Text(
                                    text = onOff,
                                    fontSize = 11.sp,
                                    fontWeight = if (isMarked) FontWeight.Bold else FontWeight.SemiBold,
                                    color = if (isMarked) KonectoTheme.semantics.accentText else MaterialTheme.colorScheme.onSurface
                                )
                            }
                            Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                                val marker = modMarkers.getOrElse(index) { "" }
                                val isMarked = marker.isNotEmpty()
                                val mod = if (isActThreePhase) "—" else if (act.modulatingTorqueNm != null) "${marker}${act.modulatingTorqueNm.toInt()} Nm" else "—"
                                Text(
                                    text = mod,
                                    fontSize = 11.sp,
                                    fontWeight = if (isMarked) FontWeight.Bold else FontWeight.SemiBold,
                                    color = if (isMarked) KonectoTheme.semantics.accentText else MaterialTheme.colorScheme.onSurface
                                )
                            }
                            Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                                val duty = if (isActThreePhase) "70% (S4)" else "${act.onOffDutyCyclePct ?: "—"}% / ${act.modulatingDutyCyclePct ?: "—"}%"
                                Text(duty, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface)
                            }
                            Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                                val marker = speed60Markers.getOrElse(index) { "" }
                                val isMarked = marker.isNotEmpty()
                                Text(
                                    text = if (isMarked && speedStr != "—") "${marker}$speedStr" else speedStr,
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = if (isMarked) FontWeight.Bold else FontWeight.SemiBold,
                                    color = if (isMarked) KonectoTheme.semantics.accentText else MaterialTheme.colorScheme.onSurface
                                )
                            }
                            Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                                Text(flaStr, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
                            }
                            Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                                Text(lraStr, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
                            }
                            Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                                val marker = powerMarkers.getOrElse(index) { "" }
                                val isMarked = marker.isNotEmpty()
                                Text(
                                    text = if (act.motorPowerWatts != null) "${marker}${act.motorPowerWatts} W" else "—",
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = if (isMarked) FontWeight.Bold else FontWeight.Normal,
                                    color = if (isMarked) KonectoTheme.semantics.accentText else MaterialTheme.colorScheme.onSurface
                                )
                            }
                            Box(modifier = Modifier.height(24.dp), contentAlignment = Alignment.CenterStart) {
                                Text(
                                    text = if (act.csaCertified) "✓ CSA" else "⚠ No CSA",
                                    fontSize = 11.sp,
                                    color = if (act.csaCertified) KonectoTheme.semantics.successText else KonectoTheme.semantics.warningText,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                        }
                    }
                }
            }

            HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline)

            // Pie de tabla con leyenda de mejor valor y botón de copiado
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = Spacing.m, vertical = Spacing.xs),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = stringResource(R.string.comparison_best_legend),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                OutlinedButton(
                    onClick = { copyComparisonTableToClipboard(context, actuators) },
                    shape = RoundedCornerShape(8.dp),
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.onSurface),
                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.ContentCopy,
                        contentDescription = null,
                        modifier = Modifier.size(13.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = stringResource(R.string.comparison_copy_btn),
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

/**
 * Vista de Recomendación con Ranking, Pros/Contras, Restricciones y Despliegue de Ficha
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun RecommendationListView(
    recommendation: RecommendationPayload,
    actuators: List<ActuatorDto> = emptyList(),
    onOpenFullDatasheet: (ActuatorDto) -> Unit = {}
) {
    var expandedPartNumber by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.s)
    ) {
        // Banner de restricciones (Hard & Relaxed Constraints)
        Card(
            shape = RoundedCornerShape(14.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(
                modifier = Modifier.padding(Spacing.m),
                verticalArrangement = Arrangement.spacedBy(Spacing.xs)
            ) {
                Text(
                    text = stringResource(R.string.recommendation_title),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    letterSpacing = 1.sp,
                    fontWeight = FontWeight.Bold
                )

                if (recommendation.hardConstraints.isNotEmpty()) {
                    Text(
                        text = stringResource(R.string.recommendation_hard_constraints),
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    FlowRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        recommendation.hardConstraints.forEach { constraint ->
                            Surface(
                                color = MaterialTheme.colorScheme.surfaceVariant,
                                shape = RoundedCornerShape(6.dp),
                                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    Text("🔒", fontSize = 11.sp)
                                    Text(
                                        text = constraint,
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurface
                                    )
                                }
                            }
                        }
                    }
                }

                if (recommendation.relaxedConstraints.isNotEmpty()) {
                    Text(
                        text = stringResource(R.string.recommendation_relaxed_constraints),
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Bold,
                        color = KonectoTheme.semantics.warningText
                    )
                    FlowRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        recommendation.relaxedConstraints.forEach { relaxed ->
                            Surface(
                                color = KonectoTheme.semantics.warningBg,
                                shape = RoundedCornerShape(6.dp),
                                border = BorderStroke(1.dp, KonectoTheme.semantics.warningBorder)
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    Text("⚡", fontSize = 11.sp)
                                    Text(
                                        text = relaxed,
                                        style = MaterialTheme.typography.labelSmall,
                                        color = KonectoTheme.semantics.warningText,
                                        fontWeight = FontWeight.Medium
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        // Caso NO_MATCH_HARD_CONSTRAINTS (ranking vacío)
        if (recommendation.ranking.isEmpty()) {
            Surface(
                color = KonectoTheme.semantics.errorBg,
                shape = RoundedCornerShape(12.dp),
                border = BorderStroke(1.dp, KonectoTheme.semantics.errorBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(Spacing.m),
                    verticalArrangement = Arrangement.spacedBy(Spacing.xs)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
                    ) {
                        Text("⚠️", fontSize = 18.sp)
                        Text(
                            text = stringResource(R.string.recommendation_no_match),
                            style = MaterialTheme.typography.titleSmall,
                            color = KonectoTheme.semantics.errorText,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    if (recommendation.hardConstraints.isNotEmpty()) {
                        Text(
                            text = stringResource(R.string.recommendation_failed_constraints),
                            style = MaterialTheme.typography.bodySmall,
                            color = KonectoTheme.semantics.errorText
                        )
                        recommendation.hardConstraints.forEach { constraint ->
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(6.dp),
                                modifier = Modifier.padding(start = 8.dp)
                            ) {
                                Text("✗", color = KonectoTheme.semantics.errorText, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                Text(
                                    text = constraint,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurface
                                )
                            }
                        }
                    }
                }
            }
        } else {
            // Lista de candidatos rankeados
            recommendation.ranking.forEachIndexed { index, item ->
                val isExpanded = expandedPartNumber == item.partNumber
                val matchingActuator = actuators.find { it.basePartNumber == item.partNumber }

                Card(
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    border = BorderStroke(
                        1.dp,
                        if (index == 0) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.outline
                    ),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier.padding(Spacing.m),
                        verticalArrangement = Arrangement.spacedBy(Spacing.s)
                    ) {
                        // Cabecera del candidato
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
                            ) {
                                Surface(
                                    color = if (index == 0) KonectoTheme.semantics.accentContainer else MaterialTheme.colorScheme.surfaceVariant,
                                    shape = RoundedCornerShape(6.dp),
                                    border = BorderStroke(1.dp, if (index == 0) KonectoTheme.semantics.warningBorder else MaterialTheme.colorScheme.outline)
                                ) {
                                    Text(
                                        text = "#${index + 1}",
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = if (index == 0) KonectoTheme.semantics.accentText else MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                    )
                                }
                                Text(
                                    text = item.partNumber,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 13.sp,
                                    color = MaterialTheme.colorScheme.onSurface
                                )
                            }

                            // Score gauge / pill (0 - 100)
                            val scorePct = (item.score * 100).toInt().coerceIn(0, 100)
                            Surface(
                                color = if (scorePct >= 75) KonectoTheme.semantics.successBg else KonectoTheme.semantics.warningBg,
                                shape = RoundedCornerShape(12.dp),
                                border = BorderStroke(1.dp, if (scorePct >= 75) KonectoTheme.semantics.successBorder else KonectoTheme.semantics.warningBorder)
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    Text(
                                        text = "$scorePct%",
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 12.sp,
                                        color = if (scorePct >= 75) KonectoTheme.semantics.successText else KonectoTheme.semantics.warningText,
                                        fontFamily = FontFamily.Monospace
                                    )
                                    Text(
                                        text = stringResource(R.string.recommendation_score),
                                        fontSize = 10.sp,
                                        color = if (scorePct >= 75) KonectoTheme.semantics.successText else KonectoTheme.semantics.warningText
                                    )
                                }
                            }
                        }

                        // Pros (Why)
                        if (item.why.isNotEmpty()) {
                            Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Text(
                                    text = stringResource(R.string.recommendation_why),
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = KonectoTheme.semantics.successText
                                )
                                item.why.forEach { pro ->
                                    Row(
                                        verticalAlignment = Alignment.Top,
                                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                                        modifier = Modifier.padding(start = 4.dp)
                                    ) {
                                        Text("✓", color = KonectoTheme.semantics.successText, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                        Text(
                                            text = pro,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurface
                                        )
                                    }
                                }
                            }
                        }

                        // Cons (Why Not)
                        if (item.whyNot.isNotEmpty()) {
                            Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Text(
                                    text = stringResource(R.string.recommendation_why_not),
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = KonectoTheme.semantics.errorText
                                )
                                item.whyNot.forEach { con ->
                                    Row(
                                        verticalAlignment = Alignment.Top,
                                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                                        modifier = Modifier.padding(start = 4.dp)
                                    ) {
                                        Text("✗", color = KonectoTheme.semantics.errorText, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                        Text(
                                            text = con,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                }
                            }
                        }

                        // Botón Desplegar Ficha Técnica
                        OutlinedButton(
                            onClick = {
                                expandedPartNumber = if (isExpanded) null else item.partNumber
                            },
                            shape = RoundedCornerShape(8.dp),
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = MaterialTheme.colorScheme.onSurface
                            ),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = if (isExpanded) stringResource(R.string.recommendation_hide_spec) else stringResource(R.string.recommendation_view_spec),
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }

                        // Ficha técnica desplegable (usando actuators si disponible)
                        if (isExpanded) {
                            HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline)
                            if (matchingActuator != null) {
                                SingleActuatorSpecCard(
                                    actuator = matchingActuator,
                                    onOpenFullDatasheet = onOpenFullDatasheet
                                )
                            } else {
                                Text(
                                    text = "${stringResource(R.string.table_col_part)}: ${item.partNumber}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

/**
 * Vista de Aclaración (CLARIFICATION) con botones tipo chip grandes
 */
@Composable
fun ClarificationView(
    clarification: ClarificationPayload,
    onSelectOption: (String) -> Unit
) {
    var selectedValue by remember { mutableStateOf<String?>(null) }
    val haptic = LocalHapticFeedback.current

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, KonectoTheme.semantics.accent.copy(alpha = 0.6f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(Spacing.m),
            verticalArrangement = Arrangement.spacedBy(Spacing.s)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
            ) {
                Text("💬", fontSize = 16.sp)
                Text(
                    text = stringResource(R.string.clarification_title),
                    style = MaterialTheme.typography.labelSmall,
                    color = KonectoTheme.semantics.accentText,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp
                )
            }

            Text(
                text = clarification.question,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )

            // Opciones interactivas grandes
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                clarification.options.forEach { option ->
                    val isChosen = selectedValue == option.value
                    val isDisabled = selectedValue != null && !isChosen

                    Surface(
                        color = if (isChosen) KonectoTheme.semantics.accentContainer else MaterialTheme.colorScheme.surfaceVariant,
                        shape = RoundedCornerShape(10.dp),
                        border = BorderStroke(
                            1.dp,
                            if (isChosen) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.outline
                        ),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(10.dp))
                            .clickable(enabled = selectedValue == null) {
                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                selectedValue = option.value
                                onSelectOption(option.value)
                            }
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = Spacing.m, vertical = 12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = option.label,
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = if (isChosen) FontWeight.Bold else FontWeight.Medium,
                                color = if (isDisabled) MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f)
                                        else if (isChosen) KonectoTheme.semantics.accentText
                                        else MaterialTheme.colorScheme.onSurface
                            )
                            if (isChosen) {
                                Text(
                                    text = "✓",
                                    color = KonectoTheme.semantics.accentText,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 14.sp
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

/**
 * Fila de Chips de Preguntas Sugeridas (SUGGESTED_FOLLOWUPS)
 */
@Composable
fun SuggestedFollowupRow(
    followups: List<SuggestedFollowup>,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    if (followups.isEmpty()) return
    val haptic = LocalHapticFeedback.current
    val limited = followups.take(3)

    var visible by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        visible = true
    }

    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(animationSpec = tween(400)) + slideInVertically(
            initialOffsetY = { 20 },
            animationSpec = spring(dampingRatio = Spring.DampingRatioLowBouncy)
        ),
        modifier = modifier.padding(top = Spacing.xs)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
        ) {
            limited.forEach { followup ->
                Surface(
                    color = MaterialTheme.colorScheme.surface,
                    shape = RoundedCornerShape(20.dp),
                    border = BorderStroke(1.dp, KonectoTheme.semantics.accent.copy(alpha = 0.7f)),
                    modifier = Modifier
                        .clip(RoundedCornerShape(20.dp))
                        .clickable {
                            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                            onSelect(followup.query)
                        }
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Text(
                            text = followup.label,
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = KonectoTheme.semantics.accentText
                        )
                        Text(
                            text = "↗",
                            fontSize = 11.sp,
                            color = KonectoTheme.semantics.accentText,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
        }
    }
}

/**
 * Insignia de Verificación discreta
 */
@Composable
fun VerificationBadge(
    verification: Verification?,
    modifier: Modifier = Modifier
) {
    if (verification == null) return
    when (verification.status) {
        "verified" -> {
            Surface(
                color = KonectoTheme.semantics.successBg,
                shape = RoundedCornerShape(12.dp),
                border = BorderStroke(1.dp, KonectoTheme.semantics.successBorder),
                modifier = modifier.padding(bottom = 4.dp)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text(
                        text = "✓",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = KonectoTheme.semantics.successText
                    )
                    Text(
                        text = stringResource(R.string.verification_verified),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = KonectoTheme.semantics.successText
                    )
                }
            }
        }
        "fallback_template" -> {
            Surface(
                color = KonectoTheme.semantics.warningBg,
                shape = RoundedCornerShape(12.dp),
                border = BorderStroke(1.dp, KonectoTheme.semantics.warningBorder),
                modifier = modifier.padding(bottom = 4.dp)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text(text = "⚠️", fontSize = 10.sp)
                    Text(
                        text = stringResource(R.string.verification_fallback),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        color = KonectoTheme.semantics.warningText
                    )
                }
            }
        }
        else -> {
            // "unverified" -> sin insignia
        }
    }
}

/**
 * Lista de Alertas del Sistema con severidad y botón de reintento
 * - Códigos internos (DUTY_CYCLE_INFO, HAZARDOUS_..., LLM_UNAVAILABLE) NUNCA se muestran al usuario
 * - Muestra alert.title o fallback legible por código desde strings es/en
 * - Errores sanitizados sin códigos HTTP, LLM ni nombres de proveedores
 * - Botón de reintento con contraste AA certificado en modo oscuro y claro
 */
@Composable
fun UIAlertsView(
    alerts: List<UIAlert>,
    onRetry: () -> Unit = {}
) {
    if (alerts.isEmpty()) return
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.xs)
    ) {
        alerts.forEach { alert ->
            val isError = alert.severity.equals("error", ignoreCase = true)
            val isWarning = alert.severity.equals("warning", ignoreCase = true)

            val bgColor = when {
                isError -> KonectoTheme.semantics.errorBg
                isWarning -> KonectoTheme.semantics.warningBg
                else -> MaterialTheme.colorScheme.surfaceVariant
            }
            val borderColor = when {
                isError -> KonectoTheme.semantics.errorBorder
                isWarning -> KonectoTheme.semantics.warningBorder
                else -> MaterialTheme.colorScheme.outline
            }
            val textColor = when {
                isError -> KonectoTheme.semantics.errorText
                isWarning -> KonectoTheme.semantics.warningText
                else -> MaterialTheme.colorScheme.onSurface
            }
            val icon = when {
                isError -> "🛑"
                isWarning -> "⚠️"
                else -> "ℹ️"
            }

            // Título amigable para el usuario: NUNCA mostrar códigos técnicos internos
            val titleText = when {
                alert.title.isNotBlank() -> alert.title
                alert.code.equals("DUTY_CYCLE_INFO", ignoreCase = true) -> stringResource(R.string.alert_title_duty_cycle)
                alert.code.equals("HAZARDOUS_NEEDS_EXPLOSIONPROOF", ignoreCase = true) -> stringResource(R.string.alert_title_hazardous)
                alert.code.equals("SERVICE_UNAVAILABLE", ignoreCase = true) ||
                    alert.code.equals("LLM_UNAVAILABLE", ignoreCase = true) ||
                    alert.code.contains("UNAVAILABLE", ignoreCase = true) -> stringResource(R.string.alert_title_service_unavailable)
                alert.code.equals("SAFETY_FACTOR_APPLIED", ignoreCase = true) -> stringResource(R.string.alert_title_safety_factor)
                alert.code.equals("NO_MATCH_HARD_CONSTRAINTS", ignoreCase = true) -> stringResource(R.string.alert_title_no_match)
                alert.code.equals("SINGLE_TORQUE_RATING", ignoreCase = true) -> stringResource(R.string.alert_title_single_torque)
                else -> stringResource(R.string.alert_title_generic)
            }

            // Muestra el mensaje localizado que envía el backend sin ocultar por contener "LLM" u "OpenRouter"
            val displayMessage = if (alert.message.isNotBlank()) {
                alert.message
            } else {
                stringResource(R.string.error_service_unavailable_clean_msg)
            }

            Surface(
                color = bgColor,
                shape = RoundedCornerShape(10.dp),
                border = BorderStroke(1.dp, borderColor),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(Spacing.s),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
                ) {
                    Text(text = icon, fontSize = 16.sp)
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = titleText,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = textColor
                        )
                        Text(
                            text = displayMessage,
                            style = MaterialTheme.typography.bodySmall,
                            color = textColor
                        )
                    }
                    if (isError) {
                        Button(
                            onClick = onRetry,
                            colors = ButtonDefaults.buttonColors(
                                containerColor = MaterialTheme.colorScheme.error,
                                contentColor = MaterialTheme.colorScheme.onError
                            ),
                            shape = RoundedCornerShape(6.dp),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            Text(
                                text = stringResource(R.string.retry),
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onError,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        }
    }
}

/**
 * Ficha Técnica Completa desplegada en ModalBottomSheet
 * - Agrupa especificaciones mecánicas, eléctricas (60 y 50 Hz) y certificaciones
 * - Fuente: Series 76 electric data, pág. N si sourcePage != null
 * - Acciones de Copiar y Compartir completas
 * - La app nunca inventa ni calcula valores faltantes (muestra "—")
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ActuatorFullDatasheetSheet(
    actuator: ActuatorDto,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current

    val isThreePhase = remember(actuator) {
        actuator.phaseType.contains("3") ||
        actuator.singleTorqueNm != null ||
        (actuator.modulatingTorqueNm == null && actuator.onOffTorqueNm != null)
    }

    fun buildFullDatasheetText(): String {
        val sb = StringBuilder()
        sb.appendLine("KONECTO SERIES 76 - FULL TECHNICAL DATASHEET")
        sb.appendLine("Part Number: ${actuator.basePartNumber}")
        sb.appendLine("Frame Size: ${actuator.frameSize}")
        sb.appendLine("Enclosure: ${actuator.enclosureType}")
        sb.appendLine("Phase Type: ${actuator.phaseType}")
        sb.appendLine("Power Supply: ${actuator.powerSupply}")
        if (isThreePhase) {
            val torque = actuator.singleTorqueNm ?: actuator.onOffTorqueNm
            val torqueInLbs = actuator.singleTorqueInLbs ?: actuator.onOffTorqueInLbs
            sb.appendLine("Output Torque: ${torque?.toInt() ?: "—"} Nm (${torqueInLbs?.toInt() ?: "—"} in-lbs)")
            sb.appendLine("Duty Rating: S4 70%")
        } else {
            sb.appendLine("On/Off Torque: ${actuator.onOffTorqueNm?.toInt() ?: "—"} Nm (${actuator.onOffTorqueInLbs?.toInt() ?: "—"} in-lbs)")
            sb.appendLine("Modulating Torque: ${actuator.modulatingTorqueNm?.toInt() ?: "—"} Nm (${actuator.modulatingTorqueInLbs?.toInt() ?: "—"} in-lbs)")
            sb.appendLine("On/Off Duty Cycle: ${actuator.onOffDutyCyclePct ?: "—"}%")
            sb.appendLine("Modulating Duty Cycle: ${actuator.modulatingDutyCyclePct ?: "—"}%")
        }
        sb.appendLine("Cycles / Hour: ${actuator.cyclesPerHour ?: "—"}")
        sb.appendLine("Starts / Hour: ${actuator.startsPerHour ?: "—"}")
        sb.appendLine("Speed 90°: 60Hz = ${actuator.speed60HzSec ?: actuator.speedDcOrFixedSec ?: "—"}s | 50Hz = ${actuator.speed50HzSec ?: "—"}s")
        sb.appendLine("FLA: 60Hz = ${actuator.fla60HzAmps ?: actuator.flaDcOrFixedAmps ?: "—"}A | 50Hz = ${actuator.fla50HzAmps ?: "—"}A")
        sb.appendLine("LRA: 60Hz = ${actuator.lra60HzAmps ?: actuator.lraDcOrFixedAmps ?: "—"}A | 50Hz = ${actuator.lra50HzAmps ?: "—"}A")
        sb.appendLine("Motor Power: ${actuator.motorPowerWatts ?: "—"} W")
        sb.appendLine("Certification: ${if (actuator.csaCertified) "CSA Certified (UL 429 / CSA C22.2 No. 139)" else "Non-CSA"}")
        if (actuator.sourcePage != null) {
            sb.appendLine("Source: Series 76 electric data, p. ${actuator.sourcePage}")
        }
        return sb.toString()
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        dragHandle = { BottomSheetDefaults.DragHandle() },
        shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = Spacing.m)
                .padding(bottom = Spacing.l)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(Spacing.s)
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = stringResource(R.string.datasheet_sheet_title),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        text = actuator.basePartNumber,
                        fontFamily = FontFamily.Monospace,
                        style = MaterialTheme.typography.bodyMedium,
                        color = KonectoTheme.semantics.accentText,
                        fontWeight = FontWeight.Bold
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(Spacing.xs)) {
                    IconButton(
                        onClick = {
                            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                            clipboard.setPrimaryClip(ClipData.newPlainText("Series 76 Datasheet", buildFullDatasheetText()))
                            Toast.makeText(context, context.getString(R.string.datasheet_copied_toast), Toast.LENGTH_SHORT).show()
                        }
                    ) {
                        Icon(
                            imageVector = Icons.Default.ContentCopy,
                            contentDescription = stringResource(R.string.card_copy_action),
                            tint = KonectoTheme.semantics.accent
                        )
                    }
                    IconButton(
                        onClick = {
                            haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                            val sendIntent = Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_SUBJECT, "Series 76 - ${actuator.basePartNumber} Datasheet")
                                putExtra(Intent.EXTRA_TEXT, buildFullDatasheetText())
                            }
                            context.startActivity(Intent.createChooser(sendIntent, context.getString(R.string.card_share_title)))
                        }
                    ) {
                        Icon(
                            imageVector = Icons.Default.Share,
                            contentDescription = stringResource(R.string.card_share_action),
                            tint = KonectoTheme.semantics.accent
                        )
                    }
                }
            }

            HorizontalDivider(color = MaterialTheme.colorScheme.outline)

            // Grupo 1: Especificaciones Mecánicas
            Text(
                text = stringResource(R.string.datasheet_group_mechanical),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(10.dp),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(Spacing.s),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    DatasheetMetricRow(stringResource(R.string.datasheet_field_frame), "Frame ${actuator.frameSize}")
                    DatasheetMetricRow(stringResource(R.string.datasheet_field_enclosure), actuator.enclosureType)
                    DatasheetMetricRow(stringResource(R.string.datasheet_field_phase), actuator.phaseType)
                    if (isThreePhase) {
                        val tNm = actuator.singleTorqueNm ?: actuator.onOffTorqueNm
                        val tLbs = actuator.singleTorqueInLbs ?: actuator.onOffTorqueInLbs
                        DatasheetMetricRow(
                            stringResource(R.string.card_output_torque),
                            if (tNm != null) "${tNm.toInt()} Nm (${tLbs?.toInt() ?: "—"} in-lbs)" else "—"
                        )
                        DatasheetMetricRow(stringResource(R.string.datasheet_field_duty_rating), "70% (S4)")
                    } else {
                        DatasheetMetricRow(
                            stringResource(R.string.datasheet_field_on_off_torque),
                            if (actuator.onOffTorqueNm != null) "${actuator.onOffTorqueNm.toInt()} Nm (${actuator.onOffTorqueInLbs?.toInt() ?: "—"} in-lbs)" else "—"
                        )
                        DatasheetMetricRow(
                            stringResource(R.string.datasheet_field_mod_torque),
                            if (actuator.modulatingTorqueNm != null) "${actuator.modulatingTorqueNm.toInt()} Nm (${actuator.modulatingTorqueInLbs?.toInt() ?: "—"} in-lbs)" else "—"
                        )
                        DatasheetMetricRow(stringResource(R.string.datasheet_field_on_off_duty), if (actuator.onOffDutyCyclePct != null) "${actuator.onOffDutyCyclePct}%" else "—")
                        DatasheetMetricRow(stringResource(R.string.datasheet_field_mod_duty), if (actuator.modulatingDutyCyclePct != null) "${actuator.modulatingDutyCyclePct}%" else "—")
                    }
                    DatasheetMetricRow(stringResource(R.string.datasheet_field_cycles_hour), if (actuator.cyclesPerHour != null) "${actuator.cyclesPerHour} ciclos/h" else "—")
                    DatasheetMetricRow(stringResource(R.string.datasheet_field_starts_hour), if (actuator.startsPerHour != null) "${actuator.startsPerHour} arranques/h" else "—")
                }
            }

            // Grupo 2: Especificaciones Eléctricas (Side-by-Side 60 Hz | 50 Hz)
            Text(
                text = stringResource(R.string.datasheet_group_electrical),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(10.dp),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(Spacing.s),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    DatasheetMetricRow(stringResource(R.string.datasheet_field_power_supply), actuator.powerSupply)
                    DatasheetMetricRow(stringResource(R.string.datasheet_field_motor_power), if (actuator.motorPowerWatts != null) "${actuator.motorPowerWatts} W" else "—")
                    DatasheetMetricRow(
                        stringResource(R.string.card_speed_metric),
                        "60Hz: ${actuator.speed60HzSec ?: actuator.speedDcOrFixedSec ?: "—"}s | 50Hz: ${actuator.speed50HzSec ?: "—"}s"
                    )
                    DatasheetMetricRow(
                        stringResource(R.string.datasheet_field_fla),
                        "60Hz: ${actuator.fla60HzAmps ?: actuator.flaDcOrFixedAmps ?: "—"}A | 50Hz: ${actuator.fla50HzAmps ?: "—"}A"
                    )
                    DatasheetMetricRow(
                        stringResource(R.string.datasheet_field_lra),
                        "60Hz: ${actuator.lra60HzAmps ?: actuator.lraDcOrFixedAmps ?: "—"}A | 50Hz: ${actuator.lra50HzAmps ?: "—"}A"
                    )
                }
            }

            // Grupo 3: Normativas y Certificaciones
            Text(
                text = stringResource(R.string.datasheet_group_certifications),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(10.dp),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(Spacing.s),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    DatasheetMetricRow(
                        stringResource(R.string.datasheet_field_csa),
                        if (actuator.csaCertified) "✓ Certified (UL 429 / CSA C22.2 No. 139)" else "Non-CSA"
                    )
                    DatasheetMetricRow(stringResource(R.string.datasheet_field_enclosure), actuator.enclosureType)
                }
            }

            // Fuente oficial
            Surface(
                color = KonectoTheme.semantics.accentContainer.copy(alpha = 0.5f),
                shape = RoundedCornerShape(8.dp),
                border = BorderStroke(1.dp, KonectoTheme.semantics.warningBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = if (actuator.sourcePage != null) {
                        stringResource(R.string.datasheet_source_page, actuator.sourcePage)
                    } else {
                        "Fuente: Series 76 electric data"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = KonectoTheme.semantics.accentText,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.padding(Spacing.s)
                )
            }
        }
    }
}

@Composable
private fun DatasheetMetricRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold,
            fontFamily = FontFamily.Monospace,
            color = MaterialTheme.colorScheme.onSurface
        )
    }
}
