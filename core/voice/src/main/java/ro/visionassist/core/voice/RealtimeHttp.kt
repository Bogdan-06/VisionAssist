package ro.visionassist.core.voice

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URI
import java.io.ByteArrayOutputStream

internal class VoiceHttpFailure(val status: Int, val code: String? = null) : Exception("HTTP $status")

/** Only the short-lived secret passes to OpenAI; it is never persisted or logged. */
internal class RealtimeHttp {
    @Volatile private var active: HttpURLConnection? = null
    fun cancel() { active?.disconnect() }

    suspend fun geminiSecret(settings: BackendSettings): Pair<String, String> = withContext(Dispatchers.IO) {
        val response = JSONObject(post(settings.url.trimEnd('/') + "/gemini/client-secret", settings.accessToken, "", "application/json"))
        val secret = response.getString("value")
        val model = response.getString("model")
        require(secret.startsWith("auth_tokens/") && secret.length <= 8192 && !secret.contains('\n') && !secret.contains('\r'))
        require(model.matches(Regex("models/gemini-[a-zA-Z0-9.-]+")))
        require(response.getLong("expires_at") * 1000 > System.currentTimeMillis())
        secret to model
    }

    suspend fun clientSecret(settings: BackendSettings): String = withContext(Dispatchers.IO) {
        val response = JSONObject(post(settings.url.trimEnd('/') + "/realtime/client-secret", settings.accessToken, "", "application/json"))
        val secret = response.getString("value")
        require(secret.startsWith("ek_") && response.getLong("expires_at") * 1000 > System.currentTimeMillis())
        secret
    }
    suspend fun answer(secret: String, sdp: String): String = withContext(Dispatchers.IO) {
        post("https://api.openai.com/v1/realtime/calls", secret, sdp, "application/sdp").also {
            require(it.startsWith("v=0") && it.contains("m=audio"))
        }
    }
    private fun post(url: String, token: String, body: String, contentType: String): String {
        val connection = URI(url).toURL().openConnection() as HttpURLConnection
        active = connection
        try {
            connection.instanceFollowRedirects = false // Do not forward credentials through redirects.
            connection.connectTimeout = 15_000; connection.readTimeout = 20_000
            connection.requestMethod = "POST"; connection.doOutput = true
            connection.setRequestProperty("Authorization", "Bearer $token")
            connection.setRequestProperty("Content-Type", contentType)
            val bytes = body.toByteArray(Charsets.UTF_8)
            connection.setFixedLengthStreamingMode(bytes.size)
            connection.outputStream.use { it.write(bytes) }
            if (connection.responseCode !in 200..299) {
                // Keep only known diagnostic codes, never upstream messages, tokens or bodies.
                val code = try {
                    val raw = connection.errorStream?.use { stream ->
                        val output = ByteArrayOutputStream()
                        val buffer = ByteArray(1024)
                        while (output.size() < 8192) {
                            val count = stream.read(buffer, 0, minOf(buffer.size, 8192 - output.size()))
                            if (count < 0) break
                            output.write(buffer, 0, count)
                        }
                        String(output.toByteArray(), Charsets.UTF_8)
                    }
                    val error = raw?.let { JSONObject(it).opt("error") }
                    val candidate = when (error) {
                        is JSONObject -> error.optString("code").ifBlank { error.optString("type") }
                        is String -> error
                        else -> ""
                    }
                    candidate.takeIf { it in setOf("insufficient_quota", "credit_balance_exhausted",
                        "organization_spend_limit_exceeded", "project_spend_limit_exceeded",
                        "organization_usage_limit_exceeded", "rate_limit_exceeded", "slow_down", "upstream_quota_exceeded") }
                } catch (_: Exception) { null }
                throw VoiceHttpFailure(connection.responseCode, code)
            }
            return connection.inputStream.use { stream ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(8_192)
                while (true) {
                    val count = stream.read(buffer)
                    if (count < 0) break
                    require(output.size() + count <= 512_000)
                    output.write(buffer, 0, count)
                }
                String(output.toByteArray(), Charsets.UTF_8)
            }
        } finally { connection.disconnect(); if (active === connection) active = null }
    }
}
