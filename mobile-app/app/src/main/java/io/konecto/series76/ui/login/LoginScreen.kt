package io.konecto.series76.ui.login

import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.text.font.FontFamily
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

/**
 * Emblema de Medidor de Actuador Industrial (120 dp) con presencia técnica,
 * animación de entrada con resorte (spring) y balanceo sutil de reposo.
 */
@Composable
fun ActuatorGaugeEmblem(
    modifier: Modifier = Modifier,
    reduceMotion: Boolean = false
) {
    val needleSweep = remember { Animatable(0f) }
    val infiniteTransition = rememberInfiniteTransition(label = "gaugeRestSway")
    val swayOffset by if (reduceMotion) {
        remember { mutableFloatStateOf(0f) }
    } else {
        infiniteTransition.animateFloat(
            initialValue = -2.2f,
            targetValue = 2.2f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 2800, easing = EaseInOutCubic),
                repeatMode = RepeatMode.Reverse
            ),
            label = "gaugeSway"
        )
    }

    LaunchedEffect(reduceMotion) {
        if (!reduceMotion) {
            needleSweep.animateTo(
                targetValue = 66f,
                animationSpec = spring(
                    dampingRatio = Spring.DampingRatioMediumBouncy,
                    stiffness = Spring.StiffnessLow
                )
            )
        } else {
            needleSweep.snapTo(66f)
        }
    }

    val currentSweepPct = if (needleSweep.isRunning) needleSweep.value else (needleSweep.value + swayOffset).coerceIn(0f, 100f)

    val accentColor = KonectoTheme.semantics.accent
    val trackColor = KonectoTheme.semantics.gaugeTrack
    val outlineColor = MaterialTheme.colorScheme.outline
    val chassisBg = MaterialTheme.colorScheme.surface

    Canvas(modifier = modifier.size(120.dp)) {
        val center = Offset(size.width / 2f, size.height / 2f)
        val outerRadius = size.minDimension / 2f - 6.dp.toPx()
        val innerRadius = outerRadius - 10.dp.toPx()

        // 1. Chasis circular exterior con bisel metálico
        drawCircle(
            color = chassisBg,
            radius = outerRadius,
            center = center
        )
        drawCircle(
            color = trackColor.copy(alpha = 0.7f),
            radius = outerRadius,
            center = center,
            style = Stroke(width = 3.dp.toPx())
        )
        drawCircle(
            color = outlineColor.copy(alpha = 0.5f),
            radius = innerRadius,
            center = center,
            style = Stroke(width = 1.dp.toPx())
        )

        // 2. Marcas radiales del cuadrante de instrumentación (16 divisiones)
        for (i in 0..16) {
            val angleDeg = 135f + (270f / 16f) * i
            val rad = Math.toRadians(angleDeg.toDouble())
            val isMajor = i % 4 == 0
            val tickLen = if (isMajor) 10.dp.toPx() else 5.dp.toPx()
            val startX = (center.x + (outerRadius - tickLen) * Math.cos(rad)).toFloat()
            val startY = (center.y + (outerRadius - tickLen) * Math.sin(rad)).toFloat()
            val endX = (center.x + (outerRadius - 2.dp.toPx()) * Math.cos(rad)).toFloat()
            val endY = (center.y + (outerRadius - 2.dp.toPx()) * Math.sin(rad)).toFloat()

            drawLine(
                color = if (isMajor) accentColor else outlineColor,
                start = Offset(startX, startY),
                end = Offset(endX, endY),
                strokeWidth = if (isMajor) 2.2.dp.toPx() else 1.dp.toPx()
            )
        }

        // 3. Arco de pista inactiva
        drawArc(
            color = trackColor.copy(alpha = 0.4f),
            startAngle = 135f,
            sweepAngle = 270f,
            useCenter = false,
            style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
        )

        // 4. Arco activo iluminado con degradado
        val sweepAngle = 270f * (currentSweepPct / 100f)
        drawArc(
            color = accentColor,
            startAngle = 135f,
            sweepAngle = sweepAngle,
            useCenter = false,
            style = Stroke(width = 4.5.dp.toPx(), cap = StrokeCap.Round)
        )

        // 5. Aguja indicadora mecánica con aguja cónica
        val needleRad = Math.toRadians((135f + sweepAngle).toDouble())
        val needleLen = outerRadius - 10.dp.toPx()
        val needleEndX = (center.x + needleLen * Math.cos(needleRad)).toFloat()
        val needleEndY = (center.y + needleLen * Math.sin(needleRad)).toFloat()

        // Contrapeso trasero
        val counterRad = needleRad + Math.PI
        val counterLen = 14.dp.toPx()
        val counterX = (center.x + counterLen * Math.cos(counterRad)).toFloat()
        val counterY = (center.y + counterLen * Math.sin(counterRad)).toFloat()

        drawLine(
            color = accentColor,
            start = Offset(counterX, counterY),
            end = Offset(needleEndX, needleEndY),
            strokeWidth = 2.5.dp.toPx(),
            cap = StrokeCap.Round
        )

        // 6. Núcleo concéntrico del actuador
        drawCircle(color = chassisBg, radius = 9.dp.toPx(), center = center)
        drawCircle(color = outlineColor, radius = 9.dp.toPx(), center = center, style = Stroke(width = 1.5.dp.toPx()))
        drawCircle(color = accentColor, radius = 5.dp.toPx(), center = center)
    }
}

