package io.konecto.series76.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.R
import io.konecto.series76.data.ApiClient
import io.konecto.series76.data.ServerPreferences
import io.konecto.series76.mock.DebugMockProvider
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing
import io.konecto.series76.util.LocaleController
import android.content.Intent
import android.speech.tts.TextToSpeech
import io.konecto.series76.util.TtsManager
import io.konecto.series76.util.TtsStatus
import kotlinx.coroutines.launch

@Composable
fun ConnectionDialog(
    initialUrl: String,
    onDismiss: () -> Unit,
    onSaved: (String) -> Unit
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    var urlText by remember { mutableStateOf(initialUrl) }
    var isValid by remember { mutableStateOf(true) }
    var isTesting by remember { mutableStateOf(false) }
    var testResult by remember { mutableStateOf<String?>(null) }
    var testSuccess by remember { mutableStateOf(false) }

    var isMockEnabled by remember { mutableStateOf(DebugMockProvider.isMockEnabled) }
    var selectedMockKey by remember { mutableStateOf(DebugMockProvider.selectedSampleKey) }

    // Language & TTS settings
    var currentLang by remember { mutableStateOf(ServerPreferences.LANG_AUTO) }
    var isTtsEnabled by remember { mutableStateOf(false) }
    val isTtsEnginePresent = remember { TtsManager.isTtsEngineInstalled(context) }
    var ttsStatus by remember { mutableStateOf(if (isTtsEnginePresent) TtsStatus.AVAILABLE else TtsStatus.NO_ENGINE) }

    LaunchedEffect(Unit) {
        currentLang = ServerPreferences.getAppLanguageSync(context)
        isTtsEnabled = ServerPreferences.isTtsEnabledSync(context)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(16.dp),
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Column(verticalArrangement = Arrangement.spacedBy(Spacing.xxs)) {
                Text(
                    text = stringResource(R.string.settings_dialog_title),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = stringResource(R.string.server_dialog_subtitle),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(vertical = Spacing.xs),
                verticalArrangement = Arrangement.spacedBy(Spacing.s)
            ) {
                // 1. SELECTOR DE IDIOMA
                Column(verticalArrangement = Arrangement.spacedBy(Spacing.xxs)) {
                    Text(
                        text = stringResource(R.string.settings_lang_title),
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
                    ) {
                        val languages = listOf(
                            ServerPreferences.LANG_AUTO to stringResource(R.string.settings_lang_auto),
                            ServerPreferences.LANG_ES to stringResource(R.string.settings_lang_es),
                            ServerPreferences.LANG_EN to stringResource(R.string.settings_lang_en)
                        )
                        languages.forEach { (code, label) ->
                            val isSelected = currentLang == code
                            Surface(
                                color = if (isSelected) KonectoTheme.semantics.accentContainer else MaterialTheme.colorScheme.surfaceVariant,
                                shape = RoundedCornerShape(8.dp),
                                border = BorderStroke(
                                    1.dp,
                                    if (isSelected) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.outline
                                ),
                                modifier = Modifier
                                    .weight(1f)
                                    .clip(RoundedCornerShape(8.dp))
                                    .clickable {
                                        currentLang = code
                                        coroutineScope.launch {
                                            ServerPreferences.setAppLanguage(context, code)
                                            LocaleController.setLanguage(context, code)
                                        }
                                    }
                            ) {
                                Text(
                                    text = label,
                                    style = MaterialTheme.typography.bodySmall,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                    color = if (isSelected) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.onSurface,
                                    modifier = Modifier.padding(vertical = Spacing.xs, horizontal = 4.dp),
                                    maxLines = 1,
                                    fontSize = 11.sp
                                )
                            }
                        }
                    }
                }

                HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline)

                // 2. LECTURA EN VOZ ALTA (TTS) - Siempre visible
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(Spacing.xxs)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = stringResource(R.string.settings_tts_title),
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = if (isTtsEnginePresent) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                            )
                            Text(
                                text = if (isTtsEnginePresent) {
                                    stringResource(R.string.settings_tts_desc)
                                } else {
                                    stringResource(R.string.settings_tts_engine_unavailable)
                                },
                                style = MaterialTheme.typography.bodySmall,
                                color = if (isTtsEnginePresent) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error
                            )
                        }
                        Switch(
                            checked = isTtsEnabled && isTtsEnginePresent,
                            enabled = isTtsEnginePresent,
                            onCheckedChange = { checked ->
                                isTtsEnabled = checked
                                coroutineScope.launch {
                                    ServerPreferences.setTtsEnabled(context, checked)
                                }
                            },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = KonectoTheme.semantics.onAccent,
                                checkedTrackColor = KonectoTheme.semantics.accent
                            )
                        )
                    }

                    if (isTtsEnginePresent && ttsStatus == TtsStatus.MISSING_LANGUAGE_DATA) {
                        TextButton(
                            onClick = {
                                try {
                                    val installIntent = Intent(TextToSpeech.Engine.ACTION_INSTALL_TTS_DATA)
                                    context.startActivity(installIntent)
                                } catch (e: Exception) {
                                    try {
                                        context.startActivity(Intent("com.android.settings.TTS_SETTINGS"))
                                    } catch (_: Exception) {}
                                }
                            },
                            contentPadding = PaddingValues(0.dp)
                        ) {
                            Text(
                                text = "⬇ ${stringResource(R.string.settings_tts_download_language)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = KonectoTheme.semantics.accentText,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }

                HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline)

                // 3. URL DEL SERVIDOR
                CleanInputField(
                    label = stringResource(R.string.server_dialog_url_label),
                    value = urlText,
                    onValueChange = {
                        urlText = it
                        isValid = ServerPreferences.isValidUrl(it)
                        testResult = null
                    },
                    placeholder = "http://10.0.2.2:8001/"
                )

                if (!isValid) {
                    Text(
                        text = stringResource(R.string.server_dialog_invalid_url),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
                ) {
                    SuggestionChip(
                        onClick = {
                            urlText = "http://10.0.2.2:8001/"
                            isValid = true
                            testResult = null
                        },
                        label = { Text(stringResource(R.string.server_dialog_preset_emulator), fontSize = 11.sp) }
                    )
                    SuggestionChip(
                        onClick = {
                            urlText = "http://localhost:8001/"
                            isValid = true
                            testResult = null
                        },
                        label = { Text(stringResource(R.string.server_dialog_preset_localhost), fontSize = 11.sp) }
                    )
                }

                // Ayuda para conexión USB con celular
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f),
                    shape = RoundedCornerShape(6.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = "ℹ " + stringResource(R.string.server_dialog_localhost_help),
                        style = MaterialTheme.typography.bodySmall,
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(Spacing.xs)
                    )
                }

                // Botón de prueba de conexión
                Button(
                    onClick = {
                        coroutineScope.launch {
                            isTesting = true
                            testResult = null
                            val res = ApiClient.testConnection(urlText)
                            isTesting = false
                            if (res.isSuccess) {
                                val data = res.getOrNull()
                                testSuccess = true
                                testResult = context.getString(
                                    R.string.server_dialog_connected,
                                    data?.status ?: "ok",
                                    data?.actuatorsLoaded ?: 0
                                )
                            } else {
                                testSuccess = false
                                testResult = context.getString(
                                    R.string.server_dialog_failed,
                                    res.exceptionOrNull()?.localizedMessage ?: "Unreachable"
                                )
                            }
                        }
                    },
                    enabled = !isTesting && isValid && urlText.isNotBlank(),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                        contentColor = MaterialTheme.colorScheme.onSurfaceVariant
                    ),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    if (isTesting) {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                        Spacer(modifier = Modifier.width(Spacing.xs))
                        Text(stringResource(R.string.server_dialog_testing), fontSize = 12.sp)
                    } else {
                        Icon(imageVector = Icons.Default.Sync, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(Spacing.xs))
                        Text(stringResource(R.string.server_dialog_test_btn), fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    }
                }

                testResult?.let { msg ->
                    Surface(
                        color = if (testSuccess) KonectoTheme.semantics.successBg else KonectoTheme.semantics.errorBg,
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(
                                1.dp,
                                if (testSuccess) KonectoTheme.semantics.successBorder else KonectoTheme.semantics.errorBorder,
                                RoundedCornerShape(8.dp)
                            )
                    ) {
                        Row(
                            modifier = Modifier.padding(Spacing.xs),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(Spacing.xs)
                        ) {
                            Icon(
                                imageVector = if (testSuccess) Icons.Default.CheckCircle else Icons.Default.ErrorOutline,
                                contentDescription = null,
                                tint = if (testSuccess) KonectoTheme.semantics.successText else KonectoTheme.semantics.errorText,
                                modifier = Modifier.size(16.dp)
                            )
                            Text(
                                text = msg,
                                style = MaterialTheme.typography.bodySmall,
                                color = if (testSuccess) KonectoTheme.semantics.successText else KonectoTheme.semantics.errorText
                            )
                        }
                    }
                }

                // 4. MOCK DE DEPURACIÓN
                if (DebugMockProvider.isAvailable) {
                    HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = stringResource(R.string.server_dialog_mock_title),
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = stringResource(R.string.server_dialog_mock_desc),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        Switch(
                            checked = isMockEnabled,
                            onCheckedChange = {
                                isMockEnabled = it
                                DebugMockProvider.isMockEnabled = it
                            },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = KonectoTheme.semantics.onAccent,
                                checkedTrackColor = KonectoTheme.semantics.accent
                            )
                        )
                    }

                    if (isMockEnabled) {
                        Column(verticalArrangement = Arrangement.spacedBy(Spacing.xxs)) {
                            Text(
                                text = stringResource(R.string.server_dialog_active_sample),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            DebugMockProvider.sampleKeys.forEach { key ->
                                val isSelected = selectedMockKey == key
                                Surface(
                                    color = if (isSelected) KonectoTheme.semantics.accentContainer else MaterialTheme.colorScheme.surfaceVariant,
                                    shape = RoundedCornerShape(6.dp),
                                    border = BorderStroke(
                                        1.dp,
                                        if (isSelected) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.outline
                                    ),
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(6.dp))
                                        .clickable {
                                            selectedMockKey = key
                                            DebugMockProvider.selectedSampleKey = key
                                        }
                                ) {
                                    Text(
                                        text = key,
                                        style = MaterialTheme.typography.bodySmall,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                        color = if (isSelected) KonectoTheme.semantics.accent else MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(horizontal = Spacing.s, vertical = Spacing.xxs)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val normalized = ServerPreferences.normalizeUrl(urlText)
                    coroutineScope.launch {
                        ServerPreferences.setServerUrl(context, normalized)
                        ServerPreferences.setAppLanguage(context, currentLang)
                        ServerPreferences.setTtsEnabled(context, isTtsEnabled)
                        LocaleController.setLanguage(context, currentLang)
                        onSaved(normalized)
                    }
                },
                enabled = isValid && urlText.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = KonectoTheme.semantics.accent)
            ) {
                Text(stringResource(R.string.server_dialog_save), color = KonectoTheme.semantics.onAccent, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.server_dialog_cancel), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    )
}
