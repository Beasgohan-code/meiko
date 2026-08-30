package ai.meiko.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import java.util.UUID

private val Context.dataStore by preferencesDataStore(name = "meiko_prefs")

/** Small persisted-settings helper backed by Jetpack DataStore (replaces SharedPreferences). */
class MeikoPrefs(private val context: Context) {
    private object Keys {
        val BACKEND_URL = stringPreferencesKey("backend_url")
        val USER_ID = stringPreferencesKey("user_id")
        val PROVIDER = stringPreferencesKey("provider")
        val MODEL = stringPreferencesKey("model")
        val MODE = stringPreferencesKey("mode")
        val PERSONA_ID = stringPreferencesKey("persona_id")
        val UI_LANGUAGE = stringPreferencesKey("ui_language")
        val API_KEY = stringPreferencesKey("meiko_api_key")
        val THEME = stringPreferencesKey("theme")
        val AUTH_TOKEN = stringPreferencesKey("auth_token")
        val AUTH_USERNAME = stringPreferencesKey("auth_username")
        val AUTH_AVATAR = stringPreferencesKey("auth_avatar")
    }

    suspend fun backendUrl(default: String): String =
        context.dataStore.data.first()[Keys.BACKEND_URL] ?: default

    suspend fun setBackendUrl(url: String) {
        context.dataStore.edit { it[Keys.BACKEND_URL] = url }
    }

    suspend fun userId(): String {
        val existing = context.dataStore.data.first()[Keys.USER_ID]
        if (existing != null) return existing
        val fresh = "user-" + UUID.randomUUID().toString().take(8)
        context.dataStore.edit { it[Keys.USER_ID] = fresh }
        return fresh
    }

    suspend fun provider(): String? = context.dataStore.data.first()[Keys.PROVIDER]
    suspend fun setProvider(v: String) {
        context.dataStore.edit { it[Keys.PROVIDER] = v }
    }

    suspend fun model(): String? = context.dataStore.data.first()[Keys.MODEL]
    suspend fun setModel(v: String?) {
        context.dataStore.edit { if (v == null) it.remove(Keys.MODEL) else it[Keys.MODEL] = v }
    }

    suspend fun mode(): String = context.dataStore.data.first()[Keys.MODE] ?: "autonomous"
    suspend fun setMode(v: String) {
        context.dataStore.edit { it[Keys.MODE] = v }
    }

    suspend fun personaId(): String = context.dataStore.data.first()[Keys.PERSONA_ID] ?: "default"
    suspend fun setPersonaId(v: String) {
        context.dataStore.edit { it[Keys.PERSONA_ID] = v }
    }

    suspend fun uiLanguage(): String = context.dataStore.data.first()[Keys.UI_LANGUAGE] ?: "en"
    suspend fun setUiLanguage(v: String) {
        context.dataStore.edit { it[Keys.UI_LANGUAGE] = v }
    }

    suspend fun apiKey(): String? = context.dataStore.data.first()[Keys.API_KEY]
    suspend fun setApiKey(v: String) {
        context.dataStore.edit { it[Keys.API_KEY] = v }
    }

    /** "dark" (default) or "light". */
    suspend fun theme(): String = context.dataStore.data.first()[Keys.THEME] ?: "dark"
    suspend fun setTheme(v: String) {
        context.dataStore.edit { it[Keys.THEME] = v }
    }

    // ---------- Optional GitHub-account session (JWT) ----------
    suspend fun authToken(): String? = context.dataStore.data.first()[Keys.AUTH_TOKEN]
    suspend fun authUsername(): String? = context.dataStore.data.first()[Keys.AUTH_USERNAME]
    suspend fun authAvatarUrl(): String? = context.dataStore.data.first()[Keys.AUTH_AVATAR]

    /** Saving a session also makes the account's stable user_id the app's
     * user_id, so conversations/settings/memories follow the account. */
    suspend fun setAuthSession(token: String, userId: String, username: String, avatarUrl: String?) {
        context.dataStore.edit {
            it[Keys.AUTH_TOKEN] = token
            it[Keys.AUTH_USERNAME] = username
            it[Keys.USER_ID] = userId
            if (avatarUrl != null) it[Keys.AUTH_AVATAR] = avatarUrl else it.remove(Keys.AUTH_AVATAR)
        }
    }

    suspend fun clearAuthSession() {
        context.dataStore.edit {
            it.remove(Keys.AUTH_TOKEN)
            it.remove(Keys.AUTH_USERNAME)
            it.remove(Keys.AUTH_AVATAR)
        }
    }
}
