package ro.visionassist.core.voice

import android.content.Context
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

enum class VoiceProvider(val label: String) { OpenAI("OpenAI"), Gemini("Google Gemini") }

interface VoiceClient : AutoCloseable {
    val state: StateFlow<VoiceState>
    fun start(settings: BackendSettings)
    fun stop()
    fun beginLocalWarning(id: String)
    fun endLocalWarning(id: String)
    suspend fun sendRequestedImage(capture: suspend () -> ByteArray)
    fun declineImage(reason: String = "user_declined")
}

/** Owns exactly one transport; switching providers disposes the previous microphone and socket. */
class SelectableVoiceClient(private val context: Context, private val allowLoopbackHttp: Boolean) : VoiceClient {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val mutableState = MutableStateFlow(VoiceState())
    override val state = mutableState.asStateFlow()
    private var client: VoiceClient? = null
    private var provider: VoiceProvider? = null
    private var collector: Job? = null
    private var closed = false
    private val warnings = mutableSetOf<String>()
    override fun start(settings: BackendSettings) {
        if (closed || warnings.isNotEmpty()) return
        if (provider != settings.provider) {
            collector?.cancel(); client?.close()
            client = when (settings.provider) {
                VoiceProvider.OpenAI -> RealtimeVoiceClient(context, allowLoopbackHttp)
                VoiceProvider.Gemini -> GeminiVoiceClient(context, allowLoopbackHttp)
            }
            provider = settings.provider
            collector = scope.launch { client!!.state.collect { mutableState.value = it } }
        }
        client!!.start(settings)
    }
    override fun stop() { client?.stop(); mutableState.value = client?.state?.value ?: VoiceState(warningActive = warnings.isNotEmpty()) }
    override fun beginLocalWarning(id: String) {
        warnings.add(id); client?.beginLocalWarning(id)
        mutableState.value = (client?.state?.value ?: mutableState.value).copy(warningActive = true)
    }
    override fun endLocalWarning(id: String) {
        warnings.remove(id); client?.endLocalWarning(id)
        mutableState.value = (client?.state?.value ?: mutableState.value).copy(warningActive = warnings.isNotEmpty())
    }
    override suspend fun sendRequestedImage(capture: suspend () -> ByteArray) { client?.sendRequestedImage(capture) }
    override fun declineImage(reason: String) { client?.declineImage(reason) }
    override fun close() { if (!closed) { closed = true; collector?.cancel(); client?.close(); scope.cancel() } }
}
