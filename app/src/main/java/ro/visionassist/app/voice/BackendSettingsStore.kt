package ro.visionassist.app.voice

import android.content.Context
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
class BackendSettingsStore(context: Context) {
    private val preferences = context.getSharedPreferences("voice_backend", Context.MODE_PRIVATE)
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("visionassist-backend", null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder("visionassist-backend", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun load(): BackendSettings {
        return try {
            val stored = preferences.getString("encrypted", null) ?: return BackendSettings("", "", VoiceProvider.Gemini)
            val payload = JSONObject(stored)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(payload.getString("iv"), Base64.NO_WRAP)))
            val value = JSONObject(String(cipher.doFinal(Base64.decode(payload.getString("data"), Base64.NO_WRAP)), Charsets.UTF_8))
            BackendSettings(value.getString("url"), value.getString("token"), VoiceProvider.valueOf(value.optString("provider", "OpenAI")))
        } catch (_: Exception) { BackendSettings("", "", VoiceProvider.Gemini) }
    }
    fun save(settings: BackendSettings) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val plain = JSONObject().put("url", settings.url).put("token", settings.accessToken).put("provider", settings.provider.name).toString().toByteArray(Charsets.UTF_8)
        val encrypted = cipher.doFinal(plain); plain.fill(0)
        preferences.edit().putString("encrypted", JSONObject()
            .put("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .put("data", Base64.encodeToString(encrypted, Base64.NO_WRAP)).toString()).apply()
    }
}
