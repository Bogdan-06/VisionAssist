package ro.visionassist.core.detection

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import java.security.MessageDigest

class ModelInstrumentedTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()


    @Test fun bundledModelMatchesPinnedChecksumAndDetectsRealFixture() {
        val context = instrumentation.targetContext
        val bytes = context.assets.open(ObjectDetector.MODEL_ASSET).use { it.readBytes() }
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        assertEquals(ObjectDetector.MODEL_SHA256, digest)
        val bitmap = instrumentation.context.assets.open("cats_and_dogs.jpg").use { BitmapFactory.decodeStream(it) }
        ObjectDetector(context).use { detector ->
            // Keep the fixture for the rotation check; detect() takes ownership of its input.
            val detections = detector.detect(bitmap.copy(Bitmap.Config.ARGB_8888, false))
            assertTrue("Real image must produce both cat and dog detections: $detections",
                detections.any { it.label == "cat" } && detections.any { it.label == "dog" })
            assertTrue(detections.all { it.confidence >= ObjectDetector.SCORE_THRESHOLD && it.confidence <= 1f })
            assertTrue(detections.all { it.bounds.right > it.bounds.left && it.bounds.bottom > it.bounds.top })
            // Simulate a landscape sensor buffer and restore upright pixels before inference.
            val sensor = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, Matrix().apply { postRotate(-90f) }, false)
            val restored = Bitmap.createBitmap(sensor, 0, 0, sensor.width, sensor.height, Matrix().apply { postRotate(90f) }, false)
            val rotatedResult = detector.detect(restored)
            assertTrue(rotatedResult.any { it.label == "cat" } && rotatedResult.any { it.label == "dog" })
            restored.recycle()
            sensor.recycle()
        }
        bitmap.recycle()
    }

    @Test fun missingModelFailsInsteadOfReturningSimulatedDetections() {
        assertThrows(RuntimeException::class.java) { ObjectDetector(instrumentation.targetContext, "missing.tflite") }
    }

    @Test fun streetImagesRecognizePeopleBicycleAndVehicles() {
        ObjectDetector(instrumentation.targetContext).use { detector ->
            fun detectAsset(name: String): List<ImageDetection> {
                val bitmap = instrumentation.context.assets.open(name).use { BitmapFactory.decodeStream(it) }
                return detector.detect(bitmap).also { println("$name: $it") }
            }
            val street = detectAsset("people_bus.jpg")
            assertTrue("Must recognize an actual person: $street", street.any { it.label == "person" })
            assertTrue("Must recognize the bus: $street", street.any { it.label == "bus" })
            val bicycle = detectAsset("dog_bicycle_vehicle.jpg")
            assertTrue("Must recognize the bicycle: $bicycle", bicycle.any { it.label == "bicycle" })
            assertTrue("Must recognize a vehicle: $bicycle", bicycle.any { it.label == "car" || it.label == "truck" })
        }
    }


    @Test fun closeIsIdempotentAndPreventsFurtherInference() {
        val detector = ObjectDetector(instrumentation.targetContext)
        detector.close()
        detector.close()
        val bitmap = Bitmap.createBitmap(32, 32, Bitmap.Config.ARGB_8888)
        try { assertThrows(IllegalStateException::class.java) { detector.detect(bitmap) } }
        finally { bitmap.recycle() }
    }
}
