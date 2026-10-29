package ro.visionassist.app.ui

import androidx.annotation.StringRes
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.intl.LocaleList
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import ro.visionassist.app.R

// Give accessibility services a Romanian language span even on an English-language phone.
@Composable
private fun romanian(@StringRes id: Int): AnnotatedString = AnnotatedString(
    stringResource(id), SpanStyle(localeList = LocaleList("ro-RO"))
)

@Composable
fun VisionAssistScreen(
    status: ScreenStatus,
    showHelp: Boolean,
    onPrimary: () -> Unit,
    onSettings: () -> Unit,
    onHelp: () -> Unit,
    onDismissHelp: () -> Unit,
    preview: @Composable (Modifier) -> Unit,
    detectionState: DetectionUiState = DetectionUiState(),
    onRetryDetection: () -> Unit = {},
    voiceControls: @Composable () -> Unit = {},
    groundResult: ro.visionassist.core.detection.DetectionResult? = null
) {
    val statusText = when (status) {
        ScreenStatus.PermissionRequired -> R.string.status_permission
        ScreenStatus.PermissionDenied -> R.string.status_denied
        ScreenStatus.Stopped -> R.string.status_paused
        ScreenStatus.Starting -> R.string.status_starting
        ScreenStatus.Streaming -> R.string.status_streaming
        ScreenStatus.Unavailable -> R.string.status_unavailable
        ScreenStatus.Error -> R.string.status_error
    }
    val bodyText = when (status) {
        ScreenStatus.PermissionRequired -> R.string.permission_body
        ScreenStatus.PermissionDenied -> R.string.denied_body
        ScreenStatus.Stopped -> R.string.paused_body
        ScreenStatus.Unavailable -> R.string.unavailable_body
        ScreenStatus.Error -> R.string.error_body
        else -> R.string.active_body
    }
    val buttonText = when (status) {
        ScreenStatus.PermissionRequired, ScreenStatus.PermissionDenied -> R.string.allow_camera
        ScreenStatus.Starting, ScreenStatus.Streaming -> R.string.stop_camera
        ScreenStatus.Unavailable, ScreenStatus.Error -> R.string.retry_camera
        ScreenStatus.Stopped -> R.string.start_camera
    }
    Scaffold { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.TopCenter) {
            Column(
                Modifier.widthIn(max = 600.dp).fillMaxWidth()
                    .verticalScroll(rememberScrollState()).padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(20.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(romanian(R.string.prototype_label), color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.labelLarge)
                    Text(stringResource(R.string.app_name), style = MaterialTheme.typography.headlineLarge,
                        modifier = Modifier.semantics { heading() })
                    Text(romanian(R.string.subtitle), style = MaterialTheme.typography.titleLarge)
                }
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(romanian(R.string.safety_title), style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.semantics { heading() })
                        Text(romanian(R.string.safety_body), style = MaterialTheme.typography.bodyLarge)
                    }
                }
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(romanian(R.string.status_heading), style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.semantics { heading() })
                    Text(romanian(statusText), style = MaterialTheme.typography.headlineSmall,
                        modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                    Text(romanian(bodyText), style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                // Controls precede the visual preview in both reading and focus order.
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = onPrimary, modifier = Modifier.fillMaxWidth().heightIn(min = 64.dp)) {
                        Text(romanian(buttonText), style = MaterialTheme.typography.titleMedium,
                            textAlign = TextAlign.Center, modifier = Modifier.padding(vertical = 8.dp))
                    }
                    if (status == ScreenStatus.PermissionDenied || status == ScreenStatus.Error) {
                        OutlinedButton(onClick = onSettings, modifier = Modifier.fillMaxWidth().heightIn(min = 64.dp)) {
                            Text(romanian(R.string.open_settings), textAlign = TextAlign.Center,
                                modifier = Modifier.padding(vertical = 8.dp))
                        }
                    }
                    TextButton(onClick = onHelp, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
                        Text(romanian(R.string.help_button), style = MaterialTheme.typography.titleMedium)
                    }
                }
                voiceControls()
                val previewDescription = stringResource(R.string.preview_description)
                Box(
                    Modifier.fillMaxWidth().height(240.dp).clip(RoundedCornerShape(24.dp))
                        .background(Color.Black)
                        .clearAndSetSemantics { contentDescription = previewDescription },
                    contentAlignment = Alignment.Center
                ) {
                    Text(romanian(R.string.preview_placeholder), color = Color.White,
                        textAlign = TextAlign.Center, modifier = Modifier.padding(24.dp))
                    preview(Modifier.fillMaxSize())
                    if (status == ScreenStatus.Streaming) {
                        DetectionOverlay(detectionState.result, Modifier.fillMaxSize())
                        GroundOverlay(groundResult, Modifier.fillMaxSize())
                    }
                }
                if (status == ScreenStatus.Streaming || status == ScreenStatus.Starting) {
                    DetectionPanel(detectionState, onRetryDetection)
                }
                Text(romanian(R.string.privacy_label), style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
    if (showHelp) {
        AlertDialog(
            onDismissRequest = onDismissHelp,
            title = { Text(romanian(R.string.help_title)) },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    Text(romanian(R.string.help_body))
                    Text(romanian(R.string.safety_body))
                }
            },
            confirmButton = {
                TextButton(onClick = onDismissHelp, modifier = Modifier.heightIn(min = 56.dp)) {
                    Text(romanian(R.string.close_help))
                }
            }
        )
    }
}

@Preview(name = "Romanian · initial", showBackground = true)
@Preview(name = "Large text", fontScale = 2f, showBackground = true)
@Composable
private fun InitialPreview() {
    VisionAssistTheme {
        VisionAssistScreen(ScreenStatus.PermissionRequired, false, {}, {}, {}, {}, {})
    }
}
