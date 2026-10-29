package ro.visionassist.app.ui

import org.junit.Assert.assertEquals
import org.junit.Test
import ro.visionassist.core.camera.PreviewStatus

class PreviewUiStateTest {
    @Test fun `missing permission always wins over stale streaming events`() {
        for (preview in PreviewStatus.entries) {
            assertEquals(ScreenStatus.PermissionRequired, screenStatus(CameraPermission.Required, true, true, preview))
            assertEquals(ScreenStatus.PermissionDenied, screenStatus(CameraPermission.Denied, true, true, preview))
        }
    }
    @Test fun `stopped or backgrounded preview never claims camera is active`() {
        for (preview in PreviewStatus.entries) {
            assertEquals(ScreenStatus.Stopped, screenStatus(CameraPermission.Granted, false, true, preview))
            assertEquals(ScreenStatus.Stopped, screenStatus(CameraPermission.Granted, true, false, preview))
        }
    }
    @Test fun `only a streaming event can present an active camera`() {
        assertEquals(ScreenStatus.Starting, screenStatus(CameraPermission.Granted, true, true, PreviewStatus.Starting))
        assertEquals(ScreenStatus.Streaming, screenStatus(CameraPermission.Granted, true, true, PreviewStatus.Streaming))
        assertEquals(ScreenStatus.Unavailable, screenStatus(CameraPermission.Granted, true, true, PreviewStatus.Unavailable))
        assertEquals(ScreenStatus.Error, screenStatus(CameraPermission.Granted, true, true, PreviewStatus.Error))
    }
}
