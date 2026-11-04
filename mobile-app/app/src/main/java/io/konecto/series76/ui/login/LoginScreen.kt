package io.konecto.series76.ui.login

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.data.ApiClient
import io.konecto.series76.ui.MainViewModel
import io.konecto.series76.ui.components.CleanInputField
import io.konecto.series76.ui.components.ConnectionDialog
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing

@Composable
fun LoginScreen(vm: MainViewModel) {
    val context = LocalContext.current
    var email by remember { mutableStateOf("engineer@konecto.io") }
    var password by remember { mutableStateOf("Konecto2026!") }
    var showServerDialog by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(Spacing.l),
        contentAlignment = Alignment.Center
    ) {
        Card(
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(16.dp))
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(Spacing.xl),
                verticalArrangement = Arrangement.spacedBy(Spacing.m)
            ) {
                // Header with settings button
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.Top
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(Spacing.xxs)) {
                        Text(
                            text = "KONECTO",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "Series 76 Assistant",
                            style = MaterialTheme.typography.headlineMedium,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = "Plant Engineering Technical Reference",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }

                    IconButton(onClick = { showServerDialog = true }) {
                        Icon(
                            imageVector = Icons.Default.Settings,
                            contentDescription = "Server Settings",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)

                // Current server indicator
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
                            text = "SERVER: ${ApiClient.baseUrl}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = "Change",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                CleanInputField(
                    label = "Corporate Identity / Email",
                    value = email,
                    onValueChange = { email = it }
                )

                CleanInputField(
                    label = "Passcode",
                    value = password,
                    onValueChange = { password = it },
                    isPassword = true
                )

                // Quick Demo Profiles
                Column(verticalArrangement = Arrangement.spacedBy(Spacing.xs)) {
                    Text(
                        text = "QUICK DEMO PROFILES",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        listOf(
                            Triple("Engineer", "engineer@konecto.io", "Konecto2026!"),
                            Triple("Supervisor", "supervisor@konecto.io", "Series76Pass!"),
                            Triple("Evaluator", "admin@konecto.io", "AdminKonecto!")
                        ).forEach { (label, userEmail, userPass) ->
                            val isSelected = email == userEmail
                            Surface(
                                color = if (isSelected) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.surfaceVariant,
                                shape = RoundedCornerShape(8.dp),
                                border = BorderStroke(
                                    1.dp,
                                    if (isSelected) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.outline
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
                                    color = if (isSelected) MaterialTheme.colorScheme.surface else MaterialTheme.colorScheme.onSurfaceVariant,
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

                // Sign In Button
                Button(
                    onClick = { vm.login(context, email, password) },
                    enabled = !vm.isLoading,
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.onSurface,
                        disabledContainerColor = MaterialTheme.colorScheme.outline
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp)
                ) {
                    if (vm.isLoading) {
                        CircularProgressIndicator(
                            color = MaterialTheme.colorScheme.surface,
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(
                            text = "Sign In",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.surface,
                            letterSpacing = (-0.2).sp
                        )
                    }
                }

                TextButton(
                    onClick = { vm.continueWithoutLogin() },
                    modifier = Modifier.align(Alignment.CenterHorizontally)
                ) {
                    Text(
                        text = "Continue in Single-User Mode",
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

