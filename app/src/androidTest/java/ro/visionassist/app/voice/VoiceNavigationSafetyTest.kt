package ro.visionassist.app.voice

import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import ro.visionassist.app.ui.*
import ro.visionassist.core.ground.GroundModelReadiness
import ro.visionassist.core.voice.*

/** Real route + real selectable-client priority state; no cloud, microphone or camera start. */
class VoiceNavigationSafetyTest {
    @get:Rule val compose = createComposeRule()

    @Test fun navigationAndDeveloperModeCannotReleaseAudioPriorityOrEnableExperimentalWarnings() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        lateinit var client: SelectableVoiceClient
        compose.runOnIdle { client = SelectableVoiceClient(context, true) }
        try {
            compose.setContent {
                var preferences by remember { mutableStateOf(UiPreferences(InterfaceLayout.Compact)) }
                VisionAssistTheme {
                    VisionAssistRoute(preferences = preferences,
                        onDeveloper = { preferences = preferences.copy(developer = it) }, voiceClient = client)
                }
            }
            compose.runOnIdle { client.beginLocalWarning("first") }
            compose.onNodeWithText("Asistent AI").performClick()
            compose.onNodeWithText("Pornește conversația AI").performScrollTo().assertIsNotEnabled()
            compose.onNodeWithText("Setări").performClick()
            compose.onNodeWithText("Mod dezvoltator").performScrollTo().performClick()
            compose.onNodeWithText("Analiză experimentală indisponibilă").performScrollTo().assertIsNotEnabled()
            compose.runOnIdle {
                assertFalse(GroundModelReadiness.WARNINGS_VALIDATED)
                client.beginLocalWarning("second"); client.endLocalWarning("first")
                client.start(BackendSettings("", "", VoiceProvider.OpenAI))
                assertEquals(VoicePhase.Disconnected, client.state.value.phase)
                assertTrue(client.state.value.warningActive)
            }
            compose.onNodeWithText("Asistență").performClick()
            compose.onNodeWithText("Asistent AI").performClick()
            compose.onNodeWithText("Pornește conversația AI").performScrollTo().assertIsNotEnabled()
            compose.runOnIdle { client.endLocalWarning("second") }
            compose.onNodeWithText("Pornește conversația AI").performScrollTo().assertIsEnabled()
        } finally { compose.runOnIdle { client.close() } }
    }
}
