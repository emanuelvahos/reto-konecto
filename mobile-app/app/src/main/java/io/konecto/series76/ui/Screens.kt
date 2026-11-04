package io.konecto.series76.ui

import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.data.ApiClient
import io.konecto.series76.data.MessageRecord
import io.konecto.series76.util.VoiceNormalizer
import java.util.Locale

// =====================================================================
// PANTALLA 1: LOGIN SCREEN — SWISS INDUSTRIAL / LINEAR STYLE
// =====================================================================
@Composable
fun LoginScreen(vm: MainViewModel) {
    val context = LocalContext.current
    var email by remember { mutableStateOf("engineer@konecto.io") }
    var password by remember { mutableStateOf("Konecto2026!") }
    var serverUrl by remember { mutableStateOf(ApiClient.baseUrl) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFFF7F7F5))
            .padding(20.dp),
        contentAlignment = Alignment.Center
    ) {
        Card(
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = Color.White),
            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, Color(0xFFE4E4E7), RoundedCornerShape(16.dp))
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Cabecera sobria y corporativa
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        text = "KONECTO",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF71717A),
                        letterSpacing = 1.2.sp
                    )
                    Text(
                        text = "Series 76 Assistant",
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF18181B),
                        letterSpacing = (-0.4).sp
                    )
                    Text(
                        text = "Plant Engineering Technical Reference",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Normal,
                        color = Color(0xFF71717A)
                    )
                }

                HorizontalDivider(thickness = 1.dp, color = Color(0xFFE4E4E7))

                // Campos limpios con fondo gris piedra sutil
                CleanInputField(
                    label = "BACKEND ENDPOINT",
                    value = serverUrl,
                    onValueChange = {
                        serverUrl = it
                        vm.updateServerUrl(context, it)
                    }
                )

                CleanInputField(
                    label = "CORPORATE IDENTITY / EMAIL",
                    value = email,
                    onValueChange = { email = it }
                )

                CleanInputField(
                    label = "PASSCODE",
                    value = password,
                    onValueChange = { password = it },
                    isPassword = true
                )

                // Quick Demo Profiles
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        text = "QUICK DEMO PROFILES",
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF71717A),
                        letterSpacing = 0.8.sp
                    )
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        listOf(
                            Triple("Engineer", "engineer@konecto.io", "Konecto2026!"),
                            Triple("Supervisor", "supervisor@konecto.io", "Series76Pass!"),
                            Triple("Evaluator", "admin@konecto.io", "AdminKonecto!")
                        ).forEach { (label, userEmail, userPass) ->
                            val isSelected = email == userEmail
                            Surface(
                                color = if (isSelected) Color(0xFF18181B) else Color(0xFFF4F4F5),
                                shape = RoundedCornerShape(8.dp),
                                border = androidx.compose.foundation.BorderStroke(
                                    1.dp,
                                    if (isSelected) Color(0xFF18181B) else Color(0xFFE4E4E7)
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
                                    color = if (isSelected) Color.White else Color(0xFF3F3F46),
                                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                                )
                            }
                        }
                    }
                }

                if (vm.errorMessage != null) {
                    Surface(
                        color = Color(0xFFFEF2F2),
                        shape = RoundedCornerShape(8.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFFECACA)),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = vm.errorMessage!!,
                            color = Color(0xFFB91C1C),
                            fontSize = 12.sp,
                            modifier = Modifier.padding(10.dp)
                        )
                    }
                }

                // Botón Sign In en Grafito Elegante
                Button(
                    onClick = { vm.login(context, email, password) },
                    enabled = !vm.isLoading,
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFF18181B),
                        disabledContainerColor = Color(0xFFE4E4E7)
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp)
                ) {
                    if (vm.isLoading) {
                        CircularProgressIndicator(
                            color = Color.White,
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(
                            text = "Sign In",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White,
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
                        color = Color(0xFF71717A),
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }
    }
}

/**
 * Campo de texto limpio con etiqueta superior
 */
@Composable
fun CleanInputField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    isPassword: Boolean = false
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            text = label,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            color = Color(0xFF71717A),
            letterSpacing = 0.6.sp
        )
        TextField(
            value = value,
            onValueChange = onValueChange,
            singleLine = true,
            visualTransformation = if (isPassword) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
            shape = RoundedCornerShape(10.dp),
            colors = TextFieldDefaults.colors(
                focusedContainerColor = Color(0xFFF4F4F5),
                unfocusedContainerColor = Color(0xFFF4F4F5),
                focusedIndicatorColor = Color.Transparent,
                unfocusedIndicatorColor = Color.Transparent,
                disabledIndicatorColor = Color.Transparent,
                cursorColor = Color(0xFF18181B),
                focusedTextColor = Color(0xFF18181B),
                unfocusedTextColor = Color(0xFF18181B)
            ),
            textStyle = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.Medium),
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, Color(0xFFE4E4E7), RoundedCornerShape(10.dp))
        )
    }
}

