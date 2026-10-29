package ro.visionassist.app.voice

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import ro.visionassist.core.voice.BackendSettings
import ro.visionassist.core.voice.VoiceProvider
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Stores only the private backend access token, encrypted by a non-exportable Android key. */
sealed interface BackendSettingsLoadResult {
    data object Unconfigured : BackendSettingsLoadResult
    data object Unreadable : BackendSettingsLoadResult
    data class Available(val settings: BackendSettings) : BackendSettingsLoadResult {
        override fun toString() = "Available(redacted)"
    }
}

class BackendSettingsStore(context: Context,
    private val preferences: SharedPreferences = context.getSharedPreferences("voice_backend", Context.MODE_PRIVATE),
    private val keyAlias: String = "visionassist-backend") {
    private fun key(create: Boolean): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(keyAlias, null) as? SecretKey)?.let { return it }
        check(create) { "Stored configuration key is unavailable" }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(keyAlias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun load(): BackendSettingsLoadResult {
        return try {
            val stored = preferences.getString("encrypted", null) ?: return BackendSettingsLoadResult.Unconfigured
            val payload = JSONObject(stored)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(create = false), GCMParameterSpec(128, Base64.decode(payload.getString("iv"), Base64.NO_WRAP)))
            val value = JSONObject(String(cipher.doFinal(Base64.decode(payload.getString("data"), Base64.NO_WRAP)), Charsets.UTF_8))
            BackendSettingsLoadResult.Available(BackendSettings(value.getString("url"), value.getString("token"),
                VoiceProvider.valueOf(value.optString("provider", "OpenAI"))))
        } catch (_: Exception) { BackendSettingsLoadResult.Unreadable }
    }
    fun save(settings: BackendSettings) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key(create = true)) }
        val plain = JSONObject().put("url", settings.url).put("token", settings.accessToken).put("provider", settings.provider.name).toString().toByteArray(Charsets.UTF_8)
        val encrypted = try { cipher.doFinal(plain) } finally { plain.fill(0) }
        preferences.edit().putString("encrypted", JSONObject()
            .put("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .put("data", Base64.encodeToString(encrypted, Base64.NO_WRAP)).toString()).apply()
    }
}
