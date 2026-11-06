package io.konecto.series76.util

import android.content.Context
import android.content.Intent
import android.speech.tts.TextToSpeech
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.util.Locale

enum class TtsStatus {
    AVAILABLE,
    MISSING_LANGUAGE_DATA,
    NO_ENGINE
}

class TtsManager(private val context: Context) : TextToSpeech.OnInitListener {
    private var tts: TextToSpeech? = null
    var isInitialized by mutableStateOf(false)
        private set
    var currentStatus by mutableStateOf(TtsStatus.AVAILABLE)
        private set

    private var pendingText: String? = null
    private var pendingLocale: String? = null
    private var lastLocaleTag: String = "es"

    init {
        if (!isTtsEngineInstalled(context)) {
            currentStatus = TtsStatus.NO_ENGINE
        } else {
            try {
                tts = TextToSpeech(context.applicationContext, this)
            } catch (e: Exception) {
                currentStatus = TtsStatus.NO_ENGINE
            }
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            isInitialized = true
            tts?.setSpeechRate(1.0f)
            checkLanguage(lastLocaleTag)
            pendingText?.let { text ->
                val loc = pendingLocale ?: lastLocaleTag
                pendingText = null
                pendingLocale = null
                speak(text, loc)
            }
        } else {
            isInitialized = false
            currentStatus = TtsStatus.NO_ENGINE
        }
    }

    fun checkLanguage(localeTag: String): TtsStatus {
        lastLocaleTag = localeTag
        if (!isTtsEngineInstalled(context)) {
            currentStatus = TtsStatus.NO_ENGINE
            return TtsStatus.NO_ENGINE
        }
        val engine = tts ?: run {
            currentStatus = TtsStatus.NO_ENGINE
            return TtsStatus.NO_ENGINE
        }
        if (!isInitialized) {
            return currentStatus
        }
        val targetLocale = if (localeTag.startsWith("es")) Locale("es", "ES") else Locale.US
        val res = engine.isLanguageAvailable(targetLocale)
        currentStatus = when (res) {
            TextToSpeech.LANG_MISSING_DATA -> TtsStatus.MISSING_LANGUAGE_DATA
            TextToSpeech.LANG_NOT_SUPPORTED -> TtsStatus.MISSING_LANGUAGE_DATA
            else -> TtsStatus.AVAILABLE
        }
        return currentStatus
    }

    fun speak(text: String, localeTag: String) {
        lastLocaleTag = localeTag
        if (text.isBlank()) return
        if (!isInitialized) {
            pendingText = text
            pendingLocale = localeTag
            return
        }
        val targetLocale = if (localeTag.startsWith("es")) Locale("es", "ES") else Locale.US
        tts?.let { engine ->
            val result = engine.setLanguage(targetLocale)
            if (result != TextToSpeech.LANG_MISSING_DATA && result != TextToSpeech.LANG_NOT_SUPPORTED) {
                engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "series76_answer")
            } else {
                currentStatus = TtsStatus.MISSING_LANGUAGE_DATA
            }
        }
    }

    fun stop() {
        pendingText = null
        try {
            tts?.stop()
        } catch (e: Exception) {
            // Ignore
        }
    }

    fun shutdown() {
        pendingText = null
        try {
            tts?.stop()
            tts?.shutdown()
        } catch (e: Exception) {
            // Ignore
        } finally {
            tts = null
            isInitialized = false
        }
    }

    companion object {
        fun isTtsEngineInstalled(context: Context): Boolean {
            return try {
                val intent = Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE)
                val services = context.packageManager.queryIntentServices(intent, 0)
                services.isNotEmpty()
            } catch (e: Exception) {
                false
            }
        }
    }
}