// =====================================================================
// PANTALLA 2: SESSIONS SCREEN — INSET GROUPED / SWISS INDUSTRIAL
// =====================================================================
@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun SessionsScreen(vm: MainViewModel) {
    val context = LocalContext.current

    Scaffold(
        containerColor = Color(0xFFF7F7F5),
        topBar = {
            Column {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.White,
                        titleContentColor = Color(0xFF18181B)
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
                                fontWeight = FontWeight.Bold,
                                fontSize = 20.sp,
                                color = Color(0xFF18181B),
                                letterSpacing = (-0.4).sp
                            )
                            Text(
                                text = vm.currentUser?.let { "${it.fullName} • ${it.email}" }
                                    ?: "Series 76 Technical Assistant",
                                fontSize = 11.sp,
                                color = Color(0xFF71717A)
                            )
                        }
                    },
                    actions = {
                        IconButton(onClick = { vm.loadSessions() }) {
                            Icon(imageVector = Icons.Default.Refresh, contentDescription = "Refresh", tint = Color(0xFF71717A))
                        }
                        IconButton(onClick = { vm.logout(context) }) {
                            Icon(imageVector = Icons.AutoMirrored.Filled.ExitToApp, contentDescription = "Logout", tint = Color(0xFF71717A))
                        }
                    }
                )
                HorizontalDivider(thickness = 1.dp, color = Color(0xFFE4E4E7))
            }
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { vm.startNewConversation() },
                shape = RoundedCornerShape(50),
                icon = { Icon(Icons.Default.Add, contentDescription = null, tint = Color.White) },
                text = {
                    Text(
                        text = "New Consultation",
                        fontWeight = FontWeight.Bold,
                        color = Color.White,
                        letterSpacing = (-0.2).sp
                    )
                },
                containerColor = Color(0xFF2563EB),
                contentColor = Color.White,
                elevation = FloatingActionButtonDefaults.elevation(defaultElevation = 2.dp)
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFFF7F7F5))
                .padding(padding)
                .padding(horizontal = 16.dp, vertical = 12.dp)
        ) {
            if (vm.errorMessage != null) {
                Surface(
                    color = Color(0xFFFEF2F2),
                    shape = RoundedCornerShape(10.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFFECACA)),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(text = vm.errorMessage!!, color = Color(0xFFB91C1C), fontSize = 12.sp, modifier = Modifier.weight(1f))
                        TextButton(onClick = { vm.loadSessions() }) {
                            Text("Retry", color = Color(0xFF18181B), fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            if (vm.isLoading && vm.sessions.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Color(0xFF71717A), modifier = Modifier.size(24.dp))
                }
            } else if (vm.sessions.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(imageVector = Icons.Default.ChatBubbleOutline, contentDescription = null, tint = Color(0xFF71717A), modifier = Modifier.size(40.dp))
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(text = "No consultations yet", fontWeight = FontWeight.Bold, fontSize = 15.sp, color = Color(0xFF18181B))
                        Text(text = "Tap 'New Consultation' to query or size actuators.", fontSize = 13.sp, color = Color(0xFF71717A))
                    }
                }
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    contentPadding = PaddingValues(bottom = 80.dp)
                ) {
                    items(vm.sessions, key = { it.sessionId }) { session ->
                        Card(
                            shape = RoundedCornerShape(14.dp),
                            colors = CardDefaults.cardColors(containerColor = Color.White),
                            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(14.dp))
                                .border(1.dp, Color(0xFFE4E4E7), RoundedCornerShape(14.dp))
                                .clickable { vm.openConversation(session) }
                        ) {
                            Row(
                                modifier = Modifier
                                    .padding(horizontal = 16.dp, vertical = 14.dp)
                                    .fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(
                                    modifier = Modifier.weight(1f),
                                    verticalArrangement = Arrangement.spacedBy(6.dp)
                                ) {
                                    Text(
                                        text = session.title,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 15.sp,
                                        color = Color(0xFF18181B),
                                        letterSpacing = (-0.3).sp,
                                        maxLines = 2,
                                        overflow = TextOverflow.Ellipsis
                                    )

                                    if (session.activePartNumbers.isNotEmpty()) {
                                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                            session.activePartNumbers.forEach { pn ->
                                                Surface(
                                                    color = Color(0xFFF4F4F5),
                                                    shape = RoundedCornerShape(6.dp),
                                                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFE4E4E7))
                                                ) {
                                                    Text(
                                                        text = pn,
                                                        fontSize = 10.sp,
                                                        fontWeight = FontWeight.Bold,
                                                        color = Color(0xFF3F3F46),
                                                        fontFamily = FontFamily.Monospace,
                                                        modifier = Modifier.padding(horizontal = 7.dp, vertical = 2.dp)
                                                    )
                                                }
                                            }
                                        }
                                    }

                                    Text(
                                        text = "${session.messageCount} msgs • ${session.updatedAt.take(16).replace("T", " ")}",
                                        fontSize = 11.sp,
                                        color = Color(0xFF71717A)
                                    )
                                }

                                IconButton(onClick = { vm.deleteConversation(session.sessionId) }) {
                                    Icon(imageVector = Icons.Default.DeleteOutline, contentDescription = "Delete", tint = Color(0xFFA1A1AA))
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

// =====================================================================
// PANTALLA 3: CHAT SCREEN — BURBUJAS SOBRIAS & CARGA NATURAL
// =====================================================================
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
        containerColor = Color(0xFFF7F7F5),
        topBar = {
            Column {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.White,
                        titleContentColor = Color(0xFF18181B)
                    ),
                    navigationIcon = {
                        IconButton(onClick = {
                            vm.currentScreen = AppScreen.SESSIONS
                            vm.loadSessions()
                        }) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBackIos,
                                contentDescription = "Back",
                                tint = Color(0xFF18181B),
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
                                horizontalArrangement = Arrangement.spacedBy(6.dp)
                            ) {
                                Text(
                                    text = vm.activeSessionTitle,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                    fontSize = 15.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF18181B),
                                    letterSpacing = (-0.3).sp,
                                    modifier = Modifier.weight(1f, fill = false)
                                )
                                if (activePart != null) {
                                    Surface(
                                        color = Color(0xFFF4F4F5),
                                        shape = RoundedCornerShape(4.dp),
                                        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFE4E4E7))
                                    ) {
                                        Text(
                                            text = activePart,
                                            fontSize = 10.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = Color(0xFF3F3F46),
                                            fontFamily = FontFamily.Monospace,
                                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                        )
                                    }
                                }
                            }
                            Text(
                                text = "Series 76 Technical Assistant",
                                fontSize = 11.sp,
                                color = Color(0xFF71717A)
                            )
                        }
                    },
                    actions = {
                        if (vm.isDeveloperModeUnlocked) {
                            IconButton(onClick = { vm.currentScreen = AppScreen.DEBUG }) {
                                Icon(
                                    imageVector = Icons.Default.Terminal,
                                    contentDescription = "Open Developer Debug Screen",
                                    tint = Color(0xFF18181B)
                                )
                            }
                        }
                    }
                )
                HorizontalDivider(thickness = 1.dp, color = Color(0xFFE4E4E7))
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFFF7F7F5))
                .padding(padding)
        ) {
            if (vm.errorMessage != null) {
                Surface(
                    color = Color(0xFFFEF2F2),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFFECACA)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = "⚠️ ${vm.errorMessage}",
                        color = Color(0xFFB91C1C),
                        fontSize = 12.sp,
                        modifier = Modifier.padding(10.dp)
                    )
                }
            }

            // Quick Suggestions when chat is empty
            if (vm.messages.isEmpty() && !vm.isLoading) {
                Column(
                    modifier = Modifier.padding(16.dp).fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        text = "SUGGESTED ENGINEERING QUERIES",
                        fontWeight = FontWeight.Bold,
                        fontSize = 11.sp,
                        color = Color(0xFF71717A),
                        letterSpacing = 0.8.sp
                    )
                    listOf(
                        "Specs for Base Part Number 763B00-11300000/A",
                        "Recommend an Explosionproof actuator with at least 200 Nm Modulating torque on 24V DC",
                        "Compare 110V single phase Weatherproof models between 500 Nm and 1100 Nm",
                        "Is 761A00-11330000/A available in 220V 3-Phase?"
                    ).forEach { sample ->
                        Surface(
                            color = Color.White,
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .border(1.dp, Color(0xFFE4E4E7), RoundedCornerShape(12.dp))
                                .clickable { vm.sendUserMessage(sample) }
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = sample,
                                    fontSize = 13.sp,
                                    color = Color(0xFF18181B),
                                    fontWeight = FontWeight.Medium,
                                    modifier = Modifier.weight(1f)
                                )
                                Icon(imageVector = Icons.Default.ChevronRight, contentDescription = null, tint = Color(0xFFA1A1AA), modifier = Modifier.size(18.dp))
                            }
                        }
                    }
                }
            }

            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = PaddingValues(vertical = 14.dp)
            ) {
                items(vm.messages, key = { it.id }) { msg ->
                    ChatBubbleItem(msg = msg)
                }
                if (vm.isLoading) {
                    item(key = "loading_indicator") {
                        Surface(
                            color = Color.White,
                            shape = RoundedCornerShape(16.dp),
                            modifier = Modifier.border(1.dp, Color(0xFFE4E4E7), RoundedCornerShape(16.dp))
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(14.dp),
                                    strokeWidth = 2.dp,
                                    color = Color(0xFF71717A)
                                )
                                Text(
                                    text = "Thinking...",
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Medium,
                                    color = Color(0xFF71717A)
                                )
                            }
                        }
                    }
                }
            }

            // Barra de entrada inferior limpia
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color.White)
            ) {
                HorizontalDivider(thickness = 1.dp, color = Color(0xFFE4E4E7))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 10.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(Color(0xFFF4F4F5))
                            .border(1.dp, Color(0xFFE4E4E7), CircleShape)
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
                        Icon(imageVector = Icons.Default.Mic, contentDescription = "Voice Input", tint = Color(0xFF71717A), modifier = Modifier.size(18.dp))
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(20.dp))
                            .background(Color(0xFFF4F4F5))
                            .border(1.dp, Color(0xFFE4E4E7), RoundedCornerShape(20.dp))
                            .padding(horizontal = 14.dp, vertical = 10.dp),
                        contentAlignment = Alignment.CenterStart
                    ) {
                        if (inputText.isEmpty()) {
                            Text(text = "Ask part number, torque, or 50Hz...", fontSize = 14.sp, color = Color(0xFFA1A1AA))
                        }
                        BasicTextField(
                            value = inputText,
                            onValueChange = { inputText = it },
                            textStyle = TextStyle(fontSize = 14.sp, color = Color(0xFF18181B)),
                            cursorBrush = SolidColor(Color(0xFF18181B)),
                            maxLines = 4,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }

                    val canSend = inputText.isNotBlank() && !vm.isLoading
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(if (canSend) Color(0xFF2563EB) else Color(0xFFE4E4E7))
                            .clickable(enabled = canSend) {
                                val q = inputText
                                inputText = ""
                                vm.sendUserMessage(q)
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(imageVector = Icons.Default.ArrowUpward, contentDescription = "Send", tint = Color.White, modifier = Modifier.size(18.dp))
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
        containerColor = Color.White,
        title = {
            Text(text = "🎙️ Voice & Technical Normalizer", fontSize = 17.sp, fontWeight = FontWeight.Bold, color = Color(0xFF18181B))
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = "Select or type spoken English/Spanish words. VoiceNormalizer will deterministically resolve exact Series 76 codes:",
                    fontSize = 12.sp,
                    color = Color(0xFF71717A)
                )

                listOf(
                    "seven six three B zero zero dash one one three zero zero zero zero zero slash A",
                    "siete seis tres be cero cero guion uno uno tres cero cero cero cero cero barra A"
                ).forEach { sample ->
                    Surface(
                        color = Color(0xFFF4F4F5),
                        shape = RoundedCornerShape(8.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFE4E4E7)),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .clickable { customText = sample }
                    ) {
                        Text(text = sample, fontSize = 11.sp, color = Color(0xFF18181B), modifier = Modifier.padding(8.dp))
                    }
                }

                TextField(
                    value = customText,
                    onValueChange = { customText = it },
                    label = { Text("Spoken Technical Input") },
                    shape = RoundedCornerShape(8.dp),
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = Color(0xFFF4F4F5),
                        unfocusedContainerColor = Color(0xFFF4F4F5),
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent
                    ),
                    modifier = Modifier.fillMaxWidth()
                )

                Surface(
                    color = Color(0xFFF4F4F5),
                    shape = RoundedCornerShape(8.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFE4E4E7)),
                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp)
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Text(text = "NORMALIZED PART NUMBER OUTPUT", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = Color(0xFF71717A))
                        Text(text = normalizedPreview, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF18181B), fontFamily = FontFamily.Monospace)
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onSendNormalizedQuery(customText) },
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF18181B)),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text("Normalize & Send", color = Color.White, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel", color = Color(0xFF71717A))
            }
        }
    )
}

