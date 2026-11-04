package io.konecto.series76.ui

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import io.konecto.series76.data.*
import kotlinx.coroutines.launch

enum class AppScreen {
    LOGIN, SESSIONS, CHAT, DEBUG
}

class MainViewModel : ViewModel() {
    var currentScreen by mutableStateOf(AppScreen.LOGIN)
    var currentUser by mutableStateOf<UserInfo?>(null)
    var isLoading by mutableStateOf(false)
    var errorMessage by mutableStateOf<String?>(null)

    // Lista de conversaciones y conversación activa
    var sessions by mutableStateOf<List<SessionSummary>>(emptyList())
    var activeSessionId by mutableStateOf<String?>(null)
    var activeSessionTitle by mutableStateOf("New Actuator Consultation")
    var messages by mutableStateOf<List<MessageRecord>>(emptyList())

    // Modo Desarrollador (Pantalla Debug oculta por Long-Press para evaluadores/devs)
    var isDeveloperModeUnlocked by mutableStateOf(false)

    fun initPrefs(context: Context) {
        val prefs = context.getSharedPreferences("konecto_prefs", Context.MODE_PRIVATE)
        val savedUrl = prefs.getString("base_url", "http://10.0.2.2:8001/") ?: "http://10.0.2.2:8001/"
        ApiClient.baseUrl = savedUrl
        val savedToken = prefs.getString("auth_token", null)
        val savedEmail = prefs.getString("user_email", null)
        val savedName = prefs.getString("user_name", null)
        if (!savedToken.isNullOrBlank() && !savedEmail.isNullOrBlank()) {
            ApiClient.authToken = savedToken
            currentUser = UserInfo(id = "", email = savedEmail, fullName = savedName ?: savedEmail, role = "engineer")
            currentScreen = AppScreen.SESSIONS
            loadSessions()
        }
    }

    fun updateServerUrl(context: Context, newUrl: String) {
        var cleanUrl = newUrl.trim()
        if (!cleanUrl.startsWith("http://") && !cleanUrl.startsWith("https://")) {
            cleanUrl = "http://$cleanUrl"
        }
        ApiClient.baseUrl = cleanUrl
        context.getSharedPreferences("konecto_prefs", Context.MODE_PRIVATE)
            .edit().putString("base_url", ApiClient.baseUrl).apply()
        errorMessage = null
    }

    fun login(context: Context, email: String, password: String) {
        viewModelScope.launch {
            isLoading = true
            errorMessage = null
            try {
                val resp = ApiClient.api.login(LoginRequest(email.trim(), password))
                ApiClient.authToken = resp.token
                currentUser = resp.user
                context.getSharedPreferences("konecto_prefs", Context.MODE_PRIVATE).edit()
                    .putString("auth_token", resp.token)
                    .putString("user_email", resp.user.email)
                    .putString("user_name", resp.user.fullName)
                    .apply()
                currentScreen = AppScreen.SESSIONS
                loadSessions()
            } catch (e: Exception) {
                errorMessage = "Login failed: ${e.localizedMessage ?: "Cannot connect to ${ApiClient.baseUrl}"}"
            } finally {
                isLoading = false
            }
        }
    }

    fun continueWithoutLogin() {
        ApiClient.authToken = null
        currentUser = null
        currentScreen = AppScreen.SESSIONS
        loadSessions()
    }

    fun logout(context: Context) {
        ApiClient.authToken = null
        currentUser = null
        sessions = emptyList()
        messages = emptyList()
        activeSessionId = null
        context.getSharedPreferences("konecto_prefs", Context.MODE_PRIVATE).edit().clear().apply()
        currentScreen = AppScreen.LOGIN
    }

    fun loadSessions() {
        viewModelScope.launch {
            isLoading = true
            errorMessage = null
            try {
                sessions = ApiClient.api.getSessions()
            } catch (e: Exception) {
                errorMessage = "Could not load conversations (${ApiClient.baseUrl}): ${e.localizedMessage}"
            } finally {
                isLoading = false
            }
        }
    }

    fun startNewConversation() {
        activeSessionId = null
        activeSessionTitle = "New Series 76 Consultation"
        messages = emptyList()
        errorMessage = null
        currentScreen = AppScreen.CHAT
    }

    fun openConversation(session: SessionSummary) {
        viewModelScope.launch {
            isLoading = true
            errorMessage = null
            activeSessionId = session.sessionId
            activeSessionTitle = session.title
            currentScreen = AppScreen.CHAT
            try {
                val history = ApiClient.api.getSessionHistory(session.sessionId)
                messages = history.messages
            } catch (e: Exception) {
                errorMessage = "Error loading conversation history: ${e.localizedMessage}"
            } finally {
                isLoading = false
            }
        }
    }

    fun deleteConversation(sessionId: String) {
        viewModelScope.launch {
            try {
                ApiClient.api.deleteSession(sessionId)
                sessions = sessions.filterNot { it.sessionId == sessionId }
                if (activeSessionId == sessionId) {
                    activeSessionId = null
                    messages = emptyList()
                    activeSessionTitle = "New Actuator Consultation"
                }
            } catch (e: Exception) {
                errorMessage = "Could not delete session: ${e.localizedMessage}"
            }
        }
    }

    fun sendUserMessage(queryText: String) {
        val cleanQuery = queryText.trim()
        if (cleanQuery.isEmpty() || isLoading) return

        // 1. Añadir el mensaje del usuario de inmediato en la UI
        val tempUserMsg = MessageRecord(
            id = (messages.size + 1) * -1,
            role = "user",
            content = cleanQuery
        )
        messages = messages + tempUserMsg

        // 2. Enviar al backend FastAPI y recibir respuesta + ui_payload + debug_trace
        viewModelScope.launch {
            isLoading = true
            errorMessage = null
            try {
                val resp = ApiClient.api.sendMessage(
                    ConversationRequest(sessionId = activeSessionId, query = cleanQuery)
                )
                activeSessionId = resp.sessionId
                if (messages.size <= 1) {
                    activeSessionTitle = cleanQuery.take(50)
                }
                val assistantMsg = MessageRecord(
                    id = messages.size + 1,
                    role = "assistant",
                    content = resp.answer,
                    uiPayload = resp.uiPayload,
                    debugTrace = resp.debugTrace
                )
                messages = messages + assistantMsg
            } catch (e: Exception) {
                errorMessage = "Backend error or timeout: ${e.localizedMessage ?: e.javaClass.simpleName}"
            } finally {
                isLoading = false
            }
        }
    }
}
