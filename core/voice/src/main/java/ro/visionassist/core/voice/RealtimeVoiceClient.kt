package ro.visionassist.core.voice

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.os.Handler
import android.os.Looper
import android.util.Base64
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject
import org.webrtc.*
import org.webrtc.audio.JavaAudioDeviceModule
import java.nio.ByteBuffer
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Foreground owner. Native callbacks are marshalled to main; generations reject late callbacks. */
class RealtimeVoiceClient(context: Context, private val allowLoopbackHttp: Boolean = false) : VoiceClient {
    private val app = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val mutableState = MutableStateFlow(VoiceState())
    override val state = mutableState.asStateFlow()
    private val audio = app.getSystemService(AudioManager::class.java)
    private val connectivity = app.getSystemService(ConnectivityManager::class.java)
    private val priority = AudioPriorityGate()
    private var factory: PeerConnectionFactory? = null
    private var audioDevice: JavaAudioDeviceModule? = null
    private var peer: PeerConnection? = null
    private var source: AudioSource? = null
    private var microphone: AudioTrack? = null
    private var channel: DataChannel? = null
    private var http: RealtimeHttp? = null
    private var work: Job? = null
    private var watchdog: Job? = null
    private var clearTimeout: Job? = null
    private var generation = 0
    private var wanted = false
    private var closed = false
    private var ready = false
    private var sessionSeen = false
    private var attempts = 0
    private var settings: BackendSettings? = null
    private var pendingImageCall: String? = null
    private var focus: AudioFocusRequest? = null
    private var previousMode: Int? = null
    private var networkRegistered = false
    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onLost(network: Network) { scope.launch { if (wanted && !online()) reconnect("Conexiunea la internet s-a pierdut.") } }
    }

    override fun start(settings: BackendSettings) {
        if (closed) return
        stop()
        try { settings.validate(allowLoopbackHttp) }
        catch (_: Exception) { fail("Configurează adresa HTTPS și codul de acces al serverului. Nu introduce cheia OpenAI pe telefon."); return }
        if (app.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            fail("Permite accesul la microfon pentru conversație."); return
        }
        this.settings = settings; wanted = true; attempts = 0
        connectivity.registerDefaultNetworkCallback(networkCallback); networkRegistered = true
        connect()
    }

    private fun connect() {
        val config = settings ?: return
        val gen = ++generation
        mutableState.value = VoiceState(VoicePhase.Connecting, "Se conectează la asistent…", warningActive = priority.warningActive)
        work = scope.launch {
            try {
                check(online())
                val transport = RealtimeHttp().also { http = it }
                val secret = transport.clientSecret(config)
                ensureActive()
                if (gen != generation) return@launch
                acquireAudioFocus()
                initializeNative(gen)
                val rtc = PeerConnection.RTCConfiguration(emptyList()).apply {
                    sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN
                }
                peer = factory!!.createPeerConnection(rtc, observer(gen)) ?: error("Cannot create peer")
                source = factory!!.createAudioSource(MediaConstraints())
                microphone = factory!!.createAudioTrack("visionassist-microphone", source)
                microphone!!.setEnabled(false) // Enabled only after session and channel are ready.
                peer!!.addTrack(microphone, listOf("visionassist"))
                channel = peer!!.createDataChannel("oai-events", DataChannel.Init()).also { data ->
                    data.registerObserver(object : DataChannel.Observer {
                        override fun onBufferedAmountChange(previousAmount: Long) = Unit
                        override fun onStateChange() { dispatch(gen) {
                            if (data.state() == DataChannel.State.OPEN) becomeReady()
                            else if (data.state() == DataChannel.State.CLOSED && wanted) reconnect("Conversația s-a deconectat.")
                        } }
                        override fun onMessage(buffer: DataChannel.Buffer) {
                            if (buffer.binary || buffer.data.remaining() > 1_000_000) return
                            val bytes = ByteArray(buffer.data.remaining()); buffer.data.get(bytes)
                            dispatch(gen) { receive(String(bytes, Charsets.UTF_8)) }
                        }
                    })
                }
                val offer = createOffer(peer!!)
                setDescription(peer!!, offer, local = true)
                val answer = transport.answer(secret, offer.description)
                ensureActive()
                if (gen != generation) return@launch
                setDescription(peer!!, SessionDescription(SessionDescription.Type.ANSWER, answer), local = false)
                watchdog = scope.launch { delay(25_000); if (gen == generation && !ready) reconnect("Conexiunea audio nu a putut fi stabilită.") }
            } catch (_: CancellationException) { /* explicit stop or old generation */ }
            catch (e: Exception) {
                if (gen == generation && wanted) {
                    if (e is VoiceHttpFailure && e.status in setOf(400, 401, 403, 404, 429, 503)) {
                        fail(when {
                            e.code == "credit_balance_exhausted" -> "Contul OpenAI nu mai are credite API. Verifică facturarea. Camera continuă local."
                            e.code in setOf("insufficient_quota", "upstream_quota_exceeded") -> "Cota API OpenAI este epuizată. Verifică soldul și limitele contului. Camera continuă local."
                            e.code in setOf("organization_spend_limit_exceeded", "project_spend_limit_exceeded", "organization_usage_limit_exceeded") -> "Limita de cheltuieli sau utilizare API a fost atinsă. Verifică limitele contului OpenAI. Camera continuă local."
                            e.status == 429 -> "Limita de solicitări a fost atinsă. Încearcă mai târziu."
                            else -> "Verifică serverul și codul de acces. Camera continuă local."
                        })
                    } else reconnect("Conectarea a eșuat. Camera continuă local.")
                }
            } catch (_: LinkageError) { if (gen == generation) fail("Componenta audio nu este disponibilă pe acest telefon.") }
        }
    }

    private fun initializeNative(gen: Int) {
        synchronized(nativeLock) {
            if (!initialized) {
                PeerConnectionFactory.initialize(PeerConnectionFactory.InitializationOptions.builder(app).createInitializationOptions())
                initialized = true
            }
        }
        fun audioError() = dispatch(gen) { if (wanted) fail("Microfonul sau redarea audio nu sunt disponibile. Verifică permisiunile și repornește conversația.") }
        audioDevice = JavaAudioDeviceModule.builder(app)
            .setAudioRecordErrorCallback(object : JavaAudioDeviceModule.AudioRecordErrorCallback {
                override fun onWebRtcAudioRecordInitError(error: String) = audioError()
                override fun onWebRtcAudioRecordStartError(code: JavaAudioDeviceModule.AudioRecordStartErrorCode, error: String) = audioError()
                override fun onWebRtcAudioRecordError(error: String) = audioError()
            })
            .setAudioTrackErrorCallback(object : JavaAudioDeviceModule.AudioTrackErrorCallback {
                override fun onWebRtcAudioTrackInitError(error: String) = audioError()
                override fun onWebRtcAudioTrackStartError(code: JavaAudioDeviceModule.AudioTrackStartErrorCode, error: String) = audioError()
                override fun onWebRtcAudioTrackError(error: String) = audioError()
            }).createAudioDeviceModule()
        audioDevice!!.setMicrophoneMute(true); audioDevice!!.setSpeakerMute(true)
        factory = PeerConnectionFactory.builder().setAudioDeviceModule(audioDevice).createPeerConnectionFactory()
    }
    private fun observer(gen: Int) = object : PeerConnection.Observer {
        override fun onSignalingChange(state: PeerConnection.SignalingState) = Unit
        override fun onIceConnectionChange(state: PeerConnection.IceConnectionState) = Unit
        override fun onIceConnectionReceivingChange(receiving: Boolean) = Unit
        override fun onIceGatheringChange(state: PeerConnection.IceGatheringState) = Unit
        override fun onIceCandidate(candidate: IceCandidate) = Unit // OpenAI answers with reachable ICE candidates; no trickle endpoint.
        override fun onIceCandidatesRemoved(candidates: Array<out IceCandidate>) = Unit
        override fun onAddStream(stream: MediaStream) = Unit
        override fun onRemoveStream(stream: MediaStream) = Unit
        override fun onDataChannel(data: DataChannel) = Unit
        override fun onRenegotiationNeeded() = Unit
        override fun onAddTrack(receiver: RtpReceiver, mediaStreams: Array<out MediaStream>) = Unit
        override fun onConnectionChange(state: PeerConnection.PeerConnectionState) { dispatch(gen) {
            if (wanted && state in setOf(PeerConnection.PeerConnectionState.FAILED, PeerConnection.PeerConnectionState.DISCONNECTED)) {
                reconnect("Legătura audio s-a întrerupt.")
            }
        } }
    }
    private fun dispatch(gen: Int, action: () -> Unit) { scope.launch { if (gen == generation && !closed) action() } }
    private fun becomeReady() {
        if (channel?.state() != DataChannel.State.OPEN || !sessionSeen) return
        ready = true; watchdog?.cancel()
        mutableState.value = mutableState.value.copy(phase = VoicePhase.Listening, message = "Asistentul ascultă. Vorbește în română.")
        applyMute()
        if (priority.muted) clearRemoteAudio()
    }
    private fun receive(raw: String) {
        val event = try { JSONObject(raw) } catch (_: Exception) { return }
        when (event.optString("type")) {
            "session.created" -> { sessionSeen = true; becomeReady() }
            "output_audio_buffer.started" -> if (priority.muted) clearRemoteAudio()
                else mutableState.value = mutableState.value.copy(phase = VoicePhase.Speaking, message = "Asistentul vorbește.")
            "output_audio_buffer.stopped" -> if (ready) mutableState.value = mutableState.value.copy(phase = VoicePhase.Listening, message = "Asistentul ascultă.")
            "output_audio_buffer.cleared" -> {
                clearTimeout?.cancel(); priority.cleared(); applyMute()
                if (ready) mutableState.value = mutableState.value.copy(phase = VoicePhase.Listening)
            }
            "response.function_call_arguments.done" -> {
                val callId = event.optString("call_id")
                if (event.optString("name") == "request_camera_image" && callId.isNotBlank()) {
                    if (pendingImageCall == null) {
                        pendingImageCall = callId
                        mutableState.value = mutableState.value.copy(imageRequested = true, message = "Confirmă trimiterea unei fotografii pe telefon.")
                    } else send(RealtimeEvents.toolResult(callId, "another_request_pending"))
                }
            }
            "error" -> {
                val code = event.optJSONObject("error")?.optString("code")
                // Cancel is deliberately safe when VAD finished the response concurrently.
                if (code != "response_cancel_not_active") fail("Serviciul vocal a raportat o eroare. Repornește conversația.")
            }
            "response.done" -> if (event.optJSONObject("response")?.optString("status") == "failed") fail("Răspunsul vocal nu a putut fi generat.")
        }
    }

    override fun beginLocalWarning(id: String) {
        priority.begin(id); applyMute() // Native mute BEFORE network cancellation or TTS.
        mutableState.value = mutableState.value.copy(warningActive = true)
        if (ready) clearRemoteAudio()
    }
    override fun endLocalWarning(id: String) {
        priority.end(id); applyMute()
        mutableState.value = mutableState.value.copy(warningActive = priority.warningActive)
    }
    private fun clearRemoteAudio() {
        priority.requireClear(); applyMute()
        send(RealtimeEvents.simple("response.cancel"))
        send(RealtimeEvents.simple("output_audio_buffer.clear"))
        send(RealtimeEvents.simple("input_audio_buffer.clear"))
        clearTimeout?.cancel()
        clearTimeout = scope.launch { delay(3_000); if (priority.awaitingClear && wanted) fail("Asistentul a fost oprit pentru anunțul local. Îl poți reporni.") }
    }
    private fun applyMute() {
        val muted = !ready || priority.muted
        audioDevice?.setSpeakerMute(muted); audioDevice?.setMicrophoneMute(muted)
        microphone?.setEnabled(!muted)
    }

    override suspend fun sendRequestedImage(capture: suspend () -> ByteArray) {
        if (!ready || priority.muted || mutableState.value.imageBusy) return
        val gen = generation
        mutableState.value = mutableState.value.copy(imageBusy = true)
        try {
            val bytes = withTimeout(3_000) { capture() }
            if (gen != generation || !ready || priority.muted) return
            send(RealtimeEvents.simple("response.cancel"))
            send(RealtimeEvents.simple("output_audio_buffer.clear"))
            pendingImageCall?.let { check(send(RealtimeEvents.toolResult(it, "user_confirmed_image_follows"))) }
            pendingImageCall = null
            check(send(RealtimeEvents.image(bytes, Base64.encodeToString(bytes, Base64.NO_WRAP))))
            check(send(RealtimeEvents.simple("response.create")))
            mutableState.value = mutableState.value.copy(imageRequested = false, message = "Fotografia solicitată a fost trimisă.")
        } catch (_: CancellationException) {
            if (gen == generation) declineImage("capture_cancelled")
        } catch (_: Exception) {
            if (gen == generation) { declineImage("camera_unavailable"); mutableState.value = mutableState.value.copy(message = "Nu există o imagine nouă. Pornește camera și încearcă din nou.") }
        } finally { if (gen == generation) mutableState.value = mutableState.value.copy(imageBusy = false) }
    }
    override fun declineImage(reason: String) {
        pendingImageCall?.let { send(RealtimeEvents.toolResult(it, reason)); send(RealtimeEvents.simple("response.create")) }
        pendingImageCall = null
        mutableState.value = mutableState.value.copy(imageRequested = false)
    }
    private fun send(event: JSONObject): Boolean {
        val data = channel ?: return false
        return try {
            check(data.state() == DataChannel.State.OPEN)
            val bytes = event.toString().toByteArray(Charsets.UTF_8)
            check(bytes.size < 64_000 && data.bufferedAmount() < 128_000)
            check(data.send(DataChannel.Buffer(ByteBuffer.wrap(bytes), false)))
            true
        } catch (_: Exception) {
            fail("Canalul conversației s-a întrerupt. Camera continuă local.")
            false
        }
    }
    private fun online(): Boolean = connectivity.getNetworkCapabilities(connectivity.activeNetwork)
        ?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true

    private fun reconnect(reason: String) {
        if (!wanted) return
        cleanup()
        if (++attempts > 2) { fail("$reason Apasă pentru a încerca din nou."); return }
        mutableState.value = VoiceState(VoicePhase.Connecting, "$reason Se reîncearcă; conversația anterioară nu este reluată.", warningActive = priority.warningActive)
        work = scope.launch { delay(attempts * 2_000L); if (wanted) connect() }
    }
    private fun fail(message: String) {
        stop(); mutableState.value = VoiceState(VoicePhase.Error, message, warningActive = priority.warningActive)
    }
    override fun stop() {
        wanted = false; cleanup()
        if (networkRegistered) { connectivity.unregisterNetworkCallback(networkCallback); networkRegistered = false }
        mutableState.value = VoiceState(warningActive = priority.warningActive)
    }
    private fun cleanup() {
        ++generation; ready = false; sessionSeen = false; pendingImageCall = null
        work?.cancel(); work = null; watchdog?.cancel(); clearTimeout?.cancel()
        http?.cancel(); http = null
        audioDevice?.setSpeakerMute(true); audioDevice?.setMicrophoneMute(true)
        channel?.unregisterObserver(); channel?.close(); channel?.dispose(); channel = null
        peer?.close(); peer?.dispose(); peer = null
        microphone?.dispose(); microphone = null; source?.dispose(); source = null
        factory?.dispose(); factory = null; audioDevice?.release(); audioDevice = null
        focus?.let { audio.abandonAudioFocusRequest(it) }; focus = null
        previousMode?.let { audio.mode = it }; previousMode = null
        priority.resetTransport()
    }
    private fun acquireAudioFocus() {
        val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setOnAudioFocusChangeListener({ change ->
                if (change < 0) scope.launch { if (wanted) fail("Conversația a fost oprită de o altă aplicație audio. O poți reporni.") }
            }, Handler(Looper.getMainLooper())).build()
        check(audio.requestAudioFocus(request) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED)
        focus = request; previousMode = audio.mode; audio.mode = AudioManager.MODE_IN_COMMUNICATION
    }
    override fun close() { if (!closed) { stop(); closed = true; scope.cancel() } }

    private suspend fun createOffer(pc: PeerConnection): SessionDescription = suspendCancellableCoroutine { continuation ->
        pc.createOffer(object : SdpObserver {
            override fun onCreateSuccess(sdp: SessionDescription) { if (continuation.isActive) continuation.resume(sdp) }
            override fun onCreateFailure(error: String) { if (continuation.isActive) continuation.resumeWithException(IllegalStateException("SDP offer failed")) }
            override fun onSetSuccess() = Unit
            override fun onSetFailure(error: String) = Unit
        }, MediaConstraints())
    }
    private suspend fun setDescription(pc: PeerConnection, sdp: SessionDescription, local: Boolean): Unit = suspendCancellableCoroutine { continuation ->
        val observer = object : SdpObserver {
            override fun onSetSuccess() { if (continuation.isActive) continuation.resume(Unit) }
            override fun onSetFailure(error: String) { if (continuation.isActive) continuation.resumeWithException(IllegalStateException("SDP answer failed")) }
            override fun onCreateSuccess(sdp: SessionDescription) = Unit
            override fun onCreateFailure(error: String) = Unit
        }
        if (local) pc.setLocalDescription(observer, sdp) else pc.setRemoteDescription(observer, sdp)
    }
    companion object { private val nativeLock = Any(); private var initialized = false }
}
