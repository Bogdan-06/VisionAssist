package ro.visionassist.core.camera

import android.graphics.Bitmap
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.withTimeout
import java.io.ByteArrayOutputStream

/** No retained camera frame. Only an explicit request consumes one subsequent analyzer frame. */
class CameraSnapshotRequest internal constructor(private val encode: (Bitmap) -> ByteArray) {
    constructor() : this(::encodeJpeg)
    internal class Source
    private class Request(val source: Source, val result: CompletableDeferred<ByteArray>) {
        var encoding = false
    }
    private val lock = Any()
    private var source: Source? = null
    private var pending: Request? = null

    internal fun beginSource(): Source {
        val fresh = Source()
        val old = synchronized(lock) { source = fresh; pending.also { pending = null } }
        old?.result?.cancel()
        return fresh
    }

    internal fun endSource(owner: Source) {
        val old = synchronized(lock) {
            if (source !== owner) return
            source = null
            pending.also { pending = null }
        }
        old?.result?.cancel()
    }

    suspend fun capture(): ByteArray {
        val result = CompletableDeferred<ByteArray>()
        val request = synchronized(lock) {
            val active = checkNotNull(source) { "Camera session is unavailable" }
            check(pending == null) { "A photograph is already pending" }
            Request(active, result).also { pending = it }
        }
        return try {
            val bytes = withTimeout(2_500) { result.await() }
            synchronized(lock) { check(source === request.source) { "Camera session changed" } }
            bytes
        } finally {
            synchronized(lock) { if (pending === request) pending = null }
            result.cancel()
        }
    }

    internal fun offer(upright: Bitmap, owner: Source) {
        // Retain ownership while JPEG encoding runs, so cancel() can still revoke it.
        val request = synchronized(lock) {
            val next = pending ?: return
            if (source !== owner || next.source !== owner || !next.result.isActive || next.encoding) return
            next.encoding = true
            next
        }
        try {
            val bytes = encode(upright)
            val owned = synchronized(lock) {
                if (source === owner && pending === request) { pending = null; true } else false
            }
            if (owned) request.result.complete(bytes)
        } catch (error: Exception) {
            val owned = synchronized(lock) {
                if (pending === request) { pending = null; true } else false
            }
            if (owned) request.result.completeExceptionally(error)
        }
    }
    fun cancel() {
        val old = synchronized(lock) { pending.also { pending = null } }
        old?.result?.cancel()
    }

    companion object {
        private fun encodeJpeg(upright: Bitmap): ByteArray {
            var edge = 512
            while (edge >= 128) {
                val scale = minOf(1f, edge.toFloat() / maxOf(upright.width, upright.height))
                val small = Bitmap.createScaledBitmap(upright, (upright.width * scale).toInt().coerceAtLeast(1),
                    (upright.height * scale).toInt().coerceAtLeast(1), true)
                val bytes = try { ByteArrayOutputStream().use { output ->
                    check(small.compress(Bitmap.CompressFormat.JPEG, 70, output)); output.toByteArray()
                } } finally { if (small !== upright) small.recycle() }
                if (bytes.size <= 44_000) return bytes
                edge /= 2
            }
            throw IllegalStateException("Image too large")
        }
    }
}
