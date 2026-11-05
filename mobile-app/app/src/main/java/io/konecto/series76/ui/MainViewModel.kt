package io.konecto.series76.ui

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import io.konecto.series76.data.*
import io.konecto.series76.mock.DebugMockProvider
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
    var lastUserQuery by mutableStateOf<String?>(null)

    // Modo Desarrollador (Pantalla Debug oculta por Long-Press para evaluadores/devs)
    var isDeveloperModeUnlocked by mutableStateOf(false)

    private var appContext: Context? = null

    fun initPrefs(context: Context) {
        appContext = context.applicationContext
        viewModelScope.launch {
            val savedUrl = ServerPreferences.getServerUrlSync(context)
            ApiClient.baseUrl = savedUrl

            val (savedToken, savedEmail, savedName) = ServerPreferences.getSavedAuth(context)
            if (!savedToken.isNullOrBlank() && !savedEmail.isNullOrBlank()) {
                ApiClient.authToken = savedToken
                currentUser = UserInfo(id = "", email = savedEmail, fullName = savedName ?: savedEmail, role = "engineer")
                currentScreen = AppScreen.SESSIONS
                loadSessions()
            }
        }
    }

    fun updateServerUrl(context: Context, newUrl: String) {
        viewModelScope.launch {
            ServerPreferences.setServerUrl(context, newUrl)
            errorMessage = null
        }
    }

    fun login(context: Context, email: String, password: String) {
        viewModelScope.launch {
            isLoading = true
            errorMessage = null
            try {
                val resp = ApiClient.api.login(LoginRequest(email.trim(), password))
                ApiClient.authToken = resp.token
                currentUser = resp.user
                ServerPreferences.saveAuth(context, resp.token, resp.user.email, resp.user.fullName)
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
        viewModelScope.launch {
            ServerPreferences.clearAuth(context)
            currentUser = null
            sessions = emptyList()
            messages = emptyList()
            activeSessionId = null
            currentScreen = AppScreen.LOGIN
        }
    }

    fun loadSessions() {
        viewModelScope.launch {
            isLoading = true
            errorMessage = null
            try {
                if (DebugMockProvider.isMockEnabled) {
                    sessions = emptyList()
                } else {
                    sessions = ApiClient.api.getSessions()
                }
            } catch (e: Exception) {
                errorMessage = "Could not load conversations (${ApiClient.baseUrl}): ${e.localizedMessage}"
            } finally {
                isLoading = false
            }
        }
    }

    fun startNewConversation() {
        activeSessionId = null
        activeSessionTitle = "Series 76"
        messages = emptyList()
        errorMessage = null
        currentScreen = AppScreen.CHAT
    }

    fun startNewConversationWithQuery(query: String) {
        val clean = query.trim()
        activeSessionId = null
        activeSessionTitle = clean.take(28)
        messages = emptyList()
        errorMessage = null
        currentScreen = AppScreen.CHAT
        sendUserMessage(clean)
    }

    fun openConversation(session: SessionSummary) {
        viewModelScope.launch {
            isLoading = true
            errorMessage = null
            activeSessionId = session.sessionId
            activeSessionTitle = session.shortTitle?.take(28) ?: session.title.take(28)
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
                    activeSessionTitle = "Series 76"
                }
            } catch (e: Exception) {
                errorMessage = "Could not delete session: ${e.localizedMessage}"
            }
        }
    }

    fun undoDeleteSession(session: SessionSummary, index: Int) {
        val mutable = sessions.toMutableList()
        val safeIdx = index.coerceIn(0, mutable.size)
        mutable.add(safeIdx, session)
        sessions = mutable
    }

    fun setSimulatedLoading(enable: Boolean) {
        isLoading = enable
    }

    fun retryLastMessage() {
        val query = lastUserQuery ?: return
        errorMessage = null
        sendUserMessage(query, isRetry = true)
    }

    fun sendUserMessage(queryText: String, isRetry: Boolean = false) {
        val cleanQuery = queryText.trim()
        if (cleanQuery.isEmpty() || isLoading) return
        lastUserQuery = cleanQuery

        // 1. Añadir el mensaje del usuario solo si no es un reintento
        if (!isRetry) {
            val tempUserMsg = MessageRecord(
                id = (messages.size + 1) * -1,
                role = "user",
                content = cleanQuery
            )
            messages = messages + tempUserMsg
        }

        // 2. Si está activo el modo mock de depuración, servir respuesta local de contract_v2_samples.json
        viewModelScope.launch {
            isLoading = true
            errorMessage = null

            if (DebugMockProvider.isMockEnabled && appContext != null) {
                val mockResp = DebugMockProvider.getMockResponse(appContext!!, cleanQuery)
                if (mockResp != null) {
                    val delayMs = if (cleanQuery.contains("loading", ignoreCase = true) || cleanQuery.contains("skeleton", ignoreCase = true)) 10000L else 400L
                    kotlinx.coroutines.delay(delayMs)
                    activeSessionId = mockResp.sessionId
                    if (messages.size <= 1) {
                        activeSessionTitle = cleanQuery.take(28)
                    }
                    val assistantMsg = MessageRecord(
                        id = messages.size + 1,
                        role = "assistant",
                        content = mockResp.answer,
                        uiPayload = mockResp.uiPayload,
                        debugTrace = mockResp.debugTrace
                    )
                    messages = messages + assistantMsg
                    isLoading = false
                    return@launch
                }
            }

            // Flujo normal contra backend FastAPI
            try {
                val resp = ApiClient.api.sendMessage(
                    ConversationRequest(sessionId = activeSessionId, query = cleanQuery)
                )
                activeSessionId = resp.sessionId
                if (messages.size <= 1) {
                    activeSessionTitle = cleanQuery.take(28)
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
