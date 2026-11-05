package io.konecto.series76.util

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

class TtsManager(context: Context) : TextToSpeech.OnInitListener {
    private var tts: TextToSpeech? = TextToSpeech(context.applicationContext, this)
    private var isInitialized = false

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            isInitialized = true
            tts?.setSpeechRate(1.0f)
        }
    }

    fun speak(text: String, localeTag: String) {
        if (!isInitialized || text.isBlank()) return
        val targetLocale = if (localeTag.startsWith("es")) Locale("es", "ES") else Locale.US
        tts?.let { engine ->
            val result = engine.setLanguage(targetLocale)
            if (result != TextToSpeech.LANG_MISSING_DATA && result != TextToSpeech.LANG_NOT_SUPPORTED) {
                engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "series76_answer")
            }
        }
    }

    fun stop() {
        try {
            tts?.stop()
        } catch (e: Exception) {
            // Ignore if already stopped
        }
    }

    fun shutdown() {
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
}

