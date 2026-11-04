package io.konecto.series76.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "series76_preferences")

object ServerPreferences {
    private val KEY_SERVER_URL = stringPreferencesKey("server_url")
    private val KEY_AUTH_TOKEN = stringPreferencesKey("auth_token")
    private val KEY_USER_EMAIL = stringPreferencesKey("user_email")
    private val KEY_USER_NAME = stringPreferencesKey("user_name")

    const val DEFAULT_SERVER_URL = "http://10.0.2.2:8001/"

    fun getServerUrl(context: Context): Flow<String> {
        return context.dataStore.data.map { prefs ->
            prefs[KEY_SERVER_URL] ?: DEFAULT_SERVER_URL
        }
    }

    suspend fun getServerUrlSync(context: Context): String {
        return context.dataStore.data.first()[KEY_SERVER_URL] ?: DEFAULT_SERVER_URL
    }

    suspend fun setServerUrl(context: Context, url: String) {
        val clean = normalizeUrl(url)
        context.dataStore.edit { prefs ->
            prefs[KEY_SERVER_URL] = clean
        }
        ApiClient.baseUrl = clean
    }

    suspend fun saveAuth(context: Context, token: String, email: String, name: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_AUTH_TOKEN] = token
            prefs[KEY_USER_EMAIL] = email
            prefs[KEY_USER_NAME] = name
        }
        ApiClient.authToken = token
    }

    suspend fun getSavedAuth(context: Context): Triple<String?, String?, String?> {
        val prefs = context.dataStore.data.first()
        return Triple(
            prefs[KEY_AUTH_TOKEN],
            prefs[KEY_USER_EMAIL],
            prefs[KEY_USER_NAME]
        )
    }

    suspend fun clearAuth(context: Context) {
        context.dataStore.edit { prefs ->
            prefs.remove(KEY_AUTH_TOKEN)
            prefs.remove(KEY_USER_EMAIL)
            prefs.remove(KEY_USER_NAME)
        }
        ApiClient.authToken = null
    }

    fun normalizeUrl(input: String): String {
        var clean = input.trim()
        if (!clean.startsWith("http://") && !clean.startsWith("https://")) {
            clean = "http://$clean"
        }
        if (!clean.endsWith("/")) {
            clean = "$clean/"
        }
        return clean
    }

    fun isValidUrl(url: String): Boolean {
        val trimmed = url.trim()
        if (trimmed.isBlank()) return false
        val regex = Regex("""^(https?://)?([a-zA-Z0-9.\-_]+)(:\d{1,5})?(/.*)?$""")
        return regex.matches(trimmed)
    }
}

