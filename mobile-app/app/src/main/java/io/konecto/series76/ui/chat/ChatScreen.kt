package io.konecto.series76.ui.chat

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
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
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import io.konecto.series76.R
import io.konecto.series76.data.ActuatorDto
import io.konecto.series76.data.ServerPreferences
import io.konecto.series76.ui.ActuatorFullDatasheetSheet
import io.konecto.series76.ui.AppScreen
import io.konecto.series76.ui.MainViewModel
import io.konecto.series76.ui.ShimmerSkeletonCard
import io.konecto.series76.ui.components.ChatBubbleItem
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing
import io.konecto.series76.ui.theme.ThemeController
import io.konecto.series76.util.LocaleController
import io.konecto.series76.util.VoiceNormalizer
import io.konecto.series76.util.VoiceRecognitionManager
import io.konecto.series76.util.VoiceState

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

    // Estados para Ficha Técnica Completa y Reconocimiento de Voz
    var selectedActuatorForDatasheet by remember { mutableStateOf<ActuatorDto?>(null) }
    var showPermissionRationale by remember { mutableStateOf(false) }
    var showVoiceListeningDialog by remember { mutableStateOf(false) }
    var voiceTextToConfirm by remember { mutableStateOf<String?>(null) }

    val voiceManager = remember { VoiceRecognitionManager(context) }
    DisposableEffect(Unit) {
        onDispose {
            voiceManager.destroy()
            vm.stopTts()
        }
    }

    val activePart = remember(vm.messages) {
        vm.messages.lastOrNull { it.uiPayload?.actuators?.isNotEmpty() == true }
            ?.uiPayload?.actuators?.firstOrNull()?.basePartNumber
            ?: vm.messages.lastOrNull { it.uiPayload?.recommendation?.ranking?.isNotEmpty() == true }
                ?.uiPayload?.recommendation?.ranking?.firstOrNull()?.partNumber
    }

    val displayTitle = remember(vm.activeSessionTitle, activePart) {
        val raw = vm.activeSessionTitle.trim()
        if (raw.isNotEmpty() && raw != "Series 76" && raw != "New Actuator Consultation") {
            raw.take(28)
        } else if (activePart != null) {
            activePart
        } else {
            ""
        }
    }

    val appLangPref by ServerPreferences.getAppLanguage(context).collectAsState(initial = ServerPreferences.LANG_AUTO)
    val effectiveLang = remember(appLangPref) { LocaleController.getEffectiveLanguage(appLangPref) }
    val speechTag = if (effectiveLang == "es") "es-CO" else "en-US"

    val recordAudioLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
            voiceManager.startListening(speechTag)
            showVoiceListeningDialog = true
        } else {
            Toast.makeText(context, context.getString(R.string.voice_permission_denied), Toast.LENGTH_LONG).show()
        }
    }

    // Observar estados del VoiceRecognitionManager
    LaunchedEffect(voiceManager.state) {
        when (val state = voiceManager.state) {
            is VoiceState.Success -> {
                haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                showVoiceListeningDialog = false
                val normalized = VoiceNormalizer.normalizeSpokenTechnicalQuery(state.text)
                voiceTextToConfirm = normalized
                voiceManager.reset()
            }
            is VoiceState.Error -> {
                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
            }
            else -> {}
        }
    }

    fun startVoiceFlow() {
        vm.stopTts()
        if (!voiceManager.isAvailable()) {
            Toast.makeText(context, context.getString(R.string.voice_unavailable), Toast.LENGTH_SHORT).show()
            return
        }
        val hasPermission = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED

        if (hasPermission) {
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
            voiceManager.startListening(speechTag)
            showVoiceListeningDialog = true
        } else {
            val activity = context as? Activity
            if (activity != null && ActivityCompat.shouldShowRequestPermissionRationale(activity, Manifest.permission.RECORD_AUDIO)) {
                showPermissionRationale = true
            } else {
                recordAudioLauncher.launch(Manifest.permission.RECORD_AUDIO)
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
                            vm.stopTts()
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
                                val isTitleThePartNumber = activePart != null && displayTitle.equals(activePart, ignoreCase = true)
                                if (activePart != null && !isTitleThePartNumber) {
                                    Surface(
                                        color = KonectoTheme.semantics.accentContainer,
                                        shape = RoundedCornerShape(4.dp),
                                        border = BorderStroke(1.dp, KonectoTheme.semantics.warningBorder)
                                    ) {
                                        Text(
                                            text = activePart,
                                            fontSize = 10.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = KonectoTheme.semantics.accentText,
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
                                contentDescription = stringResource(R.string.theme_toggle),
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
                    shape = RoundedCornerShape(10.dp),
                    border = BorderStroke(1.dp, KonectoTheme.semantics.errorBorder),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = Spacing.s, vertical = Spacing.xs)
                ) {
                    Row(
                        modifier = Modifier.padding(Spacing.s),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = stringResource(R.string.chat_error_title),
                                color = KonectoTheme.semantics.errorText,
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = vm.errorMessage!!,
                                color = KonectoTheme.semantics.errorText,
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                        Button(
                            onClick = { vm.retryLastMessage() },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = MaterialTheme.colorScheme.error,
                                contentColor = MaterialTheme.colorScheme.onError
                            ),
                            shape = RoundedCornerShape(6.dp),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            Text(
                                text = stringResource(R.string.retry),
                                color = MaterialTheme.colorScheme.onError,
                                fontWeight = FontWeight.Bold,
                                fontSize = 11.sp
                            )
                        }
                    }
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
                    val isLastAssistant = (msg == vm.messages.lastOrNull { it.role == "assistant" })
                    val verification = vm.messageVerifications[msg.id]
                    ChatBubbleItem(
                        msg = msg,
                        verification = verification,
                        isLastAssistantMessage = isLastAssistant,
                        onSendQuery = { query -> vm.sendUserMessage(query) },
                        onRetry = { vm.retryLastMessage() },
                        onOpenFullDatasheet = { act -> selectedActuatorForDatasheet = act }
                    )
                }
                if (vm.isLoading) {
                    item(key = "loading_indicator") {
                        Column(
                            modifier = Modifier.fillMaxWidth(),
                            verticalArrangement = Arrangement.spacedBy(Spacing.s)
                        ) {
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

                            // Ficha técnica en estado de carga con animación shimmer
                            ShimmerSkeletonCard()
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
                    // Botón de Voz
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.surfaceVariant)
                            .border(1.dp, MaterialTheme.colorScheme.outline, CircleShape)
                            .clickable { startVoiceFlow() },
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

    // ModalBottomSheet: Ficha Técnica Completa
    if (selectedActuatorForDatasheet != null) {
        ActuatorFullDatasheetSheet(
            actuator = selectedActuatorForDatasheet!!,
            onDismiss = { selectedActuatorForDatasheet = null }
        )
    }

    // Dialogo: Escuchando Audio con medidor RMS y parcial en tiempo real
    if (showVoiceListeningDialog) {
        VoiceListeningDialog(
            voiceManager = voiceManager,
            onDismiss = {
                showVoiceListeningDialog = false
                voiceManager.cancel()
            },
            onStopListening = {
                voiceManager.stopListening()
            }
        )
    }

    // Dialogo: Confirmación y edición de consulta reconocida antes de enviar
    if (voiceTextToConfirm != null) {
        VoiceConfirmationDialog(
            initialText = voiceTextToConfirm!!,
            onDismiss = { voiceTextToConfirm = null },
            onConfirm = { confirmedText ->
                voiceTextToConfirm = null
                vm.sendUserMessage(confirmedText, inputMode = "voice")
            }
        )
    }

    // Dialogo: Explicación de Permiso de Micrófono (Rationale)
    if (showPermissionRationale) {
        VoicePermissionRationaleDialog(
            onDismiss = { showPermissionRationale = false },
            onGrant = {
                showPermissionRationale = false
                recordAudioLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
        )
    }
}

@Composable
fun VoiceListeningDialog(
    voiceManager: VoiceRecognitionManager,
    onDismiss: () -> Unit,
    onStopListening: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Text(
                text = stringResource(R.string.voice_listening_title),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.Bold
            )
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = Spacing.s),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(Spacing.m)
            ) {
                // Indicador visual RMS dinámico
                Box(
                    modifier = Modifier
                        .size(88.dp)
                        .clip(CircleShape)
                        .background(KonectoTheme.semantics.accentContainer)
                        .border(
                            width = (3 + (voiceManager.rmsLevel * 7)).dp,
                            color = KonectoTheme.semantics.accent,
                            shape = CircleShape
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Mic,
                        contentDescription = null,
                        tint = KonectoTheme.semantics.accentText,
                        modifier = Modifier.size(38.dp)
                    )
                }

                Text(
                    text = stringResource(R.string.voice_listening_desc),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center
                )

                // Transcripción en vivo de resultados parciales
                if (voiceManager.partialResult.isNotBlank()) {
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = "“${voiceManager.partialResult}”",
                            style = MaterialTheme.typography.bodyMedium,
                            fontFamily = FontFamily.Monospace,
                            color = MaterialTheme.colorScheme.onSurface,
                            modifier = Modifier.padding(10.dp)
                        )
                    }
                }

                if (voiceManager.state is VoiceState.Error) {
                    val err = (voiceManager.state as VoiceState.Error).message
                    Text(
                        text = "⚠️ $err",
                        style = MaterialTheme.typography.bodySmall,
                        color = KonectoTheme.semantics.errorText
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = onStopListening,
                colors = ButtonDefaults.buttonColors(containerColor = KonectoTheme.semantics.accent),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(
                    text = stringResource(R.string.voice_stop),
                    color = KonectoTheme.semantics.onAccent,
                    fontWeight = FontWeight.Bold
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(
                    text = stringResource(R.string.voice_cancel),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    )
}

@Composable
fun VoiceConfirmationDialog(
    initialText: String,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    var editableText by remember(initialText) { mutableStateOf(initialText) }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Text(
                text = stringResource(R.string.voice_confirm_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )
        },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(Spacing.s)
            ) {
                Text(
                    text = stringResource(R.string.voice_confirm_desc),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                OutlinedTextField(
                    value = editableText,
                    onValueChange = { editableText = it },
                    label = { Text("Query") },
                    shape = RoundedCornerShape(10.dp),
                    textStyle = TextStyle(
                        fontFamily = FontFamily.Monospace,
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onSurface
                    ),
                    modifier = Modifier.fillMaxWidth(),
                    maxLines = 4
                )
            }
        },
        confirmButton = {
            Button(
                onClick = { onConfirm(editableText) },
                enabled = editableText.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = KonectoTheme.semantics.accent),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(
                    text = stringResource(R.string.voice_confirm_send),
                    color = KonectoTheme.semantics.onAccent,
                    fontWeight = FontWeight.Bold
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(
                    text = stringResource(R.string.voice_cancel),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    )
}

@Composable
fun VoicePermissionRationaleDialog(
    onDismiss: () -> Unit,
    onGrant: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Text(
                text = stringResource(R.string.voice_permission_rationale_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )
        },
        text = {
            Text(
                text = stringResource(R.string.voice_permission_rationale_msg),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        },
        confirmButton = {
            Button(
                onClick = onGrant,
                colors = ButtonDefaults.buttonColors(containerColor = KonectoTheme.semantics.accent),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(
                    text = stringResource(R.string.voice_permission_grant),
                    color = KonectoTheme.semantics.onAccent,
                    fontWeight = FontWeight.Bold
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(
                    text = stringResource(R.string.voice_cancel),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    )
}
