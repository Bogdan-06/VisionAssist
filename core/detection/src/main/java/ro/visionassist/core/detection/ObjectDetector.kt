package ro.visionassist.core.detection

import android.content.Context
import android.graphics.Bitmap
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.core.Delegate
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector as MediaPipeDetector

/** Create, detect and close on the same background worker. No network or runtime download. */
class ObjectDetector(context: Context, modelPath: String = MODEL_ASSET) : AutoCloseable {
    private val ownerThread = Thread.currentThread()
    private var closed = false
    private val detector = MediaPipeDetector.createFromOptions(
        context.applicationContext,
        MediaPipeDetector.ObjectDetectorOptions.builder()
            .setBaseOptions(BaseOptions.builder().setModelAssetPath(modelPath).setDelegate(Delegate.CPU).build())
            // Synchronous IMAGE mode is intentional: the CameraX worker owns backpressure and
            // image lifetime; there is never a second MediaPipe async queue of retained frames.
            .setRunningMode(RunningMode.IMAGE)
            .setScoreThreshold(SCORE_THRESHOLD)
            .setMaxResults(MAX_RESULTS)
            .build()
    )

    /** Takes ownership of the bitmap: MediaPipe recycles it when MPImage is closed. */
    fun detect(uprightBitmap: Bitmap): List<ImageDetection> {
        check(Thread.currentThread() == ownerThread) { "Detector called from a different worker" }
        check(!closed) { "Detector is closed" }
        val image = BitmapImageBuilder(uprightBitmap).build()
        try {
            return detector.detect(image).detections().mapNotNull { detection ->
                val category = detection.categories().maxByOrNull { it.score() } ?: return@mapNotNull null
                val label = category.categoryName()
                val score = category.score()
                if (label.isBlank() || label == "???" || !score.isFinite() || score < SCORE_THRESHOLD) return@mapNotNull null
                val box = detection.boundingBox()
                ImageDetection(label, score.coerceIn(0f, 1f), PixelBox(box.left, box.top, box.right, box.bottom))
            }
        } finally {
            image.close()
        }
    }

    override fun close() {
        check(Thread.currentThread() == ownerThread) { "Detector closed from a different worker" }
        if (!closed) {
            closed = true
            detector.close()
        }
    }

    companion object {
        const val MODEL_ASSET = "efficientdet_lite0.tflite"
        const val MODEL_SHA256 = "40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58"
        const val SCORE_THRESHOLD = 0.5f
        const val MAX_RESULTS = 10
    }
}
