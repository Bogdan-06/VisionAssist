package ro.visionassist.core.detection

import org.junit.Assert.*
import org.junit.Test

class DetectionGeometryTest {
    @Test fun `positions use visible view thirds and include boundaries in center`() {
        assertEquals(Direction.Left, directionFor(0.1f))
        assertEquals(Direction.Center, directionFor(1f / 3f))
        assertEquals(Direction.Center, directionFor(2f / 3f))
        assertEquals(Direction.Right, directionFor(0.9f))
    }
    @Test fun `clip to view and discard offscreen degenerate and nonfinite boxes`() {
        assertEquals(ViewBox(0f, 0.2f, 0.5f, 1f), visibleBox(PixelBox(-20f, 20f, 50f, 150f), 100, 100))
        assertNull(visibleBox(PixelBox(110f, 0f, 150f, 10f), 100, 100))
        assertNull(visibleBox(PixelBox(20f, 20f, 10f, 30f), 100, 100))
        assertNull(visibleBox(PixelBox(Float.NaN, 0f, 50f, 50f), 100, 100))
        assertNull(visibleBox(PixelBox(0f, 0f, 50f, 50f), 0, 100))
    }
    @Test fun `throttle samples at most eight frames per second and tolerates clock reset`() {
        val throttle = FrameThrottle()
        assertTrue(throttle.accept(0))
        assertFalse(throttle.accept(124))
        assertTrue(throttle.accept(125))
        assertFalse(throttle.accept(126))
        assertTrue(throttle.accept(250))
        assertTrue(throttle.accept(0))
    }
    @Test fun `old and future timestamps never remain current`() {
        assertTrue(DetectionPolicy.isFresh(100, 1099))
        assertFalse(DetectionPolicy.isFresh(100, 1100))
        assertFalse(DetectionPolicy.isFresh(100, 99))
    }
}
