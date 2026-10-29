package ro.visionassist.core.camera

import android.hardware.display.DisplayManager
import android.os.Handler
import android.os.Looper
import android.util.Rational
import android.util.Size
import android.view.Surface
import android.view.View
import androidx.camera.core.CameraSelector
import androidx.camera.core.CameraState
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.UseCaseGroup
import androidx.camera.core.ViewPort
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.camera.view.TransformExperimental
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Observer
import androidx.lifecycle.compose.LocalLifecycleOwner
import ro.visionassist.core.detection.DetectionFailure
import ro.visionassist.core.detection.DetectionResult
import ro.visionassist.core.detection.DetectionPolicy
import ro.visionassist.core.detection.ImageDetection
import ro.visionassist.core.detection.PixelBox
import ro.visionassist.core.ground.GroundFailure
import ro.visionassist.core.ground.GroundMetrics
import android.os.SystemClock
import java.util.concurrent.Executors

enum class PreviewStatus { Starting, Streaming, Unavailable, Error }

/** Local preview + inference; only an explicit snapshot request exports one JPEG in memory. */
@androidx.annotation.OptIn(TransformExperimental::class)
@Composable
fun CameraPreview(
    modifier: Modifier = Modifier,
    onStatus: (PreviewStatus) -> Unit,
    onDetections: (DetectionResult) -> Unit = {},
    onDetectionError: (DetectionFailure) -> Unit = {},
    onAnalysisReset: () -> Unit = {},
    snapshotRequest: CameraSnapshotRequest? = null,
    groundEnabled: Boolean = false,
    onGroundDetections: (DetectionResult, GroundMetrics) -> Unit = { _, _ -> },
    onGroundError: (GroundFailure) -> Unit = {},
    onGroundReset: () -> Unit = {}
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val currentOnStatus = rememberUpdatedState(onStatus)
    val currentOnDetections = rememberUpdatedState(onDetections)
    val currentOnError = rememberUpdatedState(onDetectionError)
    val currentOnReset = rememberUpdatedState(onAnalysisReset)
    val currentGroundResult = rememberUpdatedState(onGroundDetections)
    val currentGroundError = rememberUpdatedState(onGroundError)
    val currentGroundReset = rememberUpdatedState(onGroundReset)
    var viewSize by remember { mutableStateOf(IntSize.Zero) }
    var rotation by remember { mutableIntStateOf(Surface.ROTATION_0) }
    val view = remember(context) {
        PreviewView(context).apply {
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            scaleType = PreviewView.ScaleType.FILL_CENTER
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }
    }
    // Also handle 180-degree display changes, which may not recreate the Activity.
    DisposableEffect(view) {
        val manager = context.getSystemService(DisplayManager::class.java)
        fun updateRotation() { view.display?.let { rotation = it.rotation } }
        val listener = object : DisplayManager.DisplayListener {
            override fun onDisplayAdded(displayId: Int) = updateRotation()
            override fun onDisplayRemoved(displayId: Int) = Unit
            override fun onDisplayChanged(displayId: Int) = updateRotation()
        }
        val attachListener = object : View.OnAttachStateChangeListener {
            override fun onViewAttachedToWindow(v: View) = updateRotation()
            override fun onViewDetachedFromWindow(v: View) = Unit
        }
        view.addOnAttachStateChangeListener(attachListener)
        manager.registerDisplayListener(listener, Handler(Looper.getMainLooper()))
        updateRotation()
        onDispose {
            manager.unregisterDisplayListener(listener)
            view.removeOnAttachStateChangeListener(attachListener)
        }
    }
    AndroidView(factory = { view }, modifier = modifier.onSizeChanged { viewSize = it })
    DisposableEffect(view, lifecycleOwner, viewSize, rotation, groundEnabled) {
        if (viewSize.width == 0 || viewSize.height == 0) return@DisposableEffect onDispose {}
        // These flags are confined to the main thread. Worker callbacks are always posted to it.
        var disposed = false
        var failed = false
        var streaming = false
        var detectionFailed = false
        var provider: ProcessCameraProvider? = null
        var boundCamera: androidx.camera.core.Camera? = null
        val main = ContextCompat.getMainExecutor(context)
        val worker = Executors.newSingleThreadExecutor { task -> Thread(task, "VisionAssist-inference") }
        val preview = Preview.Builder().setTargetRotation(rotation).build().also {
            it.surfaceProvider = view.surfaceProvider
        }
        val analysis = ImageAnalysis.Builder()
            .setTargetRotation(rotation)
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
            .setResolutionSelector(ResolutionSelector.Builder()
                .setAspectRatioStrategy(AspectRatioStrategy.RATIO_4_3_FALLBACK_AUTO_STRATEGY)
                .setResolutionStrategy(ResolutionStrategy(Size(640, 480), ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER))
                .build())
            .build()
        lateinit var analyzer: DetectionAnalyzer
        analyzer = DetectionAnalyzer(context.applicationContext,
            onResult = { objects, source, receivedAt, duration ->
                main.execute {
                    if (!disposed && !failed && !detectionFailed && streaming) {
                        val target = view.outputTransform
                        if (target != null) {
                            try {
                                currentOnDetections.value(DetectionResult(
                                    mapDetections(objects, source, target, view.width, view.height), receivedAt, duration
                                ))
                            } catch (_: Exception) {
                                detectionFailed = true
                                currentOnError.value(DetectionFailure.Mapping)
                            }
                        }
                    }
                }
            },
            onError = { error -> main.execute {
                if (!disposed) {
                    detectionFailed = true
                    currentOnError.value(error)
                }
            } },
            snapshotRequest = snapshotRequest,
            groundEnabled = groundEnabled,
            onGroundResult = { frame, metrics, source -> main.execute {
                if (!disposed && !failed && streaming && DetectionPolicy.isFresh(frame.receivedAtMs, SystemClock.elapsedRealtime())) {
                    val target = view.outputTransform
                    if (target != null) try {
                        val objects = frame.candidates.map { candidate ->
                            val b = candidate.bounds
                            ImageDetection("pothole", candidate.confidence, PixelBox(b.left*frame.width,
                                b.top*frame.height,b.right*frame.width,b.bottom*frame.height))
                        }
                        currentGroundResult.value(DetectionResult(mapDetections(objects,source,target,view.width,view.height),
                            frame.receivedAtMs,frame.inferenceMs),metrics)
                    } catch (_: Exception) { currentGroundError.value(GroundFailure.Inference) }
                }
            } },
            onGroundError = { error -> main.execute { if (!disposed) currentGroundError.value(error) } }
        )
        currentOnStatus.value(PreviewStatus.Starting)
        currentOnReset.value()
        currentGroundReset.value()
        worker.execute {
            analyzer.initialize()
            main.execute {
                // Avoid holding an old first frame while the native model initializes.
                if (!disposed) analysis.setAnalyzer(worker, analyzer)
            }
        }
        val streamObserver = Observer<PreviewView.StreamState> { state ->
            streaming = state == PreviewView.StreamState.STREAMING
            if (!disposed && !failed) {
                currentOnStatus.value(if (streaming) PreviewStatus.Streaming else PreviewStatus.Starting)
                if (!streaming) { currentOnReset.value(); currentGroundReset.value() }
            }
        }
        val cameraObserver = Observer<CameraState> { state ->
            if (!disposed && state.error != null) {
                failed = true
                currentOnReset.value()
                currentGroundReset.value()
                currentOnStatus.value(PreviewStatus.Error)
            }
        }
        view.previewStreamState.observe(lifecycleOwner, streamObserver)
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            if (!disposed) {
                try {
                    val cameraProvider = future.get()
                    provider = cameraProvider
                    if (!cameraProvider.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA)) {
                        failed = true
                        currentOnStatus.value(PreviewStatus.Unavailable)
                    } else {
                        // Shared sensor crop is essential: independent preview/analysis binding can
                        // have different fields of view, so simple width scaling is not sufficient.
                        val viewport = ViewPort.Builder(Rational(viewSize.width, viewSize.height), rotation)
                            .setScaleType(ViewPort.FILL_CENTER).setLayoutDirection(view.layoutDirection).build()
                        val group = UseCaseGroup.Builder().setViewPort(viewport)
                            .addUseCase(preview).addUseCase(analysis).build()
                        boundCamera = cameraProvider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, group)
                            .also { it.cameraInfo.cameraState.observe(lifecycleOwner, cameraObserver) }
                    }
                } catch (_: Exception) {
                    failed = true
                    currentOnStatus.value(PreviewStatus.Error)
                }
            }
        }, main)
        onDispose {
            disposed = true
            snapshotRequest?.cancel()
            analyzer.cancel()
            analysis.clearAnalyzer()
            view.previewStreamState.removeObserver(streamObserver)
            boundCamera?.cameraInfo?.cameraState?.removeObserver(cameraObserver)
            provider?.unbind(preview, analysis)
            preview.setSurfaceProvider(null)
            // Enqueued after in-flight inference: never close native inference resources mid-call.
            worker.execute { analyzer.close() }
            worker.shutdown()
        }
    }
}
