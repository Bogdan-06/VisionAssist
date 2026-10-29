package ro.visionassist.core.ground

/** Temporal evidence only; it cannot compensate for an inaccurate visual model. */
class GroundWarningPolicy {
    private var previous: GroundCandidate? = null
    private var hits = 0
    private var firstAt = 0L
    private var lastAt = Long.MIN_VALUE
    private var warnedAt = Long.MIN_VALUE

    fun reset() { previous = null; hits = 0; lastAt = Long.MIN_VALUE }

    fun observe(candidates: List<GroundCandidate>, receivedAtMs: Long, nowMs: Long): GroundCandidate? {
        if (nowMs < receivedAtMs || nowMs-receivedAtMs >= 1_000 || receivedAtMs <= lastAt) {
            reset(); return null
        }
        val candidate = candidates.filter { it.confidence.isFinite() && it.confidence in .65f..1f &&
            it.bounds.bottom > .5f && it.bounds.right > .25f && it.bounds.left < .75f }
            .maxByOrNull { it.confidence }
        if (candidate == null) { reset(); return null }
        val consistent = previous?.let { it.category == candidate.category && it.bounds.iou(candidate.bounds) >= .25f } == true &&
            lastAt != Long.MIN_VALUE && receivedAtMs-lastAt <= 800
        if (consistent) hits++ else { hits = 1; firstAt = receivedAtMs }
        previous = candidate; lastAt = receivedAtMs
        if (hits < 3 || receivedAtMs-firstAt < 800 || (warnedAt != Long.MIN_VALUE && nowMs-warnedAt < 12_000)) return null
        warnedAt = nowMs; reset()
        return candidate
    }
}

object GroundModelReadiness {
    // v1 test @0.65: TP 0, FP 1, FN 550. A score threshold is not validation.
    const val WARNINGS_VALIDATED = false
}
