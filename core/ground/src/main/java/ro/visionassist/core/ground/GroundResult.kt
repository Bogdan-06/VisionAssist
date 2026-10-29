package ro.visionassist.core.ground

import kotlin.math.max
import kotlin.math.min

/** Normalized upright input image coordinates. No distance is inferred from these boxes. */
data class GroundBox(val left: Float, val top: Float, val right: Float, val bottom: Float) {
    fun iou(other: GroundBox): Float {
        val intersection = max(0f, min(right, other.right) - max(left, other.left)) *
            max(0f, min(bottom, other.bottom) - max(top, other.top))
        val union = (right-left)*(bottom-top) + (other.right-other.left)*(other.bottom-other.top) - intersection
        return if (union > 0) intersection / union else 0f
    }
}

enum class GroundClass { Pothole }
data class GroundCandidate(val confidence: Float, val bounds: GroundBox, val category: GroundClass = GroundClass.Pothole)
data class GroundFrame(val candidates: List<GroundCandidate>, val receivedAtMs: Long,
    val width: Int, val height: Int, val inferenceMs: Long, val processingMs: Long)
data class GroundMetrics(val offered: Long, val processed: Long, val skippedBusy: Long,
    val skippedThrottle: Long, val inferenceMs: Long, val processingMs: Long)
enum class GroundFailure { Model, Inference }

/** Scores are model outputs, not calibrated probabilities of danger. */
object GroundDecoder {
    const val SIZE = 320
    const val GRID = 20
    const val DISPLAY_THRESHOLD = .3f

    fun decode(output: FloatArray, width: Int, height: Int, resizedWidth: Int, resizedHeight: Int,
               threshold: Float = DISPLAY_THRESHOLD): List<GroundCandidate> {
        require(output.size == GRID*GRID*5 && width > 0 && height > 0)
        require(resizedWidth in 1..SIZE && resizedHeight in 1..SIZE)
        val left = (SIZE-resizedWidth)/2; val top = (SIZE-resizedHeight)/2
        val candidates = mutableListOf<GroundCandidate>()
        for (y in 0 until GRID) for (x in 0 until GRID) {
            val offset = (y*GRID+x)*5
            val score = output[offset]
            if (!score.isFinite() || score < threshold || score > 1f) continue
            if ((max(0,y-1)..min(GRID-1,y+1)).any { yy ->
                (max(0,x-1)..min(GRID-1,x+1)).any { xx -> output[(yy*GRID+xx)*5] > score }
            }) continue
            val dx = output[offset+1]; val dy = output[offset+2]
            val bw = output[offset+3]; val bh = output[offset+4]
            if (listOf(dx,dy,bw,bh).any { !it.isFinite() || it !in 0f..1f }) continue
            val cx = (x+dx)/GRID*SIZE; val cy = (y+dy)/GRID*SIZE
            val box = GroundBox(((cx-bw*SIZE/2-left)/resizedWidth).coerceIn(0f,1f),
                ((cy-bh*SIZE/2-top)/resizedHeight).coerceIn(0f,1f),
                ((cx+bw*SIZE/2-left)/resizedWidth).coerceIn(0f,1f),
                ((cy+bh*SIZE/2-top)/resizedHeight).coerceIn(0f,1f))
            if (box.right > box.left && box.bottom > box.top) candidates += GroundCandidate(score,box)
        }
        val kept = mutableListOf<GroundCandidate>()
        for (candidate in candidates.sortedByDescending { it.confidence }) {
            if (kept.none { it.bounds.iou(candidate.bounds) > .4f }) kept += candidate
            if (kept.size == 20) break
        }
        return kept
    }
}
