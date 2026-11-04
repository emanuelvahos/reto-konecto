package io.konecto.series76.ui.login

import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.Settings
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.R
import io.konecto.series76.data.ApiClient
import io.konecto.series76.ui.MainViewModel
import io.konecto.series76.ui.components.CleanInputField
import io.konecto.series76.ui.components.ConnectionDialog
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing
import io.konecto.series76.ui.theme.ThemeController

@Composable
fun ActuatorGaugeEmblem(
    modifier: Modifier = Modifier,
    reduceMotion: Boolean = false
) {
    val infiniteTransition = rememberInfiniteTransition(label = "gaugeSweep")
    val sweepPct by if (reduceMotion) {
        remember { mutableStateOf(45f) }
    } else {
        infiniteTransition.animateFloat(
            initialValue = 20f,
            targetValue = 75f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 6000, easing = FastOutSlowInEasing),
                repeatMode = RepeatMode.Reverse
            ),
            label = "needleAngle"
        )
    }

    val accentColor = KonectoTheme.semantics.accent
    val trackColor = KonectoTheme.semantics.gaugeTrack
    val outlineColor = MaterialTheme.colorScheme.outline

    Canvas(modifier = modifier.size(68.dp)) {
        val center = Offset(size.width / 2f, size.height / 2f)
        val radius = size.minDimension / 2f - 4.dp.toPx()

        // Anillo exterior del chasis
        drawCircle(
            color = trackColor.copy(alpha = 0.5f),
            radius = radius,
            center = center,
            style = Stroke(width = 2.dp.toPx())
        )

        // Marcas radiales del cuadrante de instrumentación
        for (i in 0..12) {
            val angleDeg = 135f + (270f / 12f) * i
            val rad = Math.toRadians(angleDeg.toDouble())
            val isMajor = i % 3 == 0
            val tickLen = if (isMajor) 7.dp.toPx() else 4.dp.toPx()
            val startX = (center.x + (radius - tickLen) * Math.cos(rad)).toFloat()
            val startY = (center.y + (radius - tickLen) * Math.sin(rad)).toFloat()
            val endX = (center.x + radius * Math.cos(rad)).toFloat()
            val endY = (center.y + radius * Math.sin(rad)).toFloat()
            drawLine(
                color = if (isMajor) accentColor else outlineColor,
                start = Offset(startX, startY),
                end = Offset(endX, endY),
                strokeWidth = if (isMajor) 2.dp.toPx() else 1.dp.toPx()
            )
        }

        // Arco activo iluminado
        drawArc(
            color = accentColor,
            startAngle = 135f,
            sweepAngle = 270f * (sweepPct / 100f),
            useCenter = false,
            style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round)
        )

        // Núcleo central del actuador
        drawCircle(color = accentColor, radius = 4.dp.toPx(), center = center)

        // Aguja indicadora
        val needleRad = Math.toRadians((135f + 270f * (sweepPct / 100f)).toDouble())
        val needleLen = radius - 7.dp.toPx()
        val needleEndX = (center.x + needleLen * Math.cos(needleRad)).toFloat()
        val needleEndY = (center.y + needleLen * Math.sin(needleRad)).toFloat()
        drawLine(
            color = accentColor,
            start = center,
            end = Offset(needleEndX, needleEndY),
            strokeWidth = 2.dp.toPx(),
            cap = StrokeCap.Round
        )
    }
}

