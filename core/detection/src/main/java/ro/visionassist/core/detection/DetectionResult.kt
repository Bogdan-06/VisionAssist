package ro.visionassist.core.detection

/** Immutable coordinates. PixelBox belongs to the upright model input, not the sensor buffer. */
data class PixelBox(val left: Float, val top: Float, val right: Float, val bottom: Float)
data class ImageDetection(val label: String, val confidence: Float, val bounds: PixelBox)

/** Bounds normalized to the visible PreviewView, after rotation, crop and clipping. */
data class ViewBox(val left: Float, val top: Float, val right: Float, val bottom: Float) {
    val direction: Direction get() = directionFor((left + right) / 2f)
}
enum class Direction { Left, Center, Right }
fun directionFor(centerX: Float): Direction = when {
    centerX < 1f / 3f -> Direction.Left
    centerX > 2f / 3f -> Direction.Right
    else -> Direction.Center
}

fun visibleBox(box: PixelBox, width: Int, height: Int): ViewBox? {
    if (width <= 0 || height <= 0 ||
        !listOf(box.left, box.top, box.right, box.bottom).all(Float::isFinite)) return null
    val left = (box.left / width).coerceIn(0f, 1f)
    val top = (box.top / height).coerceIn(0f, 1f)
    val right = (box.right / width).coerceIn(0f, 1f)
    val bottom = (box.bottom / height).coerceIn(0f, 1f)
    return if (right > left && bottom > top) ViewBox(left, top, right, bottom) else null
}

data class DetectedObject(val label: String, val confidence: Float, val bounds: ViewBox)
data class DetectionResult(
    val objects: List<DetectedObject>,
    // Monotonic time at analyzer receipt, not an inferred physical capture time.
    val receivedAtMs: Long,
    val inferenceMs: Long
)
enum class DetectionFailure { Model, Inference, Mapping }

/** Timestamp policy shared by the worker, UI and tests. Never keep an old box indefinitely. */
object DetectionPolicy {
    const val MIN_FRAME_INTERVAL_MS = 125L
    const val MAX_RESULT_AGE_MS = 1_000L
    fun isFresh(receivedAtMs: Long, nowMs: Long): Boolean =
        nowMs >= receivedAtMs && nowMs - receivedAtMs < MAX_RESULT_AGE_MS
}

class FrameThrottle(private val intervalMs: Long = DetectionPolicy.MIN_FRAME_INTERVAL_MS) {
    private var lastAccepted: Long? = null
    fun accept(nowMs: Long): Boolean {
        val last = lastAccepted
        if (last != null && nowMs >= last && nowMs - last < intervalMs) return false
        lastAccepted = nowMs
        return true
    }
}