/**
 * Parser Markdown ultra-ligero que filtra listas verticales de viñetas redundantes
 */
fun parseCleanMarkdown(text: String): AnnotatedString {
    val cleanedLines = mutableListOf<String>()
    for (rawLine in text.lines()) {
        val trimmed = rawLine.trim()
        if (trimmed.startsWith("|") && trimmed.endsWith("|")) continue
        val withoutHeader = trimmed.replace(Regex("""^#{1,6}\s+"""), "")
        cleanedLines.add(withoutHeader)
    }

    val normalizedText = cleanedLines
        .joinToString("\n")
        .replace(Regex("""\n{3,}"""), "\n\n")
        .trim()

    val finalSource = normalizedText.ifEmpty { text.replace("**", "").replace("`", "").trim() }

    return buildAnnotatedString {
        val tokenRegex = Regex("""\*\*(.+?)\*\*|`([^`]+)`|\*([^\*\n]+)\*""", RegexOption.DOT_MATCHES_ALL)
        var lastIndex = 0
        for (match in tokenRegex.findAll(finalSource)) {
            val range = match.range
            if (range.first > lastIndex) {
                append(finalSource.substring(lastIndex, range.first))
            }
            val boldGroup = match.groups[1]?.value
            val codeGroup = match.groups[2]?.value
            val italicGroup = match.groups[3]?.value

            when {
                boldGroup != null -> {
                    withStyle(style = SpanStyle(fontWeight = FontWeight.Bold, color = Color(0xFF18181B))) {
                        append(boldGroup)
                    }
                }
                codeGroup != null -> {
                    withStyle(
                        style = SpanStyle(
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            background = Color(0xFFF4F4F5),
                            color = Color(0xFF18181B)
                        )
                    ) {
                        append(" $codeGroup ")
                    }
                }
                italicGroup != null -> {
                    withStyle(style = SpanStyle(fontStyle = FontStyle.Italic)) {
                        append(italicGroup)
                    }
                }
            }
            lastIndex = range.last + 1
        }
        if (lastIndex < finalSource.length) {
            append(finalSource.substring(lastIndex))
        }
    }
}

