package ro.visionassist.app.ui

import android.os.SystemClock
import androidx.lifecycle.ViewModelStore
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Test
import ro.visionassist.core.detection.DetectedObject
import ro.visionassist.core.detection.DetectionFailure
import ro.visionassist.core.detection.DetectionResult
import ro.visionassist.core.detection.ViewBox

class DetectionViewModelTest {
    @Test fun diagnosticsRequireOptInAndResetOnDisableFailureAndStop() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val store = ViewModelStore()
        instrumentation.runOnMainSync {
            val vm = DetectionViewModel()
            store.put("diagnostics", vm)
            try {
                fun result() = DetectionResult(emptyList(), SystemClock.elapsedRealtime(), 12)
                vm.start(); vm.onResult(result())
                assertEquals(0, vm.state.value.diagnostics.samples)
                vm.setDiagnosticsEnabled(true); vm.onResult(result())
                assertEquals(1, vm.state.value.diagnostics.samples)
                vm.setDiagnosticsEnabled(false)
                assertEquals(0, vm.state.value.diagnostics.samples)
                assertNotNull(vm.state.value.result)
                vm.setDiagnosticsEnabled(true); vm.onResult(result()); vm.onError(DetectionFailure.Inference)
                assertEquals(0, vm.state.value.diagnostics.samples)
                vm.start(); vm.onResult(result()); vm.stop()
                assertEquals(0, vm.state.value.diagnostics.samples)
                assertNull(vm.state.value.result)
            } finally { store.clear() }
        }
    }

    @Test fun resultsExpireAndStopAndFailureClearBoxes() = runBlocking {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val vm = DetectionViewModel()
        val store = ViewModelStore()
        fun result(age: Long = 0) = DetectionResult(listOf(DetectedObject("person",0.9f,ViewBox(0f,0f,0.2f,0.5f))),
            SystemClock.elapsedRealtime() - age,25)
        try {
            instrumentation.runOnMainSync {
                store.put("detector",vm)
                vm.start()
                vm.onResult(result())
                assertEquals(DetectionPhase.Active,vm.state.value.phase)
            }
            withTimeout(4000) { vm.state.first { it.phase == DetectionPhase.Stale } }
            assertNull(vm.state.value.result)
            instrumentation.runOnMainSync {
                vm.onResult(result(1500))
                assertNull(vm.state.value.result)
                vm.onResult(result())
                vm.onError(DetectionFailure.Inference)
                vm.onResult(result())
                assertEquals(DetectionPhase.Error,vm.state.value.phase)
                assertNull(vm.state.value.result)
                vm.start()
                vm.onResult(result())
                vm.stop()
                vm.onResult(result())
                assertEquals(DetectionPhase.Idle,vm.state.value.phase)
                assertNull(vm.state.value.result)
            }
        } finally { instrumentation.runOnMainSync { store.clear() } }
    }
}
