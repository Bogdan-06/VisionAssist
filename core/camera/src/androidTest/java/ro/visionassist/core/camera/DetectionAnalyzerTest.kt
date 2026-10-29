package ro.visionassist.core.camera

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.graphics.Rect
import androidx.camera.core.ImageInfo
import androidx.camera.core.ImageProxy
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import ro.visionassist.core.detection.DetectionFailure
import ro.visionassist.core.detection.ImageDetection
import java.lang.reflect.Proxy
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import ro.visionassist.core.ground.GroundFailure
import kotlinx.coroutines.*
import java.util.concurrent.Executors

class DetectionAnalyzerTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private fun proxy(bitmap: Bitmap?, rotation: Int, beforeConversion: () -> Unit = {}, closed: () -> Unit): ImageProxy {
        val info = Proxy.newProxyInstance(ImageInfo::class.java.classLoader,arrayOf(ImageInfo::class.java)) { _,method,_ ->
            when (method.name) { "getRotationDegrees" -> rotation; else -> error("Unexpected ${method.name}") }
        } as ImageInfo
        return Proxy.newProxyInstance(ImageProxy::class.java.classLoader,arrayOf(ImageProxy::class.java)) { _,method,_ ->
            when (method.name) {
                "getImageInfo" -> info
                "getWidth" -> bitmap?.width ?: 640
                "getHeight" -> bitmap?.height ?: 480
                "getCropRect" -> Rect(0,0,bitmap?.width ?: 640,bitmap?.height ?: 480)
                "toBitmap" -> { beforeConversion(); bitmap ?: error("Injected frame conversion failure") }
                "close" -> { closed(); null }
                else -> error("Unexpected ${method.name}")
            }
        } as ImageProxy
    }

    @Test fun cancelledAnalyzerCannotSupplyAnOldFrameToANewSessionPhoto() = runBlocking {
        val image = instrumentation.context.assets.open("cats_and_dogs.jpg").use { BitmapFactory.decodeStream(it) }
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        val broker = CameraSnapshotRequest()
        val failure = AtomicReference<DetectionFailure?>()
        val oldWorker = Executors.newSingleThreadExecutor()
        val old = DetectionAnalyzer(instrumentation.targetContext, { _,_,_,_ -> fail("Cancelled analyzer published") },
            { failure.set(it) }, snapshotRequest = broker)
        var fresh: DetectionAnalyzer? = null
        val oldTask = oldWorker.submit {
            old.initialize()
            old.analyze(proxy(image.copy(Bitmap.Config.ARGB_8888, false), 0, beforeConversion = {
                entered.countDown(); check(release.await(10, TimeUnit.SECONDS))
            }) {})
        }
        try {
            assertTrue(entered.await(10, TimeUnit.SECONDS))
            old.cancel()
            fresh = DetectionAnalyzer(instrumentation.targetContext, { _,_,_,_ -> }, { failure.set(it) }, snapshotRequest = broker)
            fresh.initialize()
            val requested = async(start = CoroutineStart.UNDISPATCHED) { broker.capture() }
            release.countDown(); oldTask.get(10, TimeUnit.SECONDS)
            oldWorker.submit { old.close() }.get(10, TimeUnit.SECONDS)
            assertFalse(requested.isCompleted)
            fresh.analyze(proxy(image.copy(Bitmap.Config.ARGB_8888, false), 0) {})
            assertTrue(requested.await().isNotEmpty())
            assertNull(failure.get())
        } finally {
            release.countDown(); oldTask.get(10, TimeUnit.SECONDS)
            oldWorker.submit { old.close() }.get(10, TimeUnit.SECONDS)
            oldWorker.shutdown(); fresh?.close(); broker.cancel(); image.recycle()
        }
    }

    @Test fun rotatedCameraFrameRunsRealModelAndClosesImage() {
        val upright = instrumentation.context.assets.open("cats_and_dogs.jpg").use { BitmapFactory.decodeStream(it) }
        val sensor = Bitmap.createBitmap(upright,0,0,upright.width,upright.height,Matrix().apply { postRotate(-90f) },false)
        var result: List<ImageDetection>? = null
        var failure: DetectionFailure? = null
        var closed = 0
        DetectionAnalyzer(instrumentation.targetContext, { objects,_,_,_ -> result = objects }, { failure = it }).use { analyzer ->
            analyzer.initialize()
            analyzer.analyze(proxy(sensor,90) { closed++ })
            assertNull(failure)
            assertTrue(result.toString(),result.orEmpty().any { it.label == "cat" || it.label == "dog" })
            assertEquals(1,closed)
        }
        upright.recycle()
    }

    @Test fun failedAndCancelledFramesAreClosedWithoutPublishingResults() {
        var closed = 0
        var failures = 0
        var results = 0
        DetectionAnalyzer(instrumentation.targetContext,{ _,_,_,_ -> results++ },{ failures++ }).use { analyzer ->
            analyzer.initialize()
            analyzer.analyze(proxy(null,0) { closed++ })
            assertEquals(1,failures)
            analyzer.analyze(proxy(null,0) { closed++ })
            analyzer.cancel()
            analyzer.analyze(proxy(null,0) { closed++ })
        }
        assertEquals(3,closed)
        assertEquals(0,results)
        assertEquals(1,failures)
    }

    @Test fun groundAndCocoShareFramesWithoutRecyclingEachOthersPixels() {
        val source=instrumentation.context.assets.open("cats_and_dogs.jpg").use { BitmapFactory.decodeStream(it) }
        val groundDone=CountDownLatch(1)
        val groundFailure=AtomicReference<GroundFailure?>()
        val objectResults=AtomicInteger()
        var closed=0
        try {
            DetectionAnalyzer(instrumentation.targetContext,
                onResult={ _,_,_,_ -> objectResults.incrementAndGet() },
                onError={ fail("COCO pipeline failed: $it") },groundEnabled=true,
                onGroundResult={ frame,_,_ ->
                    assertEquals(source.width,frame.width)
                    assertEquals(source.height,frame.height)
                    groundDone.countDown()
                },onGroundError={ groundFailure.set(it); groundDone.countDown() }).use { analyzer ->
                analyzer.initialize()
                repeat(8) {
                    analyzer.analyze(proxy(source.copy(Bitmap.Config.ARGB_8888,false),0) { closed++ })
                    Thread.sleep(150)
                }
                assertTrue(groundDone.await(10,TimeUnit.SECONDS))
                assertNull(groundFailure.get())
                assertTrue(objectResults.get()>0)
                assertEquals(8,closed)
            }
        } finally { source.recycle() }
    }
}
