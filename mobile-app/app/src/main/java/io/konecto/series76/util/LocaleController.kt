package io.konecto.series76.util

import android.content.Context
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import io.konecto.series76.data.ServerPreferences
import java.util.Locale

object LocaleController {

    fun setLanguage(context: Context, langCode: String) {
        val localeList = when (langCode) {
            ServerPreferences.LANG_ES -> LocaleListCompat.forLanguageTags("es")
            ServerPreferences.LANG_EN -> LocaleListCompat.forLanguageTags("en")
            else -> LocaleListCompat.getEmptyLocaleList()
        }
        AppCompatDelegate.setApplicationLocales(localeList)
    }

    fun getEffectiveLanguage(selectedPreference: String): String {
        return when (selectedPreference) {
            ServerPreferences.LANG_ES -> "es"
            ServerPreferences.LANG_EN -> "en"
            else -> {
                val sysLang = Locale.getDefault().language
                if (sysLang.startsWith("es")) "es" else "en"
            }
        }
    }
}

