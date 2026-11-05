package io.konecto.series76.ui

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import io.konecto.series76.R
import io.konecto.series76.data.*
import io.konecto.series76.mock.DebugMockProvider
import io.konecto.series76.util.LocaleController
import io.konecto.series76.util.TtsManager
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
    val messageVerifications = androidx.compose.runtime.mutableStateMapOf<Int, Verification>()
    var lastUserQuery by mutableStateOf<String?>(null)

    // Modo Desarrollador (Pantalla Debug oculta por Long-Press para evaluadores/devs)
    var isDeveloperModeUnlocked by mutableStateOf(false)

    private var appContext: Context? = null
    private var ttsManager: TtsManager? = null

    fun initPrefs(context: Context) {
        appContext = context.applicationContext
        ttsManager = TtsManager(context.applicationContext)
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

    fun stopTts() {
        ttsManager?.stop()
    }

    override fun onCleared() {
        super.onCleared()
        ttsManager?.shutdown()
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
        stopTts()
        viewModelScope.launch {
            ServerPreferences.clearAuth(context)
            currentUser = null
            sessions = emptyList()
            messages = emptyList()
            messageVerifications.clear()
            activeSessionId = null
            currentScreen = AppScreen.LOGIN
        }
    }

    fun loadSessions() {
        viewModelScope.launch {
            isLoading = true
            errorMessage = null
            try {
                if (DebugMockProvider.isAvailable && DebugMockProvider.isMockEnabled) {
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
        stopTts()
        activeSessionId = null
        activeSessionTitle = "Series 76"
        messages = emptyList()
        messageVerifications.clear()
        errorMessage = null
        currentScreen = AppScreen.CHAT
    }

    fun startNewConversationWithQuery(query: String) {
        stopTts()
        val clean = query.trim()
        activeSessionId = null
        activeSessionTitle = clean.take(28)
        messages = emptyList()
        messageVerifications.clear()
        errorMessage = null
        currentScreen = AppScreen.CHAT
        sendUserMessage(clean)
    }

    fun openConversation(session: SessionSummary) {
        stopTts()
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
        stopTts()
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

    fun sendUserMessage(queryText: String, isRetry: Boolean = false, inputMode: String = "text") {
        val cleanQuery = queryText.trim()
        if (cleanQuery.isEmpty() || isLoading) return
        stopTts()
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

            val prefLang = appContext?.let { ServerPreferences.getAppLanguageSync(it) } ?: "auto"
            val localeLang = LocaleController.getEffectiveLanguage(prefLang)

            if (DebugMockProvider.isAvailable && DebugMockProvider.isMockEnabled && appContext != null) {
                val mockResp = DebugMockProvider.getMockResponse(appContext!!, cleanQuery)
                if (mockResp != null) {
                    val delayMs = if (cleanQuery.contains("loading", ignoreCase = true) || cleanQuery.contains("skeleton", ignoreCase = true)) 10000L else 400L
                    kotlinx.coroutines.delay(delayMs)
                    activeSessionId = mockResp.sessionId
                    val activePart = mockResp.uiPayload.actuators.firstOrNull()?.basePartNumber
                        ?: mockResp.uiPayload.recommendation?.ranking?.firstOrNull()?.partNumber
                    if (messages.size <= 2) {
                        activeSessionTitle = activePart ?: cleanQuery.take(28)
                    }
                    val assistantMsg = MessageRecord(
                        id = messages.size + 1,
                        role = "assistant",
                        content = mockResp.answer,
                        uiPayload = mockResp.uiPayload,
                        debugTrace = mockResp.debugTrace
                    )
                    messageVerifications[assistantMsg.id] = mockResp.verification
                    messages = messages + assistantMsg
                    isLoading = false

                    // TTS automático si está activado
                    if (ServerPreferences.isTtsEnabledSync(appContext!!)) {
                        ttsManager?.speak(assistantMsg.content, localeLang)
                    }
                    return@launch
                }
            }

            // Flujo normal contra backend FastAPI
            try {
                val resp = ApiClient.api.sendMessage(
                    ConversationRequest(
                        sessionId = activeSessionId,
                        query = cleanQuery,
                        locale = localeLang,
                        inputMode = inputMode
                    )
                )
                activeSessionId = resp.sessionId
                val activePart = resp.uiPayload.actuators.firstOrNull()?.basePartNumber
                    ?: resp.uiPayload.recommendation?.ranking?.firstOrNull()?.partNumber
                if (messages.size <= 2) {
                    activeSessionTitle = activePart ?: cleanQuery.take(28)
                }
                val assistantMsg = MessageRecord(
                    id = messages.size + 1,
                    role = "assistant",
                    content = resp.answer,
                    uiPayload = resp.uiPayload,
                    debugTrace = resp.debugTrace
                )
                messageVerifications[assistantMsg.id] = resp.verification
                messages = messages + assistantMsg

                // TTS automático si está activado
                appContext?.let { ctx ->
                    if (ServerPreferences.isTtsEnabledSync(ctx)) {
                        ttsManager?.speak(assistantMsg.content, localeLang)
                    }
                }
            } catch (e: Exception) {
                if (e is retrofit2.HttpException) {
                    val backendMessage = try {
                        val body = e.response()?.errorBody()?.string()
                        if (!body.isNullOrBlank()) {
                            val jsonElem = ApiClient.jsonFormat.parseToJsonElement(body)
                            (jsonElem as? kotlinx.serialization.json.JsonObject)?.let { obj ->
                                (obj["detail"] as? kotlinx.serialization.json.JsonPrimitive)?.content
                                    ?: (obj["message"] as? kotlinx.serialization.json.JsonPrimitive)?.content
                            } ?: body
                        } else null
                    } catch (_: Exception) {
                        null
                    }
                    errorMessage = backendMessage?.takeIf { it.isNotBlank() }
                        ?: appContext?.getString(R.string.error_service_unavailable_clean_msg)
                        ?: "The technical assistant is temporarily unavailable. Please retry your query."
                } else {
                    // Errores de red del cliente
                    errorMessage = appContext?.getString(R.string.error_connection_clean_msg)
                        ?: "Connection error. Please check your network connection and retry."
                }
            } finally {
                isLoading = false
            }
        }
    }
}
