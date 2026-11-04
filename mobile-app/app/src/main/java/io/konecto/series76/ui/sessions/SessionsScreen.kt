package io.konecto.series76.ui.sessions

import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ChatBubbleOutline
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.data.ApiClient
import io.konecto.series76.ui.MainViewModel
import io.konecto.series76.ui.components.ConnectionDialog
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun SessionsScreen(vm: MainViewModel) {
    val context = LocalContext.current
    var showServerDialog by remember { mutableStateOf(false) }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            Column {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.surface,
                        titleContentColor = MaterialTheme.colorScheme.onSurface
                    ),
                    title = {
                        Column(
                            modifier = Modifier.combinedClickable(
                                onClick = {},
                                onLongClick = {
                                    vm.isDeveloperModeUnlocked = !vm.isDeveloperModeUnlocked
                                    Toast.makeText(
                                        context,
                                        if (vm.isDeveloperModeUnlocked) "🔧 Developer Debug Mode UNLOCKED" else "Developer Mode Hidden",
                                        Toast.LENGTH_SHORT
                                    ).show()
                                }
                            )
                        ) {
                            Text(
                                text = "Consultations",
                                style = MaterialTheme.typography.headlineSmall,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = vm.currentUser?.let { "${it.fullName} • ${it.email}" }
                                    ?: "Series 76 Technical Assistant",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    },
                    actions = {
                        IconButton(onClick = { showServerDialog = true }) {
                            Icon(imageVector = Icons.Default.Settings, contentDescription = "Settings", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        IconButton(onClick = { vm.loadSessions() }) {
                            Icon(imageVector = Icons.Default.Refresh, contentDescription = "Refresh", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        IconButton(onClick = { vm.logout(context) }) {
                            Icon(imageVector = Icons.AutoMirrored.Filled.ExitToApp, contentDescription = "Logout", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                )
                HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)
            }
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { vm.startNewConversation() },
                shape = RoundedCornerShape(50),
                icon = { Icon(Icons.Default.Add, contentDescription = null, tint = MaterialTheme.colorScheme.onPrimary) },
                text = {
                    Text(
                        text = "New Consultation",
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onPrimary,
                        letterSpacing = (-0.2).sp
                    )
                },
                containerColor = MaterialTheme.colorScheme.primary,
                contentColor = MaterialTheme.colorScheme.onPrimary,
                elevation = FloatingActionButtonDefaults.elevation(defaultElevation = 2.dp)
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(padding)
                .padding(horizontal = Spacing.m, vertical = Spacing.s)
        ) {
            if (vm.errorMessage != null) {
                Surface(
                    color = KonectoTheme.semantics.errorBg,
                    shape = RoundedCornerShape(10.dp),
                    border = BorderStroke(1.dp, KonectoTheme.semantics.errorBorder),
                    modifier = Modifier.fillMaxWidth().padding(bottom = Spacing.s)
                ) {
                    Row(
                        modifier = Modifier.padding(Spacing.s),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = vm.errorMessage!!,
                            color = KonectoTheme.semantics.errorText,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = { vm.loadSessions() }) {
                            Text("Retry", color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            if (vm.isLoading && vm.sessions.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(24.dp))
                }
            } else if (vm.sessions.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Default.ChatBubbleOutline,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(40.dp)
                        )
                        Spacer(modifier = Modifier.height(Spacing.xs))
                        Text(
                            text = "No consultations yet",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = "Tap 'New Consultation' to query or size actuators.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(Spacing.s),
                    contentPadding = PaddingValues(bottom = 80.dp)
                ) {
                    items(vm.sessions, key = { it.sessionId }) { session ->
                        Card(
                            shape = RoundedCornerShape(14.dp),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(14.dp))
                                .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(14.dp))
                                .clickable { vm.openConversation(session) }
                        ) {
                            Row(
                                modifier = Modifier
                                    .padding(horizontal = Spacing.m, vertical = 14.dp)
                                    .fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(
                                    modifier = Modifier.weight(1f),
                                    verticalArrangement = Arrangement.spacedBy(Spacing.xxs)
                                ) {
                                    Text(
                                        text = session.title,
                                        style = MaterialTheme.typography.titleMedium,
                                        color = MaterialTheme.colorScheme.onSurface,
                                        maxLines = 2,
                                        overflow = TextOverflow.Ellipsis
                                    )

                                    if (session.activePartNumbers.isNotEmpty()) {
                                        Row(horizontalArrangement = Arrangement.spacedBy(Spacing.xxs)) {
                                            session.activePartNumbers.forEach { pn ->
                                                Surface(
                                                    color = MaterialTheme.colorScheme.surfaceVariant,
                                                    shape = RoundedCornerShape(6.dp),
                                                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline)
                                                ) {
                                                    Text(
                                                        text = pn,
                                                        fontSize = 10.sp,
                                                        fontWeight = FontWeight.Bold,
                                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                        fontFamily = FontFamily.Monospace,
                                                        modifier = Modifier.padding(horizontal = 7.dp, vertical = 2.dp)
                                                    )
                                                }
                                            }
                                        }
                                    }

                                    Text(
                                        text = "${session.messageCount} msgs • ${session.updatedAt.take(16).replace("T", " ")}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }

                                IconButton(onClick = { vm.deleteConversation(session.sessionId) }) {
                                    Icon(
                                        imageVector = Icons.Default.DeleteOutline,
                                        contentDescription = "Delete",
                                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
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

