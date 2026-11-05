package io.konecto.series76.util

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

enum class VoiceErrorType {
    NO_MATCH_OR_TIMEOUT,    // NO_MATCH (7), SPEECH_TIMEOUT (6) -> "No te escuché, intenta de nuevo"
    NETWORK,                 // NETWORK (2), NETWORK_TIMEOUT (1) -> "Error de conexión de red"
    SERVER_DISCONNECTED,     // 11 -> "Servidor de voz desconectado"
    LANGUAGE_NOT_SUPPORTED,  // 12 -> "Idioma no admitido por el motor de voz"
    LANGUAGE_UNAVAILABLE,    // 13 -> "Idioma sin conexión no disponible"
    RECOGNIZER_BUSY,         // 8 -> "El micrófono está ocupado, espera un momento"
    INSUFFICIENT_PERMISSIONS,// 9 -> "Permiso de micrófono no otorgado"
    GENERIC                  // other
}

sealed class VoiceState {
    object Idle : VoiceState()
    object Preparing : VoiceState() // "Preparando…" (hasta onReadyForSpeech)
    data class Listening(val isSilent: Boolean = false) : VoiceState() // "Te escucho"
    object Processing : VoiceState() // "Procesando…" tras onEndOfSpeech
    data class Success(val text: String) : VoiceState()
    data class Error(val errorType: VoiceErrorType) : VoiceState()
    object Unavailable : VoiceState()
}

