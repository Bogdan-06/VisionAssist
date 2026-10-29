package ro.visionassist.core.voice

enum class VoicePhase { Disconnected, Connecting, Listening, Speaking, Error }
data class VoiceState(
    val phase: VoicePhase = VoicePhase.Disconnected,
    val message: String = "Conversația este oprită.",
    val imageRequested: Boolean = false,
    val imageBusy: Boolean = false,
    val warningActive: Boolean = false
)

internal fun VoiceState.afterImageDispatch() = copy(message =
    if (phase == VoicePhase.Error) "Fotografia a fost trimisă, dar conversația s-a întrerupt. Repornește conversația."
    else "Fotografia solicitată a fost trimisă.")

data class BackendSettings(val url: String, val accessToken: String, val provider: VoiceProvider = VoiceProvider.OpenAI) {
    override fun toString() = "BackendSettings(provider=$provider, credentials=redacted)"
    fun validate(allowLoopbackHttp: Boolean) {
        val uri = java.net.URI(url)
        require(uri.userInfo == null && uri.query == null && uri.fragment == null && !uri.host.isNullOrBlank())
        val loopback = uri.host in setOf("127.0.0.1", "localhost", "10.0.2.2")
        require(uri.scheme == "https" || (allowLoopbackHttp && uri.scheme == "http" && loopback))
        require(accessToken.length >= 32 && !accessToken.startsWith("sk-") && !accessToken.startsWith("AIza"))
    }
}

/** Gate is also used for overlapping warnings; stale completion cannot release a newer warning. */
class AudioPriorityGate {
    private val holders = mutableSetOf<String>()
    var awaitingClear = false; private set
    val warningActive get() = holders.isNotEmpty()
    val muted get() = warningActive || awaitingClear
    fun begin(id: String) { holders.add(id); awaitingClear = true }
    fun end(id: String) { holders.remove(id) }
    fun cleared() { awaitingClear = false }
    fun requireClear() { awaitingClear = true }
    fun resetTransport() { awaitingClear = false }
}
