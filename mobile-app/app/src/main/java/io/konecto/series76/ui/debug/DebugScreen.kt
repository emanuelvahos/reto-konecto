package io.konecto.series76.ui.debug

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBackIos
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.R
import io.konecto.series76.data.ApiClient
import io.konecto.series76.data.DebugTracePayload
import io.konecto.series76.data.TraceStep
import io.konecto.series76.ui.AppScreen
import io.konecto.series76.ui.MainViewModel
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing
import io.konecto.series76.ui.theme.ThemeController

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DebugScreen(vm: MainViewModel) {
    val context = LocalContext.current
    val assistantMessages = remember(vm.messages) {
        vm.messages.filter { it.role == "assistant" && it.debugTrace != null }.reversed()
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            Column {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.surface,
                        titleContentColor = MaterialTheme.colorScheme.onSurface
                    ),
                    navigationIcon = {
                        IconButton(onClick = { vm.currentScreen = AppScreen.CHAT }) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBackIos,
                                contentDescription = stringResource(R.string.chat_back),
                                tint = MaterialTheme.colorScheme.onSurface,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    },
                    title = {
                        Column {
                            Text(
                                text = stringResource(R.string.debug_title),
                                fontWeight = FontWeight.Bold,
                                fontSize = 17.sp,
                                color = MaterialTheme.colorScheme.onSurface,
                                letterSpacing = (-0.3).sp
                            )
                            Text(
                                text = stringResource(R.string.debug_subtitle),
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontWeight = FontWeight.Normal
                            )
                        }
                    },
                    actions = {
                        IconButton(onClick = { ThemeController.toggleTheme() }) {
                            Icon(
                                imageVector = if (ThemeController.isDarkTheme) Icons.Default.LightMode else Icons.Default.DarkMode,
                                contentDescription = stringResource(R.string.theme_toggle),
                                tint = KonectoTheme.semantics.accent
                            )
                        }
                    }
                )
                HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)
            }
        }
    ) { padding ->
        if (assistantMessages.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = stringResource(R.string.debug_empty),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = Spacing.s),
                verticalArrangement = Arrangement.spacedBy(Spacing.s),
                contentPadding = PaddingValues(vertical = 14.dp)
            ) {
                items(assistantMessages, key = { it.id }) { msg ->
                    val trace = msg.debugTrace!!
                    val cleanPreview = remember(msg.content) {
                        msg.content
                            .lines()
                            .filter { !it.trim().startsWith("|") }
                            .joinToString(" ")
                            .replace("**", "")
                            .replace("`", "")
                            .replace(Regex("""#{1,6}\s*"""), "")
                            .replace(Regex("""\s+"""), " ")
                            .trim()
                            .take(90)
                    }

                    Surface(
                        shape = RoundedCornerShape(14.dp),
                        color = MaterialTheme.colorScheme.surface,
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(
                            modifier = Modifier.padding(Spacing.m),
                            verticalArrangement = Arrangement.spacedBy(Spacing.xs)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = stringResource(R.string.debug_answer_preview, cleanPreview),
                                    color = MaterialTheme.colorScheme.onSurface,
                                    fontSize = 12.sp,
                                    lineHeight = 16.sp,
                                    modifier = Modifier.weight(1f)
                                )
                                IconButton(
                                    onClick = {
                                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                        val jsonString = ApiClient.jsonFormat.encodeToString(DebugTracePayload.serializer(), trace)
                                        clipboard.setPrimaryClip(ClipData.newPlainText("debug_trace", jsonString))
                                        Toast.makeText(context, context.getString(R.string.debug_copied), Toast.LENGTH_SHORT).show()
                                    }
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.ContentCopy,
                                        contentDescription = stringResource(R.string.debug_copy_json),
                                        tint = KonectoTheme.semantics.accentText,
                                        modifier = Modifier.size(16.dp)
                                    )
                                }
                            }

                            // Model, Provider & Total Latency
                            Text(
                                text = stringResource(
                                    R.string.debug_metric_summary,
                                    trace.modelUsed,
                                    trace.provider.ifEmpty { "unknown" },
                                    trace.totalLatencyMs.toInt(),
                                    trace.costUsdEstimate
                                ),
                                color = KonectoTheme.semantics.accentText,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold
                            )

                            // Active Context Part Numbers
                            Text(
                                text = stringResource(R.string.debug_active_context, trace.activeContextPartNumbers.joinToString(", ").ifEmpty { "None" }),
                                color = KonectoTheme.semantics.successText,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 11.sp
                            )

                            // Token Usage
                            if (trace.tokenUsage != null) {
                                Text(
                                    text = stringResource(R.string.debug_token_usage, trace.tokenUsage),
                                    color = KonectoTheme.semantics.warningText,
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 11.sp
                                )
                            }

                            // Diagrama de cascada (Waterfall Timeline)
                            if (trace.steps.isNotEmpty()) {
                                HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant)
                                WaterfallTimeline(
                                    steps = trace.steps,
                                    totalLatencyMs = trace.totalLatencyMs
                                )
                            }

                            HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant)

                            // Tool Calls
                            if (trace.toolCalls.isEmpty()) {
                                Text(
                                    text = stringResource(R.string.debug_no_tools),
                                    color = KonectoTheme.semantics.errorText,
                                    fontSize = 12.sp
                                )
                            } else {
                                val toolBoxBg = if (ThemeController.isDarkTheme) Color(0xFF0F172A) else Color(0xFFE2E8F0)
                                trace.toolCalls.forEachIndexed { idx, tc ->
                                    Column(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .background(toolBoxBg, RoundedCornerShape(8.dp))
                                            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(8.dp))
                                            .padding(10.dp),
                                        verticalArrangement = Arrangement.spacedBy(Spacing.xxs)
                                    ) {
                                        Text(
                                            text = stringResource(R.string.debug_tool_header, idx + 1, tc.toolName, tc.executionTimeMs.toInt()),
                                            color = KonectoTheme.semantics.successText,
                                            fontFamily = FontFamily.Monospace,
                                            fontWeight = FontWeight.Bold,
                                            fontSize = 12.sp
                                        )
                                        Text(
                                            text = stringResource(R.string.debug_params, tc.arguments.toString()),
                                            color = MaterialTheme.colorScheme.onSurface,
                                            fontFamily = FontFamily.Monospace,
                                            fontSize = 11.sp
                                        )
                                        if (!tc.sqlExecuted.isNullOrBlank()) {
                                            Text(
                                                text = stringResource(R.string.debug_sql, tc.sqlExecuted),
                                                color = if (ThemeController.isDarkTheme) Color(0xFF93C5FD) else Color(0xFF1D4ED8),
                                                fontFamily = FontFamily.Monospace,
                                                fontSize = 11.sp
                                            )
                                        }
                                        Text(
                                            text = stringResource(R.string.debug_returned_data, tc.rawOutput.toString().take(900)),
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            fontFamily = FontFamily.Monospace,
                                            fontSize = 11.sp
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

/**
 * Diagrama de Cascada (Waterfall) para los pasos de ejecución
 */
@Composable
fun WaterfallTimeline(
    steps: List<TraceStep>,
    totalLatencyMs: Double,
    modifier: Modifier = Modifier
) {
    val totalTime: Float = if (totalLatencyMs > 0.0) totalLatencyMs.toFloat() else 1.0f

    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(8.dp))
            .padding(10.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text(
            text = stringResource(R.string.debug_timeline_title),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.5.sp
        )

        for (step in steps) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(3.dp)
            ) {
                // Fila de texto: Nombre del paso a la izquierda, duración a la derecha
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "• ${step.name}",
                        color = MaterialTheme.colorScheme.onSurface,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1
                    )
                    Text(
                        text = "+${step.startMs.toInt()}ms (${step.durationMs.toInt()}ms)",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp
                    )
                }

                // Barra horizontal proporcional en cascada
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(6.dp)
                        .clip(RoundedCornerShape(3.dp))
                        .background(MaterialTheme.colorScheme.surface)
                ) {
                    val startOffsetFraction: Float = (step.startMs.toFloat() / totalTime).coerceIn(0f, 0.95f)
                    val widthFraction: Float = (step.durationMs.toFloat() / totalTime).coerceIn(0.04f, 1f - startOffsetFraction)

                    Row(modifier = Modifier.fillMaxSize()) {
                        if (startOffsetFraction > 0f) {
                            Spacer(modifier = Modifier.weight(startOffsetFraction))
                        }
                        Box(
                            modifier = Modifier
                                .weight(widthFraction)
                                .fillMaxHeight()
                                .clip(RoundedCornerShape(3.dp))
                                .background(KonectoTheme.semantics.accent.copy(alpha = 0.85f))
                        )
                        val remainingFraction: Float = (1f - startOffsetFraction - widthFraction).coerceAtLeast(0f)
                        if (remainingFraction > 0f) {
                            Spacer(modifier = Modifier.weight(remainingFraction))
                        }
                    }
                }
            }
        }
    }
}
