package ro.visionassist.app.ui

import android.os.SystemClock
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import ro.visionassist.core.detection.DetectionFailure
import ro.visionassist.core.detection.DetectionPolicy
import ro.visionassist.core.detection.DetectionResult

enum class DetectionPhase { Idle, Loading, Active, Stale, Error }
data class DetectionUiState(
    val phase: DetectionPhase = DetectionPhase.Idle,
    val result: DetectionResult? = null,
    val failure: DetectionFailure? = null,
    val analysisFps: Double? = null
)

/** Owns UI state only; camera sessions own native inference resources. Main-thread callbacks. */
class DetectionViewModel : ViewModel() {
    private val mutableState = MutableStateFlow(DetectionUiState())
    val state = mutableState.asStateFlow()
    private var expiry: Job? = null
    private val frameTimes = ArrayDeque<Long>()

    fun start() {
        frameTimes.clear()
        expiry?.cancel()
        mutableState.value = DetectionUiState(DetectionPhase.Loading)
    }
    fun stop() {
        frameTimes.clear()
        expiry?.cancel()
        mutableState.value = DetectionUiState()
    }
    fun clearResults() {
        expiry?.cancel()
        if (mutableState.value.phase != DetectionPhase.Error) start()
    }
    fun onError(failure: DetectionFailure) {
        expiry?.cancel()
        mutableState.value = DetectionUiState(DetectionPhase.Error, failure = failure)
    }
    fun onResult(result: DetectionResult) {
        if (mutableState.value.phase == DetectionPhase.Idle || mutableState.value.phase == DetectionPhase.Error) return
        expiry?.cancel()
        val age = SystemClock.elapsedRealtime() - result.receivedAtMs
        if (!DetectionPolicy.isFresh(result.receivedAtMs, SystemClock.elapsedRealtime())) {
            mutableState.value = DetectionUiState(DetectionPhase.Stale)
            return
        }
        frameTimes.addLast(result.receivedAtMs)
        while (frameTimes.size > 20 || (frameTimes.size > 1 && result.receivedAtMs - frameTimes.first() > 2000)) frameTimes.removeFirst()
        val span = frameTimes.last() - frameTimes.first()
        val fps = if (frameTimes.size >= 2 && span > 0) (frameTimes.size - 1) * 1000.0 / span else null
        mutableState.value = DetectionUiState(DetectionPhase.Active, result, analysisFps = fps)
        expiry = viewModelScope.launch {
            delay((DetectionPolicy.MAX_RESULT_AGE_MS - age).coerceAtLeast(1))
            mutableState.value = DetectionUiState(DetectionPhase.Stale)
        }
    }
}
