package ro.visionassist.core.camera

import android.graphics.Bitmap
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.withTimeout
import java.io.ByteArrayOutputStream
import java.util.concurrent.atomic.AtomicReference

/** No retained camera frame. Only an explicit request consumes one subsequent analyzer frame. */
class CameraSnapshotRequest {
    private val pending = AtomicReference<CompletableDeferred<ByteArray>?>(null)
    suspend fun capture(): ByteArray {
        val result = CompletableDeferred<ByteArray>()
        check(pending.compareAndSet(null, result)) { "A photograph is already pending" }
        return try { withTimeout(2_500) { result.await() } }
        finally { pending.compareAndSet(result, null); result.cancel() }
    }
    internal fun offer(upright: Bitmap) {
        val request = pending.getAndSet(null) ?: return
        if (!request.isActive) return
        try {
            var edge = 512
            while (edge >= 128) {
                val scale = minOf(1f, edge.toFloat() / maxOf(upright.width, upright.height))
                val small = Bitmap.createScaledBitmap(upright, (upright.width * scale).toInt().coerceAtLeast(1),
                    (upright.height * scale).toInt().coerceAtLeast(1), true)
                val bytes = try { ByteArrayOutputStream().use { output ->
                    check(small.compress(Bitmap.CompressFormat.JPEG, 70, output)); output.toByteArray()
                } } finally { if (small !== upright) small.recycle() }
                if (bytes.size <= 44_000) { request.complete(bytes); return }
                edge /= 2
            }
            request.completeExceptionally(IllegalStateException("Image too large"))
        } catch (error: Exception) { request.completeExceptionally(error) }
    }
    fun cancel() { pending.getAndSet(null)?.cancel() }
}
