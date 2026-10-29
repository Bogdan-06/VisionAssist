package ro.visionassist.core.voice

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.*
import android.os.Handler
import android.os.Looper
import android.util.Base64
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.*
import okio.ByteString
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** Gemini Live transport. Main-thread lifecycle; no audio, images or tokens are persisted. */
class GeminiVoiceClient(context: Context, private val allowLoopbackHttp: Boolean = false) : VoiceClient {
    private val app = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val mutableState = MutableStateFlow(VoiceState())
    override val state = mutableState.asStateFlow()
    private val http = RealtimeHttp()
    private val sockets = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS).pingInterval(15, TimeUnit.SECONDS)
        .followRedirects(false).followSslRedirects(false).build()
    private val audio = app.getSystemService(AudioManager::class.java)
    private var focus: AudioFocusRequest? = null
    private var previousMode: Int? = null
    private var pcm: GeminiPcmAudio? = null
    private var socket: WebSocket? = null
    private var connection: Job? = null
    private var timeout: Job? = null
    private var generation = 0
    private var closed = false
    private var ready = false
    private val warnings = mutableSetOf<String>()
    private val images = ImageRequestCoordinator(
        canSend = { ready && !closed && warnings.isEmpty() },
        dispatch = { tool, jpeg, commit ->
            pcm?.interrupt()
            if (tool == null || send(GeminiEvents.toolResult(tool, "request_camera_image", "photo_confirmed"))) {
                val event = GeminiEvents.image(jpeg)
                commit { send(event) }
            }
        },
        decline = { tool, reason -> if (ready) send(GeminiEvents.toolResult(tool, "request_camera_image", reason)) },
        changed = { requested, busy -> mutableState.value = mutableState.value.copy(imageRequested = requested, imageBusy = busy) },
        sent = { mutableState.value = mutableState.value.copy(message = "O fotografie a fost trimisă către Google Gemini.") },
        captureFailed = { mutableState.value = mutableState.value.copy(message = "Fotografia nu a putut fi trimisă. Încearcă din nou.") }
    )

    override fun start(settings: BackendSettings) {
        if (closed || warnings.isNotEmpty()) return
        cleanup()
        try {
            settings.validate(allowLoopbackHttp)
            check(app.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
        } catch (_: Exception) {
            fail("Verifică permisiunea microfonului, adresa serverului și codul privat de acces."); return
        }
        val gen = generation
        mutableState.value = VoiceState(VoicePhase.Connecting, "Se conectează la Google Gemini…")
        timeout = scope.launch { delay(30_000); if (gen == generation && !ready) fail("Gemini nu a răspuns. Verifică internetul și repornește conversația.") }
        connection = scope.launch {
            try {
                val (token, model) = http.geminiSecret(settings)
                ensureActive()
                if (gen != generation) return@launch
                acquireFocus(gen)
                // Header authentication avoids putting even the short-lived token in URLs.
                val request = Request.Builder().url("https://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained")
                    .header("Authorization", "Token $token").build()
                socket = sockets.newWebSocket(request, object : WebSocketListener() {
                    override fun onOpen(webSocket: WebSocket, response: Response) = dispatch(gen) {
                        send(JSONObject().put("setup", JSONObject().put("model", model)))
                    }
                    override fun onMessage(webSocket: WebSocket, text: String) = dispatch(gen) { receive(text, gen) }
                    override fun onMessage(webSocket: WebSocket, bytes: ByteString) = dispatch(gen) { receive(bytes.utf8(), gen) }
                    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) = dispatch(gen) {
                        fail(if (response?.code == 429) "Limita Gemini a fost atinsă. Încearcă mai târziu. Camera continuă local."
                            else "Conexiunea Gemini a eșuat. Verifică internetul, cheia și accesul la model pe server.")
                    }
                    override fun onClosing(webSocket: WebSocket, code: Int, reason: String) = dispatch(gen) {
                        fail("Sesiunea Gemini s-a încheiat. Poți reporni conversația. Camera continuă local.")
                    }
                    override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = dispatch(gen) {
                        fail("Sesiunea Gemini s-a încheiat. Poți reporni conversația.")
                    }
                })
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: VoiceHttpFailure) {
                if (gen == generation) fail(when (failure.status) {
                    401, 403 -> "Codul privat al serverului este incorect sau accesul este refuzat."
                    429 -> "Limita Gemini sau a serverului a fost atinsă. Încearcă mai târziu. Camera continuă local."
                    503 -> "Gemini nu este configurat. Administratorul trebuie să adauge cheia Google pe server."
                    else -> "Serverul nu poate conecta Gemini. Verifică cheia Google și modelul configurat."
                })
            } catch (_: Exception) { if (gen == generation) fail("Conexiunea Gemini sau dispozitivul audio nu este disponibil. Camera continuă local.") }
        }
    }

    private fun dispatch(gen: Int, action: () -> Unit) { scope.launch { if (!closed && gen == generation) action() } }
    private fun receive(raw: String, gen: Int) {
        try {
            require(raw.length <= 1_000_000)
            val event = JSONObject(raw)
            if (event.has("error")) { fail("Gemini a refuzat cererea. Verifică modelul și cota disponibilă."); return }
            if (event.has("goAway")) { fail("Sesiunea Gemini se încheie. Repornește conversația pentru a continua."); return }
            if (event.has("setupComplete") && !ready) {
                timeout?.cancel(); ready = true
                pcm = GeminiPcmAudio(scope, onInput = { bytes ->
                    val ws = socket
                    if (ws == null || ws.queueSize() > 64_000 || !ws.send(GeminiEvents.audio(bytes).toString())) {
                        dispatch(gen) { fail("Conexiunea este prea lentă pentru voce. Repornește conversația.") }
                    }
                }, onPlaying = { playing -> dispatch(gen) {
                    mutableState.value = mutableState.value.copy(phase = if (playing) VoicePhase.Speaking else VoicePhase.Listening)
                } }, onFailure = { dispatch(gen) { fail("Microfonul sau redarea audio s-a oprit. Repornește conversația.") } })
                pcm!!.start()
                mutableState.value = VoiceState(VoicePhase.Listening, "Gemini ascultă. Vorbește în română.")
            }
            val content = event.optJSONObject("serverContent")
            if (content?.optBoolean("interrupted") == true) pcm?.interrupt()
            val parts = content?.optJSONObject("modelTurn")?.optJSONArray("parts")
            if (ready && parts != null) for (i in 0 until parts.length()) {
                val data = parts.getJSONObject(i).optJSONObject("inlineData") ?: continue
                require(data.optString("mimeType").replace(" ", "") == "audio/pcm;rate=24000")
                val decoded = Base64.decode(data.getString("data"), Base64.DEFAULT)
                check(pcm?.enqueue(decoded) == true)
            }
            val cancelled = event.optJSONObject("toolCallCancellation")?.optJSONArray("ids")
            if (cancelled != null) for (i in 0 until cancelled.length()) images.cancelTool(cancelled.optString(i))
            val calls = event.optJSONObject("toolCall")?.optJSONArray("functionCalls")
            if (calls != null) for (i in 0 until calls.length()) {
                val call = calls.getJSONObject(i); val id = call.getString("id"); val name = call.getString("name")
                if (name != "request_camera_image" || !images.request(id)) send(GeminiEvents.toolResult(id, name, "unavailable"))
            }
        } catch (_: Exception) { fail("Fluxul Gemini nu poate fi redat în siguranță. Repornește conversația.") }
    }

    override suspend fun sendRequestedImage(capture: suspend () -> ByteArray) = images.submit(capture)
    override fun declineImage(reason: String) = images.cancel(reason)
    private fun send(event: JSONObject): Boolean {
        if (socket?.queueSize()?.let { it <= 128_000 } == true && socket?.send(event.toString()) == true) return true
        fail("Conexiunea Gemini nu poate transmite date. Repornește conversația."); return false
    }

    override fun beginLocalWarning(id: String) {
        warnings.add(id)
        // Disconnect before TTS, discard queued audio and prevent late model packets from resuming.
        val wasRunning = ready || state.value.phase == VoicePhase.Connecting
        cleanup()
        mutableState.value = VoiceState(message = if (wasRunning) "Anunțul local a oprit Gemini. Poți reporni conversația după anunț." else state.value.message,
            warningActive = true)
    }
    override fun endLocalWarning(id: String) { warnings.remove(id); mutableState.value = mutableState.value.copy(warningActive = warnings.isNotEmpty()) }
    override fun stop() { cleanup(); mutableState.value = VoiceState(warningActive = warnings.isNotEmpty()) }
    private fun fail(message: String) { cleanup(); mutableState.value = VoiceState(VoicePhase.Error, message, warningActive = warnings.isNotEmpty()) }
    private fun cleanup() {
        generation++; ready = false
        images.cancel("session_ended", notify = false)
        pcm?.close(); pcm = null
        socket?.cancel(); socket = null; http.cancel()
        connection?.cancel(); connection = null; timeout?.cancel(); timeout = null
        focus?.let { audio.abandonAudioFocusRequest(it) }; focus = null
        previousMode?.let { audio.mode = it }; previousMode = null
    }
    private fun acquireFocus(gen: Int) {
        val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setOnAudioFocusChangeListener({ change -> if (change != AudioManager.AUDIOFOCUS_GAIN) dispatch(gen) {
                fail("O altă aplicație folosește sunetul. Repornește conversația când este disponibil.")
            } }, Handler(Looper.getMainLooper())).build()
        check(audio.requestAudioFocus(request) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED)
        focus = request; previousMode = audio.mode; audio.mode = AudioManager.MODE_IN_COMMUNICATION
    }
    override fun close() {
        if (!closed) { stop(); closed = true; scope.cancel(); sockets.dispatcher.executorService.shutdown(); sockets.connectionPool.evictAll() }
    }
}

internal object GeminiEvents {
    fun audio(bytes: ByteArray) = JSONObject().put("realtimeInput", JSONObject().put("audio", JSONObject()
        .put("mimeType", "audio/pcm;rate=16000").put("data", Base64.encodeToString(bytes, Base64.NO_WRAP))))
    fun toolResult(id: String, name: String, status: String) = JSONObject().put("toolResponse", JSONObject()
        .put("functionResponses", JSONArray().put(JSONObject().put("id", id).put("name", name).put("response", JSONObject().put("status", status)))))
    fun image(bytes: ByteArray) = JSONObject().put("clientContent", JSONObject().put("turnComplete", true).put("turns", JSONArray().put(
        JSONObject().put("role", "user").put("parts", JSONArray()
            .put(JSONObject().put("inlineData", JSONObject().put("mimeType", "image/jpeg").put("data", Base64.encodeToString(bytes, Base64.NO_WRAP))))
            .put(JSONObject().put("text", "Descrie pe scurt în română indicii vizibile în această fotografie. Nu inventa distanțe sau pericole. Imaginea reprezintă un moment trecut; nu confirma siguranța traseului."))))))
}