fun formatMarkdownBold(text: String): AnnotatedString = parseCleanMarkdown(text)

@Composable
fun ChatBubbleItem(msg: MessageRecord) {
    val isUser = msg.role == "user"
    val bubbleShape = if (isUser) {
        RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 16.dp, bottomEnd = 4.dp)
    } else {
        RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 4.dp, bottomEnd = 16.dp)
    }

    val formattedContent = remember(msg.content, isUser) {
        if (isUser) AnnotatedString(msg.content) else parseCleanMarkdown(msg.content)
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        if (formattedContent.text.isNotBlank()) {
            Box(
                modifier = Modifier
                    .widthIn(max = 340.dp)
                    .clip(bubbleShape)
                    .then(
                        if (isUser) {
                            Modifier.background(Color(0xFF2563EB))
                        } else {
                            Modifier
                                .background(Color.White)
                                .border(1.dp, Color(0xFFE4E4E7), bubbleShape)
                        }
                    )
            ) {
                Text(
                    text = formattedContent,
                    color = if (isUser) Color.White else Color(0xFF18181B),
                    fontSize = 14.sp,
                    lineHeight = 20.sp,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)
                )
            }
        }

        if (!isUser && msg.uiPayload != null) {
            ProductDataVisualizer(
                uiPayload = msg.uiPayload,
                contextText = msg.content
            )
        }
    }
}

