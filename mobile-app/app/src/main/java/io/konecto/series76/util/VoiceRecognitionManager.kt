package io.konecto.series76.util

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

sealed class VoiceState {
    object Idle : VoiceState()
    object Listening : VoiceState()
    object Processing : VoiceState()
    data class Success(val text: String) : VoiceState()
    data class Error(val message: String) : VoiceState()
    object Unavailable : VoiceState()
}

class VoiceRecognitionManager(
    private val context: Context
) : RecognitionListener {

    var state by mutableStateOf<VoiceState>(VoiceState.Idle)
    var rmsLevel by mutableStateOf(0f)
    var partialResult by mutableStateOf("")

    private var speechRecognizer: SpeechRecognizer? = null

    fun isAvailable(): Boolean {
        return SpeechRecognizer.isRecognitionAvailable(context)
    }

    fun reset() {
        state = VoiceState.Idle
        rmsLevel = 0f
        partialResult = ""
    }

    fun startListening(localeTag: String) {
        if (!isAvailable()) {
            state = VoiceState.Unavailable
            return
        }

        try {
            speechRecognizer?.destroy()
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
                setRecognitionListener(this@VoiceRecognitionManager)
            }

            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)

                val primaryLang = if (localeTag.startsWith("es")) "es-CO" else "en-US"
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, primaryLang)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, primaryLang)
                if (primaryLang.startsWith("es")) {
                    putExtra("android.speech.extra.EXTRA_ADDITIONAL_LANGUAGES", arrayOf("es-ES", "es-419", "es-US"))
                }
            }

            reset()
            state = VoiceState.Listening
            speechRecognizer?.startListening(intent)
        } catch (e: Exception) {
            state = VoiceState.Error(e.localizedMessage ?: "Error al inicializar micrófono")
        }
    }

    fun stopListening() {
        state = VoiceState.Processing
        try {
            speechRecognizer?.stopListening()
        } catch (e: Exception) {
            // Ignore
        }
    }

    fun cancel() {
        try {
            speechRecognizer?.cancel()
        } catch (e: Exception) {
            // Ignore
        }
        reset()
    }

    fun destroy() {
        try {
            speechRecognizer?.destroy()
        } catch (e: Exception) {
            // Ignore
        }
        speechRecognizer = null
        reset()
    }

    override fun onReadyForSpeech(params: Bundle?) {
        state = VoiceState.Listening
    }

    override fun onBeginningOfSpeech() {
        state = VoiceState.Listening
    }

    override fun onRmsChanged(rmsdB: Float) {
        rmsLevel = ((rmsdB + 2f) / 12f).coerceIn(0f, 1f)
    }

    override fun onBufferReceived(buffer: ByteArray?) {}

    override fun onEndOfSpeech() {
        state = VoiceState.Processing
    }

    override fun onError(error: Int) {
        val msg = when (error) {
            SpeechRecognizer.ERROR_AUDIO -> "Error de grabación de audio"
            SpeechRecognizer.ERROR_CLIENT -> "Error de cliente de reconocimiento"
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Permiso de micrófono no otorgado"
            SpeechRecognizer.ERROR_NETWORK -> "Error de red"
            SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Tiempo de espera de red agotado"
            SpeechRecognizer.ERROR_NO_MATCH -> "No se detectó habla comprensible"
            SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Reconocedor de voz ocupado"
            SpeechRecognizer.ERROR_SERVER -> "Error del servidor de voz"
            SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No se escuchó ninguna voz"
            else -> "Error de reconocimiento ($error)"
        }
        state = VoiceState.Error(msg)
    }

    override fun onResults(results: Bundle?) {
        val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val text = matches?.firstOrNull().orEmpty()
        if (text.isNotBlank()) {
            state = VoiceState.Success(text)
        } else {
            state = VoiceState.Error("No se detectó voz comprensible")
        }
    }

    override fun onPartialResults(partialResults: Bundle?) {
        val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
        val partial = matches?.firstOrNull().orEmpty()
        if (partial.isNotBlank()) {
            partialResult = partial
        }
    }

    override fun onEvent(eventType: Int, params: Bundle?) {}
}
