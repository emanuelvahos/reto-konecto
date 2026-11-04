package io.konecto.series76.ui.chat

import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBackIos
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.ui.AppScreen
import io.konecto.series76.ui.MainViewModel
import io.konecto.series76.ui.components.ChatBubbleItem
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing
import io.konecto.series76.util.VoiceNormalizer
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun ChatScreen(vm: MainViewModel) {
    val context = LocalContext.current
    var inputText by remember { mutableStateOf("") }
    var showVoiceSimulationDialog by remember { mutableStateOf(false) }

    val activePart = remember(vm.messages) {
        vm.messages.lastOrNull { it.uiPayload?.actuators?.isNotEmpty() == true }
            ?.uiPayload?.actuators?.firstOrNull()?.basePartNumber
    }

    val voiceLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val spoken = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()
            if (!spoken.isNullOrBlank()) {
                val normalized = VoiceNormalizer.normalizeSpokenTechnicalQuery(spoken)
                Toast.makeText(context, "🎙️ Recognized: $normalized", Toast.LENGTH_SHORT).show()
                inputText = ""
                vm.sendUserMessage(normalized)
            }
        }
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
                        IconButton(onClick = {
                            vm.currentScreen = AppScreen.SESSIONS
                            vm.loadSessions()
                        }) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBackIos,
                                contentDescription = "Back",
                                tint = MaterialTheme.colorScheme.onSurface,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    },
                    title = {
                        Column(
                            modifier = Modifier.combinedClickable(
                                onClick = {},
                                onLongClick = {
                                    vm.isDeveloperModeUnlocked = true
                                    vm.currentScreen = AppScreen.DEBUG
                                    Toast.makeText(context, "🔧 Developer Debug Mode Opened", Toast.LENGTH_SHORT).show()
                                }
                            )
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(Spacing.xxs)
                            ) {
                                Text(
                                    text = vm.activeSessionTitle,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    style = MaterialTheme.typography.titleMedium,
                                    color = MaterialTheme.colorScheme.onSurface,
                                    modifier = Modifier.weight(1f, fill = false)
                                )
                                if (activePart != null) {
                                    Surface(
                                        color = MaterialTheme.colorScheme.surfaceVariant,
                                        shape = RoundedCornerShape(4.dp),
                                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
                                    ) {
                                        Text(
                                            text = activePart,
                                            fontSize = 10.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            fontFamily = FontFamily.Monospace,
                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                        )
                                    }
                                }
                            }
                            Text(
                                text = "Series 76 Technical Assistant",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    },
                    actions = {
                        if (vm.isDeveloperModeUnlocked) {
                            IconButton(onClick = { vm.currentScreen = AppScreen.DEBUG }) {
                                Icon(
                                    imageVector = Icons.Default.Terminal,
                                    contentDescription = "Open Developer Debug Screen",
                                    tint = MaterialTheme.colorScheme.primary
                                )
                            }
                        }
                    }
                )
                HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(padding)
        ) {
            if (vm.errorMessage != null) {
                Surface(
                    color = KonectoTheme.semantics.errorBg,
                    border = BorderStroke(1.dp, KonectoTheme.semantics.errorBorder),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = "⚠️ ${vm.errorMessage}",
                        color = KonectoTheme.semantics.errorText,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(Spacing.s)
                    )
                }
            }

            // Quick Suggestions when chat is empty
            if (vm.messages.isEmpty() && !vm.isLoading) {
                Column(
                    modifier = Modifier.padding(Spacing.m).fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(Spacing.xs)
                ) {
                    Text(
                        text = "SUGGESTED ENGINEERING QUERIES",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    listOf(
                        "Specs for Base Part Number 763B00-11300000/A",
                        "Recommend an Explosionproof actuator with at least 200 Nm Modulating torque on 24V DC",
                        "Compare 110V single phase Weatherproof models between 500 Nm and 1100 Nm",
                        "Is 761A00-11330C00/A available in 220V 3-Phase?"
                    ).forEach { sample ->
                        Surface(
                            color = MaterialTheme.colorScheme.surface,
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(12.dp))
                                .clickable { vm.sendUserMessage(sample) }
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 14.dp, vertical = Spacing.s),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = sample,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurface,
                                    fontWeight = FontWeight.Medium,
                                    modifier = Modifier.weight(1f)
                                )
                                Icon(
                                    imageVector = Icons.Default.ChevronRight,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                        }
                    }
                }
            }

            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = Spacing.s),
                verticalArrangement = Arrangement.spacedBy(Spacing.s),
                contentPadding = PaddingValues(vertical = 14.dp)
            ) {
                items(vm.messages, key = { it.id }) { msg ->
                    ChatBubbleItem(msg = msg)
                }
                if (vm.isLoading) {
                    item(key = "loading_indicator") {
                        Surface(
                            color = MaterialTheme.colorScheme.surface,
                            shape = RoundedCornerShape(16.dp),
                            modifier = Modifier.border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(16.dp))
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
                                modifier = Modifier.padding(horizontal = Spacing.s, vertical = Spacing.xs)
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(14.dp),
                                    strokeWidth = 2.dp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Text(
                                    text = "Thinking...",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
            }

            // Input Bar
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surface)
            ) {
                HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 10.dp, vertical = Spacing.xs),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
                ) {
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.surfaceVariant)
                            .border(1.dp, MaterialTheme.colorScheme.outline, CircleShape)
                            .combinedClickable(
                                onClick = {
                                    try {
                                        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                                            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                                            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.US)
                                            putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak Series 76 Part Number...")
                                        }
                                        voiceLauncher.launch(intent)
                                    } catch (e: Exception) {
                                        showVoiceSimulationDialog = true
                                    }
                                },
                                onLongClick = { showVoiceSimulationDialog = true }
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Mic,
                            contentDescription = "Voice Input",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(18.dp)
                        )
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(20.dp))
                            .background(MaterialTheme.colorScheme.surfaceVariant)
                            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(20.dp))
                            .padding(horizontal = 14.dp, vertical = 10.dp),
                        contentAlignment = Alignment.CenterStart
                    ) {
                        if (inputText.isEmpty()) {
                            Text(
                                text = "Ask part number, torque, or 50Hz...",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        BasicTextField(
                            value = inputText,
                            onValueChange = { inputText = it },
                            textStyle = TextStyle(
                                fontSize = 14.sp,
                                color = MaterialTheme.colorScheme.onSurface
                            ),
                            cursorBrush = SolidColor(MaterialTheme.colorScheme.onSurface),
                            maxLines = 4,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }

                    val canSend = inputText.isNotBlank() && !vm.isLoading
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(if (canSend) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline)
                            .clickable(enabled = canSend) {
                                val q = inputText
                                inputText = ""
                                vm.sendUserMessage(q)
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.ArrowUpward,
                            contentDescription = "Send",
                            tint = if (canSend) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }

    if (showVoiceSimulationDialog) {
        VoiceSimulationDialog(
            onDismiss = { showVoiceSimulationDialog = false },
            onSendNormalizedQuery = { query ->
                showVoiceSimulationDialog = false
                val normalized = VoiceNormalizer.normalizeSpokenTechnicalQuery(query)
                Toast.makeText(context, "🎙️ Voice Normalized: $normalized", Toast.LENGTH_SHORT).show()
                vm.sendUserMessage(normalized)
            }
        )
    }
}

@Composable
fun VoiceSimulationDialog(
    onDismiss: () -> Unit,
    onSendNormalizedQuery: (String) -> Unit
) {
    var customText by remember { mutableStateOf("seven six three B zero zero dash one one three zero zero zero zero zero slash A") }
    val normalizedPreview = remember(customText) { VoiceNormalizer.normalizeSpokenTechnicalQuery(customText) }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Text(
                text = "🎙️ Voice & Technical Normalizer",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(Spacing.xs)) {
                Text(
                    text = "Select or type spoken English/Spanish words. VoiceNormalizer will deterministically resolve exact Series 76 codes:",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                listOf(
                    "seven six three B zero zero dash one one three zero zero zero zero zero slash A",
                    "siete seis tres be cero cero guion uno uno tres cero cero cero cero cero barra A"
                ).forEach { sample ->
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .clickable { customText = sample }
                    ) {
                        Text(
                            text = sample,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface,
                            modifier = Modifier.padding(Spacing.xs)
                        )
                    }
                }

                TextField(
                    value = customText,
                    onValueChange = { customText = it },
                    label = { Text("Spoken Technical Input") },
                    shape = RoundedCornerShape(8.dp),
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                        unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(8.dp),
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                    modifier = Modifier.fillMaxWidth().padding(top = Spacing.xxs)
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Text(
                            text = "NORMALIZED PART NUMBER OUTPUT",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = normalizedPreview,
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onSendNormalizedQuery(customText) },
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.onSurface),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text("Normalize & Send", color = MaterialTheme.colorScheme.surface, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    )
}

