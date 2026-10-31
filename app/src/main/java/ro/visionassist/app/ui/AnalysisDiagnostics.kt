package ro.visionassist.app.ui

import kotlin.math.ceil

data class AnalysisDiagnostics(val samples: Int = 0, val fps: Double? = null,
    val medianMs: Long? = null, val p95Ms: Long? = null)

/** Bounded session window. Durations are MediaPipe detect calls, not sensor-to-warning latency. */
internal class AnalysisWindow(private val capacity: Int = 60) {
    init { require(capacity >= 2) }
    private val samples = ArrayDeque<Pair<Long, Long>>()
    fun clear() = samples.clear()
    fun add(receivedAtMs: Long, durationMs: Long): AnalysisDiagnostics {
        if (durationMs < 0 || (samples.isNotEmpty() && receivedAtMs <= samples.last().first)) return snapshot()
        if (samples.isNotEmpty() && receivedAtMs - samples.last().first >= 1_000) clear()
        samples.addLast(receivedAtMs to durationMs)
        while (samples.size > capacity) samples.removeFirst()
        return snapshot()
    }
    fun snapshot(): AnalysisDiagnostics {
        if (samples.isEmpty()) return AnalysisDiagnostics()
        val times = samples.map { it.second }.sorted()
        val middle = times.size / 2
        // Integer midpoint without overflowing a sum of two durations.
        val median = if (times.size % 2 == 1) times[middle]
            else times[middle - 1] + (times[middle] - times[middle - 1]) / 2
        val recent = samples.takeLast(20).filter { it.first >= samples.last().first - 2_000 }
        val span = recent.last().first - recent.first().first
        return AnalysisDiagnostics(times.size,
            if (recent.size >= 2 && span > 0) (recent.size - 1) * 1000.0 / span else null,
            median, times[ceil(times.size * .95).toInt() - 1])
    }
}
