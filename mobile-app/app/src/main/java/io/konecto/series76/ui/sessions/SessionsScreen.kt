package io.konecto.series76.ui.sessions

import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.R
import io.konecto.series76.data.ApiClient
import io.konecto.series76.ui.MainViewModel
import io.konecto.series76.ui.components.ConnectionDialog
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing
import io.konecto.series76.ui.theme.ThemeController
import kotlinx.coroutines.launch

/**
 * Esquema industrial de actuador eléctrico dibujado en Canvas
 */
@Composable
fun IndustrialActuatorSchematic(modifier: Modifier = Modifier) {
    val strokeColor = MaterialTheme.colorScheme.outline
    val accentColor = KonectoTheme.semantics.accent

    Canvas(modifier = modifier.size(100.dp)) {
        val center = Offset(size.width / 2f, size.height / 2f)

        // Carcasa principal cilíndrica del motor
        drawRoundRect(
            color = strokeColor,
            topLeft = Offset(center.x - 36.dp.toPx(), center.y - 28.dp.toPx()),
            size = Size(72.dp.toPx(), 56.dp.toPx()),
            cornerRadius = androidx.compose.ui.geometry.CornerRadius(8.dp.toPx(), 8.dp.toPx()),
            style = Stroke(width = 2.dp.toPx())
        )

        // Eje de salida superior
        drawRect(
            color = accentColor,
            topLeft = Offset(center.x - 8.dp.toPx(), center.y - 42.dp.toPx()),
            size = Size(16.dp.toPx(), 14.dp.toPx()),
            style = Stroke(width = 2.dp.toPx())
        )

        // Brida inferior (ISO 5211)
        drawLine(
            color = strokeColor,
            start = Offset(center.x - 44.dp.toPx(), center.y + 28.dp.toPx()),
            end = Offset(center.x + 44.dp.toPx(), center.y + 28.dp.toPx()),
            strokeWidth = 3.dp.toPx()
        )

        // Mirilla circular central del dial
        drawCircle(
            color = accentColor,
            radius = 12.dp.toPx(),
            center = center,
            style = Stroke(width = 2.dp.toPx())
        )

        // Aguja / Ranura de posición
        drawLine(
            color = accentColor,
            start = center,
            end = Offset(center.x + 9.dp.toPx(), center.y - 9.dp.toPx()),
            strokeWidth = 2.dp.toPx()
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class, ExperimentalLayoutApi::class)
@Composable
fun SessionsScreen(vm: MainViewModel) {
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current
    val coroutineScope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }
    var showServerDialog by remember { mutableStateOf(false) }

    val reduceMotion = remember {
        try {
            android.provider.Settings.Global.getFloat(
                context.contentResolver,
                android.provider.Settings.Global.TRANSITION_ANIMATION_SCALE,
                1.0f
            ) == 0f
        } catch (e: Exception) {
            false
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
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
                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                    Toast.makeText(
                                        context,
                                        if (vm.isDeveloperModeUnlocked) "🔧 Developer Debug Mode UNLOCKED" else "Developer Mode Hidden",
                                        Toast.LENGTH_SHORT
                                    ).show()
                                }
                            )
                        ) {
                            Text(
                                text = stringResource(R.string.sessions_title),
                                style = MaterialTheme.typography.headlineSmall,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = vm.currentUser?.let { "${it.fullName} • ${it.email}" }
                                    ?: stringResource(R.string.sessions_default_user),
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
                        IconButton(onClick = { showServerDialog = true }) {
                            Icon(
                                imageVector = Icons.Default.Settings,
                                contentDescription = stringResource(R.string.server_dialog_title),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        IconButton(onClick = { vm.loadSessions() }) {
                            Icon(
                                imageVector = Icons.Default.Refresh,
                                contentDescription = stringResource(R.string.sessions_refresh),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        IconButton(onClick = { vm.logout(context) }) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ExitToApp,
                                contentDescription = stringResource(R.string.sessions_logout),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                )
                HorizontalDivider(thickness = 1.dp, color = MaterialTheme.colorScheme.outline)
            }
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = {
                    haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                    vm.startNewConversation()
                },
                shape = RoundedCornerShape(50),
                icon = { Icon(Icons.Default.Add, contentDescription = null, tint = KonectoTheme.semantics.onAccent) },
                text = {
                    Text(
                        text = stringResource(R.string.sessions_new),
                        fontWeight = FontWeight.Bold,
                        color = KonectoTheme.semantics.onAccent,
                        letterSpacing = (-0.2).sp
                    )
                },
                containerColor = KonectoTheme.semantics.accent,
                contentColor = KonectoTheme.semantics.onAccent,
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
                    Column(modifier = Modifier.padding(Spacing.s)) {
                        Text(
                            text = vm.errorMessage!!,
                            color = KonectoTheme.semantics.errorText,
                            style = MaterialTheme.typography.bodySmall
                        )
                        Spacer(modifier = Modifier.height(Spacing.xs))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.End,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            OutlinedButton(
                                onClick = { showServerDialog = true },
                                shape = RoundedCornerShape(6.dp),
                                border = BorderStroke(1.dp, KonectoTheme.semantics.errorBorder),
                                contentPadding = PaddingValues(horizontal = Spacing.s, vertical = Spacing.xxs)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Settings,
                                    contentDescription = null,
                                    modifier = Modifier.size(14.dp),
                                    tint = KonectoTheme.semantics.errorText
                                )
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(
                                    text = stringResource(R.string.error_open_settings),
                                    color = KonectoTheme.semantics.errorText,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                            Spacer(modifier = Modifier.width(Spacing.xs))
                            Button(
                                onClick = { vm.loadSessions() },
                                shape = RoundedCornerShape(6.dp),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = MaterialTheme.colorScheme.error,
                                    contentColor = MaterialTheme.colorScheme.onError
                                ),
                                contentPadding = PaddingValues(horizontal = Spacing.s, vertical = Spacing.xxs)
                            ) {
                                Text(
                                    text = stringResource(R.string.retry),
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }
                }
            }

            if (vm.isLoading && vm.sessions.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = KonectoTheme.semantics.accent, modifier = Modifier.size(28.dp))
                }
            } else if (vm.sessions.isEmpty()) {
                // Estado vacío con ilustración Canvas y 3 sugerencias táctiles (Req 9)
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(Spacing.m),
                        modifier = Modifier.padding(horizontal = Spacing.m)
                    ) {
                        IndustrialActuatorSchematic()

                        Text(
                            text = stringResource(R.string.sessions_empty_title),
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = stringResource(R.string.sessions_empty_subtitle),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center
                        )

                        Spacer(modifier = Modifier.height(Spacing.xxs))

                        // 3 Chips de sugerencias interactivas
                        listOf(
                            stringResource(R.string.chat_suggested_1),
                            stringResource(R.string.chat_suggested_2),
                            stringResource(R.string.chat_suggested_3)
                        ).forEach { suggestion ->
                            Surface(
                                color = MaterialTheme.colorScheme.surface,
                                shape = RoundedCornerShape(10.dp),
                                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(10.dp))
                                    .clickable {
                                        haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                                        vm.startNewConversationWithQuery(suggestion)
                                    }
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 11.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text(
                                        text = suggestion,
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.Medium,
                                        color = MaterialTheme.colorScheme.onSurface,
                                        modifier = Modifier.weight(1f)
                                    )
                                    Icon(
                                        imageVector = Icons.Default.ChevronRight,
                                        contentDescription = null,
                                        tint = KonectoTheme.semantics.accent,
                                        modifier = Modifier.size(16.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(Spacing.s),
                    contentPadding = PaddingValues(bottom = 80.dp)
                ) {
                    itemsIndexed(
                        items = vm.sessions,
                        key = { _, item -> item.sessionId }
                    ) { index, session ->
                        var itemVisible by remember { mutableStateOf(reduceMotion) }
                        LaunchedEffect(Unit) {
                            if (!reduceMotion) {
                                kotlinx.coroutines.delay((index * 40L).coerceAtMost(320L))
                                itemVisible = true
                            }
                        }

                        AnimatedVisibility(
                            visible = itemVisible,
                            enter = fadeIn(animationSpec = tween(250)) +
                                    slideInVertically(
                                        initialOffsetY = { 20 },
                                        animationSpec = spring(stiffness = Spring.StiffnessMediumLow)
                                    )
                        ) {
                            // Deslizar para borrar con opción Deshacer (Req 10)
                            val dismissState = rememberSwipeToDismissBoxState(
                                confirmValueChange = { dismissValue ->
                                    if (dismissValue == SwipeToDismissBoxValue.EndToStart || dismissValue == SwipeToDismissBoxValue.StartToEnd) {
                                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                        val deletedSession = session
                                        val deletedIdx = index
                                        vm.sessions = vm.sessions.filterNot { it.sessionId == deletedSession.sessionId }

                                        coroutineScope.launch {
                                            val snackResult = snackbarHostState.showSnackbar(
                                                message = context.getString(R.string.sessions_deleted),
                                                actionLabel = context.getString(R.string.sessions_undo),
                                                duration = SnackbarDuration.Short
                                            )
                                            if (snackResult == SnackbarResult.ActionPerformed) {
                                                vm.undoDeleteSession(deletedSession, deletedIdx)
                                            } else {
                                                try {
                                                    ApiClient.api.deleteSession(deletedSession.sessionId)
                                                } catch (e: Exception) {
                                                    // ignore server delete error if offline
                                                }
                                            }
                                        }
                                        true
                                    } else false
                                }
                            )

                            SwipeToDismissBox(
                                state = dismissState,
                                backgroundContent = {
                                    val color by animateColorAsState(
                                        targetValue = when (dismissState.targetValue) {
                                            SwipeToDismissBoxValue.Settled -> Color.Transparent
                                            else -> KonectoTheme.semantics.errorBg
                                        },
                                        label = "dismissBg"
                                    )
                                    Box(
                                        modifier = Modifier
                                            .fillMaxSize()
                                            .clip(RoundedCornerShape(14.dp))
                                            .background(color)
                                            .padding(horizontal = Spacing.l),
                                        contentAlignment = Alignment.CenterEnd
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.Delete,
                                            contentDescription = stringResource(R.string.sessions_delete),
                                            tint = KonectoTheme.semantics.errorText
                                        )
                                    }
                                }
                            ) {
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
                                                text = session.shortTitle ?: session.title,
                                                style = MaterialTheme.typography.titleMedium,
                                                color = MaterialTheme.colorScheme.onSurface,
                                                maxLines = 2,
                                                overflow = TextOverflow.Ellipsis
                                            )

                                            if (session.activePartNumbers.isNotEmpty()) {
                                                FlowRow(
                                                    modifier = Modifier.fillMaxWidth(),
                                                    horizontalArrangement = Arrangement.spacedBy(Spacing.xxs),
                                                    verticalArrangement = Arrangement.spacedBy(4.dp)
                                                ) {
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
                                                                color = KonectoTheme.semantics.accentText,
                                                                fontFamily = FontFamily.Monospace,
                                                                modifier = Modifier.padding(horizontal = 7.dp, vertical = 2.dp)
                                                            )
                                                        }
                                                    }
                                                }
                                            }

                                            Text(
                                                text = "${stringResource(R.string.sessions_msgs_count, session.messageCount)} • ${session.updatedAt.take(16).replace("T", " ")}",
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant
                                            )
                                        }

                                        IconButton(
                                            onClick = {
                                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                                val deletedSession = session
                                                val deletedIdx = index
                                                vm.sessions = vm.sessions.filterNot { it.sessionId == deletedSession.sessionId }
                                                coroutineScope.launch {
                                                    val snackResult = snackbarHostState.showSnackbar(
                                                        message = context.getString(R.string.sessions_deleted),
                                                        actionLabel = context.getString(R.string.sessions_undo),
                                                        duration = SnackbarDuration.Short
                                                    )
                                                    if (snackResult == SnackbarResult.ActionPerformed) {
                                                        vm.undoDeleteSession(deletedSession, deletedIdx)
                                                    } else {
                                                        vm.deleteConversation(deletedSession.sessionId)
                                                    }
                                                }
                                            }
                                        ) {
                                            Icon(
                                                imageVector = Icons.Default.DeleteOutline,
                                                contentDescription = stringResource(R.string.sessions_delete),
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