@Composable
fun LoginScreen(vm: MainViewModel) {
    val context = LocalContext.current
    var email by remember { mutableStateOf("engineer@konecto.io") }
    var password by remember { mutableStateOf("Konecto2026!") }
    var showServerDialog by remember { mutableStateOf(false) }

    val isDark = ThemeController.isDarkTheme
    val accentColor = KonectoTheme.semantics.accent

    val bgGradient = if (isDark) {
        Brush.verticalGradient(
            listOf(
                Color(0xFF070B12),
                Color(0xFF0B101D),
                Color(0xFF111827)
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
    ) {
        // Cuadrícula técnica sutil y brillo radial en Canvas
        Canvas(modifier = Modifier.fillMaxSize()) {
            val glowCenter = Offset(size.width / 2f, size.height * 0.22f)
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        accentColor.copy(alpha = if (isDark) 0.16f else 0.10f),
                        Color.Transparent
                    ),
                    center = glowCenter,
                    radius = size.width * 0.70f
                ),
                radius = size.width * 0.70f,
                center = glowCenter
            )

            val gridStep = 32.dp.toPx()
            val gridColor = if (isDark) Color(0xFF1E293B).copy(alpha = 0.35f) else Color(0xFFCBD5E1).copy(alpha = 0.30f)
            var x = 0f
            while (x < size.width) {
                drawLine(color = gridColor, start = Offset(x, 0f), end = Offset(x, size.height), strokeWidth = 0.8f)
                x += gridStep
            }
            var y = 0f
            while (y < size.height) {
                drawLine(color = gridColor, start = Offset(0f, y), end = Offset(size.width, y), strokeWidth = 0.8f)
                y += gridStep
            }
        }

        // Barra superior de acciones rápidas (Tema y Servidor)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(horizontal = Spacing.m, vertical = Spacing.xs),
            horizontalArrangement = Arrangement.End,
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = { ThemeController.toggleTheme() }) {
                Icon(
                    imageVector = if (isDark) Icons.Default.LightMode else Icons.Default.DarkMode,
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

        // Contenedor principal centrado
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = Spacing.l)
                .navigationBarsPadding(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Emblema técnico de 120 dp con presencia
            ActuatorGaugeEmblem(modifier = Modifier.padding(bottom = Spacing.s))

            Text(
                text = stringResource(R.string.brand_name),
                style = MaterialTheme.typography.labelSmall,
                color = KonectoTheme.semantics.accentText,
                fontWeight = FontWeight.Bold,
                letterSpacing = 2.sp
            )
            Text(
                text = stringResource(R.string.app_name),
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface,
                letterSpacing = (-0.5).sp
            )
            Text(
                text = stringResource(R.string.app_subtitle),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(bottom = Spacing.m)
            )

            // Tarjeta compacta de credenciales
            Card(
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .border(
                        1.dp,
                        KonectoTheme.semantics.accent.copy(alpha = 0.35f),
                        RoundedCornerShape(16.dp)
                    )
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(Spacing.m),
                    verticalArrangement = Arrangement.spacedBy(Spacing.s)
                ) {
                    // Chip de servidor activo
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .clickable { showServerDialog = true }
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = Spacing.s, vertical = Spacing.xxs),
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
                                color = KonectoTheme.semantics.accentText,
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

                    // Perfiles demo rápidos compactos
                    Column(verticalArrangement = Arrangement.spacedBy(Spacing.xxs)) {
                        Text(
                            text = stringResource(R.string.login_quick_profiles),
                            style = MaterialTheme.typography.labelSmall,
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
                                    shape = RoundedCornerShape(6.dp),
                                    border = BorderStroke(
                                        1.dp,
                                        if (isSelected) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.outline
                                    ),
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(6.dp))
                                        .clickable {
                                            email = userEmail
                                            password = userPass
                                        }
                                ) {
                                    Text(
                                        text = label,
                                        fontSize = 11.sp,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                        color = if (isSelected) KonectoTheme.semantics.accentText else MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(horizontal = Spacing.s, vertical = 4.dp)
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

                    // Botón Sign In
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
                            .height(44.dp)
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
                                fontSize = 14.sp,
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
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
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
