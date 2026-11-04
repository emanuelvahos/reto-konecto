package io.konecto.series76.ui.chat

import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.*
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
import androidx.compose.material.icons.filled.DarkMode
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.R
import io.konecto.series76.ui.AppScreen
import io.konecto.series76.ui.MainViewModel
import io.konecto.series76.ui.components.ChatBubbleItem
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing
import io.konecto.series76.ui.theme.ThemeController
import io.konecto.series76.util.VoiceNormalizer
import java.util.Locale

@Composable
fun TypingIndicator(modifier: Modifier = Modifier) {
    val infiniteTransition = rememberInfiniteTransition(label = "typingDots")
    val dot1 by infiniteTransition.animateFloat(
        initialValue = 0.25f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(550, delayMillis = 0), RepeatMode.Reverse),
        label = "dot1"
    )
    val dot2 by infiniteTransition.animateFloat(
        initialValue = 0.25f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(550, delayMillis = 180), RepeatMode.Reverse),
        label = "dot2"
    )
    val dot3 by infiniteTransition.animateFloat(
        initialValue = 0.25f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(550, delayMillis = 360), RepeatMode.Reverse),
        label = "dot3"
    )

    Row(
        modifier = modifier.padding(horizontal = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        listOf(dot1, dot2, dot3).forEach { alpha ->
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .clip(CircleShape)
                    .background(KonectoTheme.semantics.accent.copy(alpha = alpha))
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun ChatScreen(vm: MainViewModel) {
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current
    var inputText by remember { mutableStateOf("") }
    var showVoiceSimulationDialog by remember { mutableStateOf(false) }

    val activePart = remember(vm.messages) {
        vm.messages.lastOrNull { it.uiPayload?.actuators?.isNotEmpty() == true }
            ?.uiPayload?.actuators?.firstOrNull()?.basePartNumber
    }

    val displayTitle = remember(vm.activeSessionTitle, activePart) {
        val title = vm.activeSessionTitle.trim()
        if (activePart != null && title.contains(activePart, ignoreCase = true)) {
            // No duplicar el chip si el título ya contiene el part number
            title.take(28)
        } else {
            title.take(28)
        }
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
                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
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
                                contentDescription = stringResource(R.string.chat_back),
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
                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                    Toast.makeText(context, "🔧 Developer Debug Mode Opened", Toast.LENGTH_SHORT).show()
                                }
                            )
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(Spacing.xxs)
                            ) {
                                Text(
                                    text = displayTitle.ifEmpty { stringResource(R.string.chat_default_title) },
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    style = MaterialTheme.typography.titleMedium,
                                    color = MaterialTheme.colorScheme.onSurface,
                                    modifier = Modifier.weight(1f, fill = false)
                                )
                                // Mostrar chip solo si no es idéntico al título
                                if (activePart != null && !displayTitle.equals(activePart, ignoreCase = true)) {
                                    Surface(
                                        color = KonectoTheme.semantics.accentContainer,
                                        shape = RoundedCornerShape(4.dp),
                                        border = BorderStroke(1.dp, KonectoTheme.semantics.warningBorder)
                                    ) {
                                        Text(
                                            text = activePart,
                                            fontSize = 10.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = KonectoTheme.semantics.accent,
                                            fontFamily = FontFamily.Monospace,
                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                        )
                                    }
                                }
                            }
                            Text(
                                text = stringResource(R.string.chat_subtitle),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    },
                    actions = {
                        IconButton(onClick = { ThemeController.toggleTheme() }) {
                            Icon(
                                imageVector = if (ThemeController.isDarkTheme) Icons.Default.LightMode else Icons.Default.DarkMode,
                                contentDescription = "Toggle Theme",
                                tint = KonectoTheme.semantics.accent
                            )
                        }
                        if (vm.isDeveloperModeUnlocked) {
                            IconButton(onClick = { vm.currentScreen = AppScreen.DEBUG }) {
                                Icon(
                                    imageVector = Icons.Default.Terminal,
                                    contentDescription = stringResource(R.string.chat_open_debug),
                                    tint = KonectoTheme.semantics.accent
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

            // Consultas sugeridas cuando el chat está vacío
            if (vm.messages.isEmpty() && !vm.isLoading) {
                Column(
                    modifier = Modifier.padding(Spacing.m).fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(Spacing.xs)
                ) {
                    Text(
                        text = stringResource(R.string.chat_suggested_queries),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    listOf(
                        stringResource(R.string.chat_suggested_1),
                        stringResource(R.string.chat_suggested_2),
                        stringResource(R.string.chat_suggested_3),
                        stringResource(R.string.chat_suggested_4)
                    ).forEach { sample ->
                        Surface(
                            color = MaterialTheme.colorScheme.surface,
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(12.dp))
                                .clickable {
                                    haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                    vm.sendUserMessage(sample)
                                }
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
                                    tint = KonectoTheme.semantics.accent,
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
                                modifier = Modifier.padding(horizontal = Spacing.m, vertical = Spacing.xs)
                            ) {
                                TypingIndicator()
                                Text(
                                    text = stringResource(R.string.chat_thinking),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                    }
                }
            }

            // Barra de entrada inferior redondeada
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
                            contentDescription = stringResource(R.string.chat_voice),
                            tint = KonectoTheme.semantics.accent,
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
                                text = stringResource(R.string.chat_input_placeholder),
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
                            cursorBrush = SolidColor(KonectoTheme.semantics.accent),
                            maxLines = 4,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }

                    val canSend = inputText.isNotBlank() && !vm.isLoading
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(if (canSend) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.outline)
                            .clickable(enabled = canSend) {
                                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                val q = inputText
                                inputText = ""
                                vm.sendUserMessage(q)
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.ArrowUpward,
                            contentDescription = stringResource(R.string.chat_send),
                            tint = if (canSend) KonectoTheme.semantics.onAccent else MaterialTheme.colorScheme.onSurfaceVariant,
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
                            color = KonectoTheme.semantics.accent,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onSendNormalizedQuery(customText) },
                colors = ButtonDefaults.buttonColors(containerColor = KonectoTheme.semantics.accent),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text("Normalize & Send", color = KonectoTheme.semantics.onAccent, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.server_dialog_cancel), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    )
}
