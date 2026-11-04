package io.konecto.series76.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
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

    AlertDialog(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(16.dp),
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Column(verticalArrangement = Arrangement.spacedBy(Spacing.xxs)) {
                Text(
                    text = stringResource(R.string.server_dialog_title),
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
                    .padding(vertical = Spacing.xs),
                verticalArrangement = Arrangement.spacedBy(Spacing.s)
            ) {
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

                // Debug Mock Switch
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
                                    border = androidx.compose.foundation.BorderStroke(
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
