package ro.visionassist.core.camera

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class CameraSnapshotTest {
    @Test fun cancellationDuringEncodingCannotCompleteOldRequestOrConsumeReplacement() = runBlocking {
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        var calls = 0
        val broker = CameraSnapshotRequest {
            if (++calls == 1) {
                entered.countDown()
                check(release.await(5, TimeUnit.SECONDS))
            }
            byteArrayOf(calls.toByte())
        }
        val source = broker.beginSource()
        val bitmap = Bitmap.createBitmap(16, 16, Bitmap.Config.ARGB_8888)
        val first = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
        val encoding = launch(Dispatchers.Default) { broker.offer(bitmap, source) }
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            broker.cancel()
            val next = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
            release.countDown(); encoding.join(); first.join()
            assertTrue(first.isCancelled)
            assertFalse(next.isCompleted)
            broker.offer(bitmap, source)
            assertArrayEquals(byteArrayOf(2), next.await())
        } finally { release.countDown(); encoding.join(); broker.cancel(); bitmap.recycle() }
    }
    @Test fun capturesOnlyOneFrameAfterExplicitRequestAndBoundsPayload() = runBlocking {
        val broker = CameraSnapshotRequest()
        val source = broker.beginSource()
        val first = Bitmap.createBitmap(640, 480, Bitmap.Config.ARGB_8888).apply { eraseColor(android.graphics.Color.RED) }
        val second = Bitmap.createBitmap(640, 480, Bitmap.Config.ARGB_8888).apply { eraseColor(android.graphics.Color.BLUE) }
        try {
            broker.offer(first, source) // No request: this image must not be cached.
            val result = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
            assertFalse(result.isCompleted)
            broker.offer(second, source)
            val jpeg = result.await(); assertTrue(jpeg.size <= 44_000)
            val decoded = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size)
            try { assertTrue(android.graphics.Color.blue(decoded.getPixel(10, 10)) > 240); assertTrue(decoded.width <= 512) }
            finally { decoded.recycle() }
            assertFalse(first.isRecycled); assertFalse(second.isRecycled)
        } finally { first.recycle(); second.recycle() }
    }
    @Test fun cancellationDiscardsRequestAndAllowsNextExplicitCapture() = runBlocking {
        val broker = CameraSnapshotRequest()
        val source = broker.beginSource()
        val pending = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
        broker.cancel(); assertThrows(CancellationException::class.java) { runBlocking { pending.await() } }
        val next = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
        val bitmap = Bitmap.createBitmap(128, 128, Bitmap.Config.ARGB_8888)
        try { broker.offer(bitmap, source); assertTrue(next.await().isNotEmpty()) } finally { bitmap.recycle() }
    }

    @Test fun oldCameraSourceCannotSatisfyOrCancelANewCameraRequest() = runBlocking {
        val broker = CameraSnapshotRequest()
        val old = broker.beginSource()
        val first = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
        val current = broker.beginSource()
        first.join(); assertTrue(first.isCancelled)
        val next = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
        val bitmap = Bitmap.createBitmap(16, 16, Bitmap.Config.ARGB_8888)
        try {
            broker.offer(bitmap, old); broker.endSource(old)
            assertFalse(next.isCompleted)
            broker.offer(bitmap, current)
            assertTrue(next.await().isNotEmpty())
        } finally { broker.endSource(current); bitmap.recycle() }
    }
}
