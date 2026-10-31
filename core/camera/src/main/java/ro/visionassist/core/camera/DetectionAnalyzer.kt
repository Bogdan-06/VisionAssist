package ro.visionassist.core.camera

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.os.SystemClock
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.view.TransformExperimental
import androidx.camera.view.transform.ImageProxyTransformFactory
import androidx.camera.view.transform.OutputTransform
import ro.visionassist.core.detection.DetectionFailure
import ro.visionassist.core.detection.FrameThrottle
import ro.visionassist.core.detection.ImageDetection
import ro.visionassist.core.detection.ObjectDetector
import ro.visionassist.core.ground.GroundWorker
import ro.visionassist.core.ground.GroundFrame
import ro.visionassist.core.ground.GroundMetrics
import ro.visionassist.core.ground.GroundFailure
import java.util.concurrent.atomic.AtomicBoolean

/** All methods except cancel() run on the camera session's single executor. */
@androidx.annotation.OptIn(TransformExperimental::class)
class DetectionAnalyzer(
    private val context: Context,
    private val onResult: (List<ImageDetection>, OutputTransform, Long, Long) -> Unit,
    private val onError: (DetectionFailure) -> Unit,
    private val snapshotRequest: CameraSnapshotRequest? = null,
    private val groundEnabled: Boolean = false,
    private val onGroundResult: (GroundFrame, GroundMetrics, OutputTransform) -> Unit = { _, _, _ -> },
    private val onGroundError: (GroundFailure) -> Unit = {}
) : ImageAnalysis.Analyzer, AutoCloseable {
    private val cancelled = AtomicBoolean(false)
    private val snapshotSource = snapshotRequest?.beginSource()
    private var failed = false
    private var detector: ObjectDetector? = null
    private var ground: GroundWorker? = null
    private val throttle = FrameThrottle()
    private val transformFactory = ImageProxyTransformFactory().apply {
        isUsingCropRect = false // toBitmap() uses the entire image buffer, including outside ViewPort.
        isUsingRotationDegrees = true // detect() receives physically rotated upright pixels.
    }

    fun initialize() {
        if (cancelled.get()) return
        if (groundEnabled) ground = GroundWorker(context, onGroundError)
        try {
            detector = ObjectDetector(context)
        } catch (_: Exception) {
            fail(DetectionFailure.Model)
        } catch (_: LinkageError) {
            fail(DetectionFailure.Model)
        }
    }

    override fun analyze(image: ImageProxy) {
        var bitmap: Bitmap? = null
        var upright: Bitmap? = null
        try {
            val receivedAt = SystemClock.elapsedRealtime()
            if (cancelled.get() || !throttle.accept(receivedAt)) return
            val source = transformFactory.getOutputTransform(image)
            bitmap = image.toBitmap()
            upright = if (image.imageInfo.rotationDegrees == 0) bitmap else Bitmap.createBitmap(
                bitmap, 0, 0, bitmap.width, bitmap.height,
                Matrix().apply { postRotate(image.imageInfo.rotationDegrees.toFloat()) }, true
            )
            if (cancelled.get()) return
            snapshotSource?.let { snapshotRequest?.offer(upright, it) }
            ground?.offer(upright, receivedAt) { result, metrics ->
                if (!cancelled.get()) onGroundResult(result, metrics, source)
            }
            if (!failed) detector?.let { activeDetector ->
                val inferenceStarted = SystemClock.elapsedRealtime()
                val detections = activeDetector.detect(upright)
                if (!cancelled.get()) onResult(detections, source, receivedAt, SystemClock.elapsedRealtime() - inferenceStarted)
            }
        } catch (_: Exception) {
            fail(DetectionFailure.Inference)
        } catch (_: LinkageError) {
            fail(DetectionFailure.Inference)
        } finally {
            if (upright !== bitmap && upright?.isRecycled == false) upright.recycle()
            if (bitmap?.isRecycled == false) bitmap.recycle()
            image.close() // Including throttled, failed, cancelled and successful frames.
        }
    }

    private fun fail(reason: DetectionFailure) {
        if (failed) return
        failed = true
        if (!cancelled.get()) onError(reason)
    }
    fun cancel() {
        cancelled.set(true)
        snapshotSource?.let { snapshotRequest?.endSource(it) }
    }
    override fun close() {
        cancel()
        ground?.close()
        ground = null
        detector?.close()
        detector = null
    }
}
