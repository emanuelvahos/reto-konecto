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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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

    // Mock settings
    var isMockEnabled by remember { mutableStateOf(DebugMockProvider.isMockEnabled) }
    var selectedMockKey by remember { mutableStateOf(DebugMockProvider.selectedSampleKey) }

    AlertDialog(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(16.dp),
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Column(verticalArrangement = Arrangement.spacedBy(Spacing.xxs)) {
                Text(
                    text = "Server Configuration",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = "Configure host endpoint or switch to debug mock.",
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
                    label = "Server URL (Port 8001)",
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
                        text = "Invalid URL format. Example: http://10.0.2.2:8001/ or http://192.168.1.100:8001/",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }

                // Quick buttons for presets (Emulator, Physical Phone hints)
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
                        label = { Text("Emulator (10.0.2.2)", fontSize = 11.sp) }
                    )
                    SuggestionChip(
                        onClick = {
                            urlText = "http://localhost:8001/"
                            isValid = true
                            testResult = null
                        },
                        label = { Text("Localhost", fontSize = 11.sp) }
                    )
                }

                // Test Connection Button
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
                                testResult = "Connected! Status: ${data?.status}, Actuators loaded: ${data?.actuatorsLoaded}"
                            } else {
                                testSuccess = false
                                testResult = "Failed: ${res.exceptionOrNull()?.localizedMessage ?: "Unreachable"}"
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
                        Text("Testing /health...", fontSize = 12.sp)
                    } else {
                        Icon(imageVector = Icons.Default.Sync, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(Spacing.xs))
                        Text("Test Connection (/health)", fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    }
                }

                // Test Result Feedback Banner
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

                // Debug Mock Switch (Only active in debug source set)
                if (DebugMockProvider.isAvailable) {
                    HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outline)
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "DEBUG MOCK MODE",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = "Serve samples from contract_v2_samples.json without backend.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        Switch(
                            checked = isMockEnabled,
                            onCheckedChange = {
                                isMockEnabled = it
                                DebugMockProvider.isMockEnabled = it
                            }
                        )
                    }

                    if (isMockEnabled) {
                        Column(verticalArrangement = Arrangement.spacedBy(Spacing.xxs)) {
                            Text(
                                text = "ACTIVE MOCK SAMPLE",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            DebugMockProvider.sampleKeys.forEach { key ->
                                val isSelected = selectedMockKey == key
                                Surface(
                                    color = if (isSelected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
                                    shape = RoundedCornerShape(6.dp),
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
                                        color = if (isSelected) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant,
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
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
            ) {
                Text("Save", color = MaterialTheme.colorScheme.onPrimary, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    )
}

