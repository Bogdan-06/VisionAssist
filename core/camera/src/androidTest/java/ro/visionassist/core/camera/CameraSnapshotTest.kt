package ro.visionassist.core.camera

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test

class CameraSnapshotTest {
    @Test fun capturesOnlyOneFrameAfterExplicitRequestAndBoundsPayload() = runBlocking {
        val broker = CameraSnapshotRequest()
        val first = Bitmap.createBitmap(640, 480, Bitmap.Config.ARGB_8888).apply { eraseColor(android.graphics.Color.RED) }
        val second = Bitmap.createBitmap(640, 480, Bitmap.Config.ARGB_8888).apply { eraseColor(android.graphics.Color.BLUE) }
        try {
            broker.offer(first) // No request: this image must not be cached.
            val result = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
            assertFalse(result.isCompleted)
            broker.offer(second)
            val jpeg = result.await(); assertTrue(jpeg.size <= 44_000)
            val decoded = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size)
            try { assertTrue(android.graphics.Color.blue(decoded.getPixel(10, 10)) > 240); assertTrue(decoded.width <= 512) }
            finally { decoded.recycle() }
            assertFalse(first.isRecycled); assertFalse(second.isRecycled)
        } finally { first.recycle(); second.recycle() }
    }
    @Test fun cancellationDiscardsRequestAndAllowsNextExplicitCapture() = runBlocking {
        val broker = CameraSnapshotRequest()
        val pending = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
        broker.cancel(); assertThrows(CancellationException::class.java) { runBlocking { pending.await() } }
        val next = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
        val bitmap = Bitmap.createBitmap(128, 128, Bitmap.Config.ARGB_8888)
        try { broker.offer(bitmap); assertTrue(next.await().isNotEmpty()) } finally { bitmap.recycle() }
    }
}
