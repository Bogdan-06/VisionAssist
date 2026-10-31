package ro.visionassist.app.ui

import org.junit.Assert.*
import org.junit.Test

class AnalysisWindowTest {
    @Test fun boundedWindowUsesNearestRankP95AndMeasuredResultFps() {
        val window = AnalysisWindow()
        repeat(100) { window.add(it * 125L, it + 1L) }
        val stats = window.snapshot()
        assertEquals(60, stats.samples)
        assertEquals(70L, stats.medianMs)
        assertEquals(97L, stats.p95Ms)
        assertEquals(8.0, stats.fps!!, .001)
    }
    @Test fun initialValuesAndSessionResetNeverInventMeasurements() {
        val window = AnalysisWindow()
        assertEquals(AnalysisDiagnostics(), window.snapshot())
        assertNull(window.add(100, 10).fps)
        assertEquals(10L, window.snapshot().medianMs)
        window.clear()
        assertEquals(AnalysisDiagnostics(), window.snapshot())
        window.add(100, 10)
        val afterGap = window.add(1_100, 50)
        assertEquals(1, afterGap.samples)
        assertEquals(50L, afterGap.p95Ms)
        assertNull(afterGap.fps)
    }
    @Test fun duplicateOutOfOrderAndNegativeDurationDoNotPolluteStatistics() {
        val window = AnalysisWindow()
        window.add(200, 4); window.add(400, 8)
        val expected = window.snapshot()
        assertEquals(6L, expected.medianMs)
        assertEquals(expected, window.add(400, 999))
        assertEquals(expected, window.add(300, 999))
        assertEquals(expected, window.add(500, -1))
    }
}
