package io.konecto.series76.ui.debug

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBackIos
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.data.ApiClient
import io.konecto.series76.data.DebugTracePayload
import io.konecto.series76.ui.AppScreen
import io.konecto.series76.ui.MainViewModel
import io.konecto.series76.ui.theme.Spacing

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DebugScreen(vm: MainViewModel) {
    val context = LocalContext.current
    val assistantMessages = remember(vm.messages) {
        vm.messages.filter { it.role == "assistant" && it.debugTrace != null }.reversed()
    }

    Scaffold(
        containerColor = Color(0xFF0F172A),
        topBar = {
            Column {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color(0xFF1E293B),
                        titleContentColor = Color.White
                    ),
                    navigationIcon = {
                        IconButton(onClick = { vm.currentScreen = AppScreen.CHAT }) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBackIos,
                                contentDescription = "Back",
                                tint = Color.White,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    },
                    title = {
                        Column {
                            Text(
                                text = "X-Ray Telemetry Inspector",
                                fontWeight = FontWeight.Bold,
                                fontSize = 17.sp,
                                color = Color.White,
                                letterSpacing = (-0.3).sp
                            )
                            Text(
                                text = "Tools invoked, parameters, SQL & PostgreSQL output",
                                fontSize = 11.sp,
                                color = Color(0xFF94A3B8),
                                fontWeight = FontWeight.Normal
                            )
                        }
                    }
                )
                HorizontalDivider(thickness = 1.dp, color = Color(0xFF334155))
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
                    text = "No agent answers with debug telemetry in this session yet.",
                    color = Color(0xFF94A3B8)
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
                            .take(100)
                    }

                    Surface(
                        shape = RoundedCornerShape(14.dp),
                        color = Color(0xFF1E293B),
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, Color(0xFF334155), RoundedCornerShape(14.dp))
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
                                    text = "Answer: \"$cleanPreview...\"",
                                    color = Color(0xFFCBD5E1),
                                    fontSize = 12.sp,
                                    lineHeight = 16.sp,
                                    modifier = Modifier.weight(1f)
                                )
                                IconButton(
                                    onClick = {
                                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                        val jsonString = ApiClient.jsonFormat.encodeToString(DebugTracePayload.serializer(), trace)
                                        clipboard.setPrimaryClip(ClipData.newPlainText("debug_trace", jsonString))
                                        Toast.makeText(context, "Copied Trace JSON", Toast.LENGTH_SHORT).show()
                                    }
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.ContentCopy,
                                        contentDescription = "Copy JSON",
                                        tint = Color(0xFF38BDF8),
                                        modifier = Modifier.size(16.dp)
                                    )
                                }
                            }

                            // Model, Provider & Total Latency
                            Text(
                                text = "Model: ${trace.modelUsed} (${trace.provider.ifEmpty { "unknown" }}) | Latency: ${trace.totalLatencyMs} ms | Cost: \$${trace.costUsdEstimate}",
                                color = Color(0xFF38BDF8),
                                fontFamily = FontFamily.Monospace,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold
                            )

                            // Active Context Part Numbers
                            Text(
                                text = "Active Context: ${trace.activeContextPartNumbers.joinToString(", ").ifEmpty { "None" }}",
                                color = Color(0xFF4ADE80),
                                fontFamily = FontFamily.Monospace,
                                fontSize = 11.sp
                            )

                            // Token Usage
                            if (trace.tokenUsage != null) {
                                Text(
                                    text = "Token Usage: ${trace.tokenUsage}",
                                    color = Color(0xFFFDE68A),
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 11.sp
                                )
                            }

                            // Timeline Steps
                            if (trace.steps.isNotEmpty()) {
                                HorizontalDivider(thickness = 0.5.dp, color = Color(0xFF334155))
                                Text(
                                    text = "EXECUTION TIMELINE STEPS",
                                    color = Color(0xFF94A3B8),
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold
                                )
                                trace.steps.forEach { step ->
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween
                                    ) {
                                        Text(
                                            text = "• ${step.name}",
                                            color = Color(0xFFE2E8F0),
                                            fontFamily = FontFamily.Monospace,
                                            fontSize = 11.sp
                                        )
                                        Text(
                                            text = "+${step.startMs}ms (${step.durationMs}ms)",
                                            color = Color(0xFF94A3B8),
                                            fontFamily = FontFamily.Monospace,
                                            fontSize = 10.sp
                                        )
                                    }
                                }
                            }

                            HorizontalDivider(thickness = 0.5.dp, color = Color(0xFF334155))

                            // Tool Calls
                            if (trace.toolCalls.isEmpty()) {
                                Text(
                                    text = "No tools invoked in this turn.",
                                    color = Color(0xFFF87171),
                                    fontSize = 12.sp
                                )
                            } else {
                                trace.toolCalls.forEachIndexed { idx, tc ->
                                    Column(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .background(Color(0xFF0F172A), RoundedCornerShape(8.dp))
                                            .padding(10.dp),
                                        verticalArrangement = Arrangement.spacedBy(Spacing.xxs)
                                    ) {
                                        Text(
                                            text = "TOOL #${idx + 1}: ${tc.toolName} (${tc.executionTimeMs} ms)",
                                            color = Color(0xFF4ADE80),
                                            fontFamily = FontFamily.Monospace,
                                            fontWeight = FontWeight.Bold,
                                            fontSize = 12.sp
                                        )
                                        Text(
                                            text = "Parameters: ${tc.arguments}",
                                            color = Color.White,
                                            fontFamily = FontFamily.Monospace,
                                            fontSize = 11.sp
                                        )
                                        if (!tc.sqlExecuted.isNullOrBlank()) {
                                            Text(
                                                text = "SQL: ${tc.sqlExecuted}",
                                                color = Color(0xFF93C5FD),
                                                fontFamily = FontFamily.Monospace,
                                                fontSize = 11.sp
                                            )
                                        }
                                        Text(
                                            text = "Returned Data: ${tc.rawOutput.toString().take(900)}",
                                            color = Color(0xFFD1D1D6),
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