@Composable
fun LoginScreen(vm: MainViewModel) {
    val context = LocalContext.current
    var email by remember { mutableStateOf("engineer@konecto.io") }
    var password by remember { mutableStateOf("Konecto2026!") }
    var showServerDialog by remember { mutableStateOf(false) }

    val bgGradient = if (ThemeController.isDarkTheme) {
        Brush.verticalGradient(
            listOf(
                Color(0xFF070B12),
                Color(0xFF0F172A),
                Color(0xFF141F36)
            )
        )
    } else {
        Brush.verticalGradient(
            listOf(
                Color(0xFFE2E8F0),
                Color(0xFFF1F5F9),
                Color(0xFFFFFFFF)
            )
        )
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(bgGradient)
            .padding(Spacing.l),
        contentAlignment = Alignment.Center
    ) {
        Card(
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            modifier = Modifier
                .fillMaxWidth()
                .border(
                    1.dp,
                    KonectoTheme.semantics.accent.copy(alpha = 0.45f),
                    RoundedCornerShape(16.dp)
                )
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(Spacing.xl),
                verticalArrangement = Arrangement.spacedBy(Spacing.m)
            ) {
                // Header con emblema de medidor y botones de acción
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    ActuatorGaugeEmblem()

                    Column(
                        modifier = Modifier.weight(1f).padding(horizontal = Spacing.s),
                        verticalArrangement = Arrangement.spacedBy(2.dp)
                    ) {
                        Text(
                            text = stringResource(R.string.brand_name),
                            style = MaterialTheme.typography.labelMedium,
                            color = KonectoTheme.semantics.accent
                        )
                        Text(
                            text = stringResource(R.string.app_name),
                            style = MaterialTheme.typography.headlineSmall,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = stringResource(R.string.app_subtitle),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }

                    Row {
                        IconButton(onClick = { ThemeController.toggleTheme() }) {
                            Icon(
                                imageVector = if (ThemeController.isDarkTheme) Icons.Default.LightMode else Icons.Default.DarkMode,
                                contentDescription = "Toggle Theme",
                                tint = KonectoTheme.semantics.accent
                            )
                        }
                        IconButton(onClick = { showServerDialog = true }) {
                            Icon(
                                imageVector = Icons.Default.Settings,
                                contentDescription = stringResource(R.string.server_dialog_title),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }

                HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)

                // Indicador de servidor activo
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .clickable { showServerDialog = true }
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = Spacing.s, vertical = Spacing.xs),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "${stringResource(R.string.login_server_label)}: ${ApiClient.baseUrl}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = stringResource(R.string.login_change),
                            style = MaterialTheme.typography.labelSmall,
                            color = KonectoTheme.semantics.accent,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                CleanInputField(
                    label = stringResource(R.string.login_email_label),
                    value = email,
                    onValueChange = { email = it }
                )

                CleanInputField(
                    label = stringResource(R.string.login_password_label),
                    value = password,
                    onValueChange = { password = it },
                    isPassword = true
                )

                // Perfiles demo rápidos
                Column(verticalArrangement = Arrangement.spacedBy(Spacing.xs)) {
                    Text(
                        text = stringResource(R.string.login_quick_profiles),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        listOf(
                            Triple(stringResource(R.string.login_profile_engineer), "engineer@konecto.io", "Konecto2026!"),
                            Triple(stringResource(R.string.login_profile_supervisor), "supervisor@konecto.io", "Series76Pass!"),
                            Triple(stringResource(R.string.login_profile_evaluator), "admin@konecto.io", "AdminKonecto!")
                        ).forEach { (label, userEmail, userPass) ->
                            val isSelected = email == userEmail
                            Surface(
                                color = if (isSelected) KonectoTheme.semantics.accentContainer else MaterialTheme.colorScheme.surfaceVariant,
                                shape = RoundedCornerShape(8.dp),
                                border = BorderStroke(
                                    1.dp,
                                    if (isSelected) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.outline
                                ),
                                modifier = Modifier
                                    .clip(RoundedCornerShape(8.dp))
                                    .clickable {
                                        email = userEmail
                                        password = userPass
                                    }
                            ) {
                                Text(
                                    text = label,
                                    fontSize = 12.sp,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                    color = if (isSelected) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(horizontal = Spacing.s, vertical = Spacing.xxs)
                                )
                            }
                        }
                    }
                }

                if (vm.errorMessage != null) {
                    Surface(
                        color = KonectoTheme.semantics.errorBg,
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(1.dp, KonectoTheme.semantics.errorBorder),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = vm.errorMessage!!,
                            color = KonectoTheme.semantics.errorText,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(Spacing.s)
                        )
                    }
                }

                // Botón Sign In en acento ámbar industrial
                Button(
                    onClick = { vm.login(context, email, password) },
                    enabled = !vm.isLoading,
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = KonectoTheme.semantics.accent,
                        disabledContainerColor = MaterialTheme.colorScheme.outline
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp)
                ) {
                    if (vm.isLoading) {
                        CircularProgressIndicator(
                            color = KonectoTheme.semantics.onAccent,
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(
                            text = stringResource(R.string.login_sign_in),
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = KonectoTheme.semantics.onAccent,
                            letterSpacing = (-0.2).sp
                        )
                    }
                }

                TextButton(
                    onClick = { vm.continueWithoutLogin() },
                    modifier = Modifier.align(Alignment.CenterHorizontally)
                ) {
                    Text(
                        text = stringResource(R.string.login_single_user),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.titleSmall
                    )
                }
            }
        }
    }

    if (showServerDialog) {
        ConnectionDialog(
            initialUrl = ApiClient.baseUrl,
            onDismiss = { showServerDialog = false },
            onSaved = { newUrl ->
                showServerDialog = false
                vm.updateServerUrl(context, newUrl)
            }
        )
    }
}
