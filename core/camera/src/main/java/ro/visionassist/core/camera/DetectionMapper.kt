package ro.visionassist.core.camera

import android.graphics.RectF
import androidx.camera.view.TransformExperimental
import androidx.camera.view.transform.CoordinateTransform
import androidx.camera.view.transform.OutputTransform
import ro.visionassist.core.detection.DetectedObject
import ro.visionassist.core.detection.ImageDetection
import ro.visionassist.core.detection.PixelBox
import ro.visionassist.core.detection.visibleBox

/** Both transforms must belong to the same CameraX UseCaseGroup/ViewPort. */
@androidx.annotation.OptIn(TransformExperimental::class)
fun mapDetections(
    detections: List<ImageDetection>, source: OutputTransform, target: OutputTransform,
    viewWidth: Int, viewHeight: Int
): List<DetectedObject> {
    val transform = CoordinateTransform(source, target)
    return detections.mapNotNull { detection ->
        val box = detection.bounds
        val mapped = RectF(box.left, box.top, box.right, box.bottom)
        transform.mapRect(mapped)
        val visible = visibleBox(PixelBox(mapped.left, mapped.top, mapped.right, mapped.bottom), viewWidth, viewHeight)
            ?: return@mapNotNull null
        DetectedObject(detection.label, detection.confidence, visible)
    }
}
