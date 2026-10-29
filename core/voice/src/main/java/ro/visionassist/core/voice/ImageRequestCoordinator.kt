package ro.visionassist.core.voice

import java.util.UUID
import kotlinx.coroutines.*

/** Main-thread confined consent boundary shared by the two real transports.
 * A remote tool ID is correlation data, never the identity of a local approval.
 * Dispatch is synchronous (no suspension); after it starts, sent data cannot be recalled.
 */
internal typealias ImageDispatchCommit = (sendImage: () -> Boolean) -> Boolean

internal class ImageRequestCoordinator(
    private val canSend: () -> Boolean,
    private val dispatch: (String?, ByteArray, ImageDispatchCommit) -> Unit,
    private val decline: (String, String) -> Unit,
    private val changed: (requested: Boolean, busy: Boolean) -> Unit,
    private val sent: () -> Unit,
    private val captureFailed: () -> Unit,
    private val timeoutMs: Long = 3_000
) {
    private class Request(val callId: String?, val identity: UUID = UUID.randomUUID())
    private class Capture(val request: Request, val identity: UUID = UUID.randomUUID()) {
        lateinit var task: Deferred<Unit>
    }
    private var pending: Request? = null
    private var active: Capture? = null

    fun request(callId: String): Boolean {
        if (pending != null || active != null) return false
        require(callId.isNotBlank())
        pending = Request(callId)
        publish()
        return true
    }

    fun cancel(reason: String, notify: Boolean = true) {
        val old = pending
        val capture = active
        // Revoke before cancelling a coroutine or invoking any transport callback.
        pending = null
        active = null
        capture?.task?.cancel(CancellationException("Image approval revoked"))
        publish()
        if (notify && old?.callId != null) decline(old.callId, reason)
    }

    fun cancelTool(callId: String) {
        if (pending?.callId == callId) cancel("request_cancelled", notify = false)
    }

    suspend fun submit(capture: suspend () -> ByteArray) = coroutineScope {
        if (!canSend() || active != null) return@coroutineScope
        // This method is called only by an explicit photo action. Manual photos also get
        // their own approval, even when there is no outstanding server tool request.
        val request = pending ?: Request(null).also { pending = it }
        val operation = Capture(request)
        val task = async(start = CoroutineStart.LAZY) {
            try {
                val bytes = withTimeout(timeoutMs) { capture() }
                ensureActive()
                if (!owns(operation) || !canSend()) return@async
                require(bytes.isNotEmpty() && bytes.size <= 44_000)
                var accepted = false
                dispatch(request.callId, bytes) { sink ->
                    ensureActive()
                    if (!owns(operation) || !canSend()) false
                    else {
                        // The transport must call this at its image send, after protocol
                        // preparation. No callback/suspension occurs before the actual sink.
                        pending = null
                        accepted = sink()
                        accepted
                    }
                }
                if (accepted) sent()
            } catch (_: TimeoutCancellationException) {
                failCapture(operation)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                failCapture(operation)
            }
        }
        operation.task = task
        active = operation
        publish()
        try {
            task.start()
            task.await()
        } finally {
            // A late completion/cancellation must not clear a newer request or its busy state.
            if (active?.identity == operation.identity) {
                val unanswered = pending?.identity == request.identity
                active = null
                if (unanswered) pending = null
                publish()
                if (unanswered && request.callId != null) decline(request.callId, "capture_cancelled")
            }
        }
    }

    private fun owns(capture: Capture) = active?.identity == capture.identity && pending?.identity == capture.request.identity
    private fun failCapture(capture: Capture) {
        if (!owns(capture)) return
        pending = null
        active = null
        publish()
        capture.request.callId?.let { decline(it, "camera_unavailable") }
        if (canSend() && pending == null && active == null) captureFailed()
    }
    private fun publish() = changed(pending?.callId != null, active != null)
}
