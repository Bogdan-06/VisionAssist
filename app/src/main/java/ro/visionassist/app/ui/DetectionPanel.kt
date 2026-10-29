package ro.visionassist.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.intl.LocaleList
import androidx.compose.ui.unit.dp
import ro.visionassist.app.R

@Composable
fun DetectionPanel(state: DetectionUiState, onRetry: () -> Unit) {
    val status = when (state.phase) {
        DetectionPhase.Idle -> R.string.detection_idle
        DetectionPhase.Loading -> R.string.detection_loading
        DetectionPhase.Active -> R.string.detection_active
        DetectionPhase.Stale -> R.string.detection_stale
        DetectionPhase.Error -> R.string.detection_error
    }
    fun ro(text: String) = AnnotatedString(text, SpanStyle(localeList = LocaleList("ro-RO")))
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(ro(stringResource(R.string.detection_heading)), style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.semantics { heading() })
        Text(ro(stringResource(status)), modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        if (state.phase == DetectionPhase.Error) {
            OutlinedButton(onClick = onRetry, modifier = Modifier.fillMaxWidth().heightIn(min = 64.dp)) {
                Text(ro(stringResource(R.string.retry_detection)))
            }
        }
        state.result?.let { result ->
            Text(ro(stringResource(R.string.detection_timing, result.inferenceMs)), style = MaterialTheme.typography.bodyMedium)
            if (result.objects.isEmpty()) Text(ro(stringResource(R.string.detection_empty)))
            // Deliberately no live region on per-frame results: accessible by exploration,
            // without continuously interrupting TalkBack or implementing spoken warnings.
            result.objects.forEach { obj -> Text(ro(DetectionLabels.description(obj)), style = MaterialTheme.typography.bodyLarge) }
        }
        Text(ro(stringResource(R.string.detection_limits)), style = MaterialTheme.typography.bodyMedium)
    }
}
