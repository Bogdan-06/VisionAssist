package ro.visionassist.core.ground

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.SystemClock
import android.os.Debug
import android.os.Build
import android.util.Log
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import org.json.JSONObject

class GroundInferenceTest {
    @Test fun packagedModelRunsOnRealPhotographWithoutTakingBitmapOwnership() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val bitmap=instrumentation.context.assets.open("rdd_pothole.jpg").use { BitmapFactory.decodeStream(it) }
        val beforeMemory=Debug.MemoryInfo().also { Debug.getMemoryInfo(it) }
        try {
            GroundHazardDetector(instrumentation.targetContext).use { detector ->
                val times=mutableListOf<Long>()
                val processing=mutableListOf<Long>()
                repeat(20) {
                    val result=detector.detect(bitmap,SystemClock.elapsedRealtime())
                    assertEquals(bitmap.width,result.width)
                    assertFalse(bitmap.isRecycled)
                    assertTrue("The selected real-photo fixture must produce actual candidates",result.candidates.isNotEmpty())
                    assertTrue(result.processingMs >= result.inferenceMs)
                    result.candidates.forEach { candidate ->
                        assertTrue(candidate.confidence.isFinite() && candidate.confidence in .3f..1f)
                        assertTrue(candidate.bounds.left >= 0 && candidate.bounds.right <= 1)
                        assertTrue(candidate.bounds.top >= 0 && candidate.bounds.bottom <= 1)
                    }
                    times += result.inferenceMs
                    processing += result.processingMs
                }
                times.sort()
                processing.sort()
                Log.i("GroundBenchmark","device=${Build.MODEL} fixture iterations=20 inference_ms median=${times[10]} p95=${times[18]}; fixture timing is not sustained camera throughput")
                Log.i("GroundBenchmark","frame_processing_ms median=${processing[10]} p95=${processing[18]}; includes resizing, inference and decoding, excludes CameraX delivery")
                val duringMemory=Debug.MemoryInfo().also { Debug.getMemoryInfo(it) }
                Log.i("GroundBenchmark","process_pss_kb before=${beforeMemory.totalPss} loaded_after_20=${duringMemory.totalPss}; includes runtime/test harness, not isolated model allocation")
            }
        } finally { bitmap.recycle() }
    }

    @Test fun losslessPreparedInputMatchesPythonInterpreterAndDecoder() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val metadata=instrumentation.context.assets.open("rdd_pothole.json").bufferedReader().use { JSONObject(it.readText()) }
        assertEquals(GroundHazardDetector.MODEL_SHA256,metadata.getString("model_sha256"))
        val expected=metadata.getJSONArray("preprocessed_predictions")
        assertTrue("Parity fixture must contain real predictions",expected.length()>0)
        val bitmap=instrumentation.context.assets.open("rdd_preprocessed.png").use { BitmapFactory.decodeStream(it) }
        try {
            GroundHazardDetector(instrumentation.targetContext).use { detector ->
                val actual=detector.detect(bitmap,SystemClock.elapsedRealtime()).candidates
                assertEquals(expected.length(),actual.size)
                for (i in 0 until expected.length()) {
                    val candidate=expected.getJSONObject(i)
                    val box=candidate.getJSONArray("box")
                    val bounds=GroundBox(box.getDouble(0).toFloat()/320,box.getDouble(1).toFloat()/320,
                        box.getDouble(2).toFloat()/320,box.getDouble(3).toFloat()/320)
                    val closest=requireNotNull(actual.maxByOrNull { it.bounds.iou(bounds) })
                    assertTrue("Python/Android box mismatch",closest.bounds.iou(bounds)>.99f)
                    assertEquals(candidate.getDouble("score"),closest.confidence.toDouble(),.001)
                }
                // Actual model output reaches the temporal filter. Production warnings remain gated.
                val policy=GroundWarningPolicy()
                assertNull(policy.observe(actual,1_000,1_000))
                assertNull(policy.observe(actual,1_400,1_400))
                assertNotNull(policy.observe(actual,1_800,1_800))
                assertNull(policy.observe(actual,2_200,2_200))
            }
        } finally { bitmap.recycle() }
    }

    @Test fun closeCanRaceFrameSubmissionWithoutRejectedTasks() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val bitmap=Bitmap.createBitmap(640,480,Bitmap.Config.ARGB_8888)
        val failure=AtomicReference<Throwable?>()
        try {
            repeat(5) {
                val worker=GroundWorker(context) { failure.set(AssertionError(it.toString())) }
                val start=CountDownLatch(1)
                val producer=Thread {
                    try { start.await(); repeat(100) { worker.offer(bitmap,SystemClock.elapsedRealtime()) { _, _ -> } } }
                    catch (error:Throwable) { failure.set(error) }
                }
                producer.start(); start.countDown(); worker.close(); producer.join(5_000)
                assertFalse("Producer did not finish",producer.isAlive)
                assertNull(failure.get())
                assertFalse(bitmap.isRecycled)
            }
        } finally { bitmap.recycle() }
    }

    @Test fun workerCopiesBeforeProducerRecyclesAndBoundsFrameBacklog() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val error=AtomicReference<GroundFailure?>()
        val done=CountDownLatch(1)
        val metrics=AtomicReference<GroundMetrics?>()
        val worker=GroundWorker(context) { error.set(it); done.countDown() }
        try {
            // Warm-up offers may be dropped while the model initializes. Every bitmap is recycled
            // immediately, reproducing MediaPipe's ownership behavior on the producer thread.
            val deadline=SystemClock.elapsedRealtime()+15_000
            while (done.count > 0 && SystemClock.elapsedRealtime()<deadline) {
                val bitmap=Bitmap.createBitmap(640,480,Bitmap.Config.ARGB_8888)
                worker.offer(bitmap,SystemClock.elapsedRealtime()) { _, stats -> metrics.set(stats); done.countDown() }
                bitmap.recycle()
                if (done.await(50,TimeUnit.MILLISECONDS)) break
            }
            assertEquals("No inference result",0L,done.count)
            assertNull(error.get())
            assertNotNull(metrics.get())
            val stats=requireNotNull(metrics.get())
            assertTrue(stats.processed <= stats.offered)
        } finally { worker.close() }
    }
}
