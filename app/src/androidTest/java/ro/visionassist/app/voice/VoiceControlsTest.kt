package ro.visionassist.app.voice

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.Density
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.After
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import ro.visionassist.app.ui.VisionAssistTheme
import ro.visionassist.core.camera.CameraSnapshotRequest
import ro.visionassist.core.voice.*
import kotlinx.coroutines.flow.MutableStateFlow

class VoiceControlsTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var client: VoiceClient
    private lateinit var local: LocalAnnouncements
    @After fun close() { compose.runOnIdle { if (::local.isInitialized) local.close(); if (::client.isInitialized) client.close() } }

    @Test fun stopRemainsAvailableDuringLocalPriorityAndStartRemainsBlockedAfterStop() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val events = MutableStateFlow(VoiceState(VoicePhase.Listening, warningActive = true))
        var stops = 0
        compose.runOnIdle {
            // UI state fixture only: no microphone, network or synthetic detections.
            client = object : VoiceClient {
                override val state = events
                override fun start(settings: BackendSettings) { error("Start must stay blocked by priority") }
                override fun stop() { stops++; events.value = VoiceState(warningActive = true) }
                override fun beginLocalWarning(id: String) = Unit
                override fun endLocalWarning(id: String) = Unit
                override suspend fun sendRequestedImage(capture: suspend () -> ByteArray) = Unit
                override fun declineImage(reason: String) = Unit
                override fun close() = Unit
            }
            local = LocalAnnouncements(context, client)
        }
        compose.setContent {
            VisionAssistTheme { Column(Modifier.verticalScroll(rememberScrollState())) {
                VoiceControls(client, local, CameraSnapshotRequest(), false, true)
            } }
        }
        compose.onNodeWithText("Oprește conversația AI").performScrollTo().assertIsEnabled().performClick()
        compose.runOnIdle { assertEquals(1, stops) }
        compose.onNodeWithText("Pornește conversația AI").performScrollTo().assertIsNotEnabled()
    }

    @Test fun accessibleSetupAtLargeFontDoesNotUploadImagesOrOpenMicrophone() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        context.getSharedPreferences("voice_backend", 0).edit().clear().commit()
        compose.runOnIdle { client = RealtimeVoiceClient(context, true); local = LocalAnnouncements(context, client) }
        compose.setContent {
            CompositionLocalProvider(LocalDensity provides Density(LocalDensity.current.density, 2f)) {
                VisionAssistTheme { Column(Modifier.verticalScroll(rememberScrollState())) {
                    VoiceControls(client, local, CameraSnapshotRequest(), false, true)
                } }
            }
        }
        compose.onNodeWithText("Ce este în fața mea? Trimite o fotografie").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithText("Pornește conversația AI").performScrollTo().assertHasClickAction().performClick()
        compose.onNodeWithText("Adresa HTTPS a serverului").assertExists()
        compose.onNodeWithText("Google Gemini").performScrollTo().assertIsSelected().assertHasClickAction()
        compose.onNodeWithText("OpenAI").performScrollTo().performClick().assertIsSelected()
        compose.onNodeWithText("Anulează").performClick()
        compose.runOnIdle { assertEquals(VoicePhase.Disconnected, client.state.value.phase) }
    }
    @Test fun localPrioritySurvivesStopAndLateCompletionWithoutAConnection() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        compose.runOnIdle {
            client = RealtimeVoiceClient(context)
            client.beginLocalWarning("first"); client.beginLocalWarning("second")
            client.start(BackendSettings("", "")) // Must not validate/connect while a local warning owns audio.
            assertEquals(VoicePhase.Disconnected, client.state.value.phase)
            client.endLocalWarning("first"); assertTrue(client.state.value.warningActive)
            client.stop(); assertTrue(client.state.value.warningActive)
            client.endLocalWarning("first"); assertTrue(client.state.value.warningActive)
            client.endLocalWarning("second"); assertFalse(client.state.value.warningActive)
            client.close(); client.close()
        }
    }

    @Test fun geminiOverlappingWarningsBlockStartAndRequireExplicitRestart() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        compose.runOnIdle {
            client = GeminiVoiceClient(context, true)
            client.beginLocalWarning("first"); client.beginLocalWarning("second")
            client.start(BackendSettings("", "", VoiceProvider.Gemini)) // Must not attempt validation/network while muted.
            assertEquals(VoicePhase.Disconnected, client.state.value.phase)
            client.stop(); client.endLocalWarning("first"); client.endLocalWarning("first")
            assertTrue(client.state.value.warningActive)
            client.endLocalWarning("second"); assertFalse(client.state.value.warningActive)
            assertEquals(VoicePhase.Disconnected, client.state.value.phase)
            client.close(); client.close()
        }
    }
}