// =====================================================================
// PANTALLA 4: DEVELOPER X-RAY DEBUG SCREEN
// =====================================================================
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DebugScreen(vm: MainViewModel) {
    val assistantMessages = remember(vm.messages) {
        vm.messages.filter { it.role == "assistant" && it.debugTrace != null }.reversed()
    }

    Scaffold(
        containerColor = Color(0xFFF7F7F5),
        topBar = {
            Column {
                TopAppBar(
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.White,
                        titleContentColor = Color(0xFF18181B)
                    ),
                    navigationIcon = {
                        IconButton(onClick = { vm.currentScreen = AppScreen.CHAT }) {
                            Icon(imageVector = Icons.AutoMirrored.Filled.ArrowBackIos, contentDescription = "Back", tint = Color(0xFF18181B), modifier = Modifier.size(18.dp))
                        }
                    },
                    title = {
                        Column {
                            Text(text = "X-Ray Telemetry Inspector", fontWeight = FontWeight.Bold, fontSize = 17.sp, color = Color(0xFF18181B), letterSpacing = (-0.3).sp)
                            Text(text = "Tools invoked, parameters, SQL & PostgreSQL output", fontSize = 11.sp, color = Color(0xFF71717A), fontWeight = FontWeight.Normal)
                        }
                    }
                )
                HorizontalDivider(thickness = 1.dp, color = Color(0xFFE4E4E7))
            }
        }
    ) { padding ->
        if (assistantMessages.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                Text(text = "No agent answers with debug telemetry in this session yet.", color = Color(0xFF71717A))
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 14.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
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
                        color = Color(0xFF1C1C1E),
                        modifier = Modifier.fillMaxWidth().border(1.dp, Color(0xFF2C2C2E), RoundedCornerShape(14.dp))
                    ) {
                        Column(
                            modifier = Modifier.padding(14.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text(text = "Answer Preview: \"$cleanPreview...\"", color = Color(0xFFAEAEB2), fontSize = 12.sp, lineHeight = 16.sp)
                            Text(
                                text = "Model: ${trace.modelUsed} | Total Latency: ${trace.totalLatencyMs} ms",
                                color = Color(0xFF38BDF8),
                                fontFamily = FontFamily.Monospace,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "Active Context Part Numbers: ${trace.activeContextPartNumbers.joinToString(", ").ifEmpty { "None" }}",
                                color = Color(0xFF4ADE80),
                                fontFamily = FontFamily.Monospace,
                                fontSize = 11.sp
                            )
                            Text(
                                text = "Token Usage: ${trace.tokenUsage}",
                                color = Color(0xFFFDE68A),
                                fontFamily = FontFamily.Monospace,
                                fontSize = 11.sp
                            )

                            HorizontalDivider(thickness = 0.5.dp, color = Color(0xFF38383A))

                            if (trace.toolCalls.isEmpty()) {
                                Text(text = "No LangChain tools invoked in this turn.", color = Color(0xFFFF453A), fontSize = 12.sp)
                            } else {
                                trace.toolCalls.forEachIndexed { idx, tc ->
                                    Column(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .background(Color(0xFF2C2C2E), RoundedCornerShape(8.dp))
                                            .padding(10.dp),
                                        verticalArrangement = Arrangement.spacedBy(4.dp)
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

