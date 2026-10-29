package ro.visionassist.app.ui

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.core.net.toUri
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ro.visionassist.core.camera.CameraPreview
import ro.visionassist.core.camera.PreviewStatus
import ro.visionassist.core.camera.CameraSnapshotRequest
import ro.visionassist.core.voice.SelectableVoiceClient
import ro.visionassist.app.BuildConfig
import ro.visionassist.app.voice.LocalAnnouncements
import ro.visionassist.app.voice.VoiceControls
import ro.visionassist.core.ground.GroundMetrics
import ro.visionassist.core.ground.GroundFailure
import ro.visionassist.core.detection.DetectionFailure

@Composable
fun VisionAssistRoute(preferences: UiPreferences = UiPreferences(InterfaceLayout.Compact),
                      preferenceError: String? = null,
                      onLayout: (InterfaceLayout) -> Unit = {}, onTheme: (ThemeChoice) -> Unit = {},
                      onDeveloper: (Boolean) -> Unit = {}, onLocalAnnouncements: (Boolean) -> Unit = {}) {
    val detectionViewModel: DetectionViewModel = viewModel()
    val detectionState by detectionViewModel.state.collectAsStateWithLifecycle()
    val groundViewModel: DetectionViewModel = viewModel(key = "ground")
    val groundState by groundViewModel.state.collectAsStateWithLifecycle()
    // Unvalidated ground detectors stay disabled regardless of navigation/developer settings.
    val groundEnabled = false
    var groundMetrics by remember { mutableStateOf<GroundMetrics?>(null) }
    val context = LocalContext.current
    val voice = remember { SelectableVoiceClient(context, BuildConfig.DEBUG) }
    val snapshots = remember { CameraSnapshotRequest() }
    val announcements = remember { LocalAnnouncements(context, voice) }
    val voiceState by voice.state.collectAsStateWithLifecycle()
    val recent by announcements.recent.collectAsStateWithLifecycle()
    val hazards by announcements.recentHazards.collectAsStateWithLifecycle()
    LaunchedEffect(preferences.localAnnouncements) { announcements.enabled = preferences.localAnnouncements }
    DisposableEffect(voice) {
        onDispose { snapshots.cancel(); announcements.close(); voice.close() }
    }
    val lifecycleOwner = LocalLifecycleOwner.current
    val cameraPreferences = remember(context) { context.getSharedPreferences("camera_permission", Activity.MODE_PRIVATE) }
    fun permissionNow(): CameraPermission = when {
        ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED -> CameraPermission.Granted
        cameraPreferences.getBoolean("requested", false) -> CameraPermission.Denied
        else -> CameraPermission.Required
    }
    var permission by remember { mutableStateOf(permissionNow()) }
    var enabled by rememberSaveable { mutableStateOf(false) }
    var foreground by remember { mutableStateOf(lifecycleOwner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) }
    var previewStatus by remember { mutableStateOf(PreviewStatus.Starting) }
    var session by remember { mutableIntStateOf(0) }
    var showHelp by rememberSaveable { mutableStateOf(false) }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        permission = if (granted) CameraPermission.Granted else CameraPermission.Denied
        previewStatus = PreviewStatus.Starting
    }
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> {
                    permission = permissionNow()
                    previewStatus = PreviewStatus.Starting
                    foreground = true
                }
                Lifecycle.Event.ON_PAUSE -> {
                    foreground = false
                    snapshots.cancel(); announcements.stop(); voice.stop()
                }
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    val status = screenStatus(permission, enabled, foreground, previewStatus)
    val shouldAnalyze = permission == CameraPermission.Granted && enabled && foreground &&
        previewStatus != PreviewStatus.Error && previewStatus != PreviewStatus.Unavailable
    DisposableEffect(shouldAnalyze, session) {
        if (shouldAnalyze) detectionViewModel.start() else { detectionViewModel.stop(); snapshots.cancel(); announcements.stop() }
        onDispose { detectionViewModel.stop() }
    }
    DisposableEffect(shouldAnalyze, groundEnabled, session) {
        groundMetrics = null
        announcements.resetGround()
        if (shouldAnalyze && groundEnabled) groundViewModel.start() else groundViewModel.stop()
        onDispose { groundViewModel.stop(); announcements.resetGround() }
    }
    VisionAssistScreen(
        status = status,
        showHelp = showHelp,
        onPrimary = {
            when (status) {
                ScreenStatus.PermissionRequired, ScreenStatus.PermissionDenied -> {
                    enabled = true
                    cameraPreferences.edit { putBoolean("requested", true) }
                    permissionLauncher.launch(Manifest.permission.CAMERA)
                }
                ScreenStatus.Streaming, ScreenStatus.Starting -> enabled = false
                else -> {
                    permission = permissionNow()
                    previewStatus = PreviewStatus.Starting
                    session++
                    enabled = true
                }
            }
        },
        onSettings = {
            context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, "package:${context.packageName}".toUri()))
        },
        onHelp = { showHelp = true },
        onDismissHelp = { showHelp = false },
        preview = { modifier ->
            if (shouldAnalyze) {
                key(session) {
                    CameraPreview(
                        modifier = modifier,
                        onStatus = { previewStatus = it },
                        onDetections = { result -> detectionViewModel.onResult(result); announcements.observe(result) },
                        onDetectionError = detectionViewModel::onError,
                        onAnalysisReset = detectionViewModel::clearResults,
                        snapshotRequest = snapshots,
                        groundEnabled = groundEnabled,
                        onGroundDetections = { result, metrics ->
                            groundViewModel.onResult(result); groundMetrics = metrics; announcements.observeGround(result)
                        },
                        onGroundError = { error ->
                            groundViewModel.onError(if (error == GroundFailure.Model) DetectionFailure.Model else DetectionFailure.Inference)
                            announcements.resetGround()
                        },
                        onGroundReset = { if (groundEnabled) groundViewModel.clearResults() }
                    )
                }
            }
        },
        detectionState = detectionState,
        onRetryDetection = { session++ },
        preferences = preferences,
        onLayout = onLayout, onTheme = onTheme, onDeveloper = onDeveloper,
        preferenceError = preferenceError,
        recentAnnouncements = recent,
        recentHazardWarnings = hazards,
        connectionSummary = "Asistent AI: " + when (voiceState.phase) {
            ro.visionassist.core.voice.VoicePhase.Disconnected -> "deconectat"
            ro.visionassist.core.voice.VoicePhase.Connecting -> "se conectează"
            ro.visionassist.core.voice.VoicePhase.Listening -> "ascultă"
            ro.visionassist.core.voice.VoicePhase.Speaking -> "vorbește"
            ro.visionassist.core.voice.VoicePhase.Error -> "eroare de conexiune"
        } + if (voiceState.warningActive) ". Anunțul local are prioritate." else "",
        voiceControls = {
            VoiceControls(voice, announcements, snapshots, status == ScreenStatus.Streaming, foreground,
                showLocal = false)
        },
        settingsControls = {
            VoiceControls(voice, announcements, snapshots, status == ScreenStatus.Streaming, foreground,
                showConversation = false, localEnabled = preferences.localAnnouncements,
                onLocalEnabledChange = onLocalAnnouncements)
            GroundPanel(groundEnabled,groundState,groundMetrics,
                onToggle = {},
                onDepth = {
                    enabled = false
                    snapshots.cancel(); announcements.stop(); voice.stop()
                    context.startActivity(Intent(context,ro.visionassist.app.depth.DepthActivity::class.java))
                })
        },
        groundResult = groundState.result
    )
}
