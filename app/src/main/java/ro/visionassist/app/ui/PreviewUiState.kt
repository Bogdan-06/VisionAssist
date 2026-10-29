package ro.visionassist.app.ui

import ro.visionassist.core.camera.PreviewStatus

enum class CameraPermission { Required, Denied, Granted }
enum class ScreenStatus { PermissionRequired, PermissionDenied, Stopped, Starting, Streaming, Unavailable, Error }

/** Pure presentation state: camera success cannot override missing permission or a user stop. */
fun screenStatus(
    permission: CameraPermission,
    enabled: Boolean,
    foreground: Boolean,
    previewStatus: PreviewStatus
): ScreenStatus = when {
    permission == CameraPermission.Required -> ScreenStatus.PermissionRequired
    permission == CameraPermission.Denied -> ScreenStatus.PermissionDenied
    !enabled || !foreground -> ScreenStatus.Stopped
    else -> when (previewStatus) {
        PreviewStatus.Starting -> ScreenStatus.Starting
        PreviewStatus.Streaming -> ScreenStatus.Streaming
        PreviewStatus.Unavailable -> ScreenStatus.Unavailable
        PreviewStatus.Error -> ScreenStatus.Error
    }
}