class VoiceRecognitionManager(
    private val context: Context
) : RecognitionListener {

    var state by mutableStateOf<VoiceState>(VoiceState.Idle)
    var rmsLevel by mutableStateOf(0f)
    var partialResult by mutableStateOf("")

    private var speechRecognizer: SpeechRecognizer? = null
    private var hasRetriedWithoutOffline = false
    private var lastLocaleTag: String = "es-CO"
    private var hasDetectedSound = false

    private val mainHandler = Handler(Looper.getMainLooper())
    private val silenceRunnable = Runnable {
        if (state is VoiceState.Listening && !hasDetectedSound) {
            state = VoiceState.Listening(isSilent = true)
        }
    }

    fun isAvailable(): Boolean {
        return SpeechRecognizer.isRecognitionAvailable(context)
    }

    fun reset() {
        mainHandler.removeCallbacks(silenceRunnable)
        state = VoiceState.Idle
        rmsLevel = 0f
        partialResult = ""
        hasDetectedSound = false
    }

    fun startListening(localeTag: String, isRetry: Boolean = false) {
        if (!isAvailable()) {
            state = VoiceState.Unavailable
            return
        }

        lastLocaleTag = localeTag
        if (!isRetry) {
            hasRetriedWithoutOffline = false
        }

        startInternal(localeTag, preferOffline = !hasRetriedWithoutOffline)
    }

    private fun startInternal(localeTag: String, preferOffline: Boolean) {
        reset()
        state = VoiceState.Preparing

        try {
            speechRecognizer?.destroy()
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
                setRecognitionListener(this@VoiceRecognitionManager)
            }

            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                if (preferOffline) {
                    putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
                }
                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)

                val primaryLang = if (localeTag.startsWith("es")) "es-CO" else "en-US"
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, primaryLang)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, primaryLang)
                if (primaryLang.startsWith("es")) {
                    putExtra("android.speech.extra.EXTRA_ADDITIONAL_LANGUAGES", arrayOf("es-ES", "es-419", "es-US"))
                }
            }

            speechRecognizer?.startListening(intent)
        } catch (e: Exception) {
            state = VoiceState.Error(VoiceErrorType.GENERIC)
        }
    }

    fun stopListening() {
        mainHandler.removeCallbacks(silenceRunnable)
        state = VoiceState.Processing
        try {
            speechRecognizer?.stopListening()
        } catch (_: Exception) {}
    }

    fun cancel() {
        mainHandler.removeCallbacks(silenceRunnable)
        try {
            speechRecognizer?.cancel()
        } catch (_: Exception) {}
        reset()
    }

    fun destroy() {
        mainHandler.removeCallbacks(silenceRunnable)
        try {
            speechRecognizer?.destroy()
        } catch (_: Exception) {}
        speechRecognizer = null
        reset()
    }

    override fun onReadyForSpeech(params: Bundle?) {
        state = VoiceState.Listening(isSilent = false)
        hasDetectedSound = false
        mainHandler.removeCallbacks(silenceRunnable)
        mainHandler.postDelayed(silenceRunnable, 4000)
    }

    override fun onBeginningOfSpeech() {
        hasDetectedSound = true
        mainHandler.removeCallbacks(silenceRunnable)
        state = VoiceState.Listening(isSilent = false)
    }

    override fun onRmsChanged(rmsdB: Float) {
        // Suavizado del valor RMS real
        val normalized = ((rmsdB + 2f) / 12f).coerceIn(0f, 1f)
        val smoothed = rmsLevel * 0.65f + normalized * 0.35f
        rmsLevel = smoothed

        if (smoothed > 0.18f && !hasDetectedSound) {
            hasDetectedSound = true
            mainHandler.removeCallbacks(silenceRunnable)
            if (state is VoiceState.Listening) {
                state = VoiceState.Listening(isSilent = false)
            }
        }
    }

    override fun onBufferReceived(buffer: ByteArray?) {}

    override fun onEndOfSpeech() {
        mainHandler.removeCallbacks(silenceRunnable)
        state = VoiceState.Processing
    }

    override fun onError(error: Int) {
        mainHandler.removeCallbacks(silenceRunnable)

        // Error codes 11 (SERVER_DISCONNECTED), 12 (LANGUAGE_NOT_SUPPORTED), 13 (LANGUAGE_UNAVAILABLE)
        // Si falló con offline, reintentar UNA vez sin EXTRA_PREFER_OFFLINE antes de mostrar error
        if ((error == 11 || error == 12 || error == 13 || error == SpeechRecognizer.ERROR_SERVER) && !hasRetriedWithoutOffline) {
            hasRetriedWithoutOffline = true
            startInternal(lastLocaleTag, preferOffline = false)
            return
        }

        val type = when (error) {
            SpeechRecognizer.ERROR_NO_MATCH,
            SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> VoiceErrorType.NO_MATCH_OR_TIMEOUT
            SpeechRecognizer.ERROR_NETWORK,
            SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> VoiceErrorType.NETWORK
            11 -> VoiceErrorType.SERVER_DISCONNECTED
            12 -> VoiceErrorType.LANGUAGE_NOT_SUPPORTED
            13 -> VoiceErrorType.LANGUAGE_UNAVAILABLE
            SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> VoiceErrorType.RECOGNIZER_BUSY
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> VoiceErrorType.INSUFFICIENT_PERMISSIONS
            else -> VoiceErrorType.GENERIC
        }
        state = VoiceState.Error(type)
    }

    override fun onResults(results: Bundle?) {
        mainHandler.removeCallbacks(silenceRunnable)
        val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val text = matches?.firstOrNull().orEmpty()
        if (text.isNotBlank()) {
            state = VoiceState.Success(text)
        } else {
            state = VoiceState.Error(VoiceErrorType.NO_MATCH_OR_TIMEOUT)
        }
    }

    override fun onPartialResults(partialResults: Bundle?) {
        val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val partial = matches?.firstOrNull().orEmpty()
        if (partial.isNotBlank()) {
            partialResult = partial
            hasDetectedSound = true
            mainHandler.removeCallbacks(silenceRunnable)
            if (state is VoiceState.Listening) {
                state = VoiceState.Listening(isSilent = false)
            }
        }
    }

    override fun onEvent(eventType: Int, params: Bundle?) {}
}
