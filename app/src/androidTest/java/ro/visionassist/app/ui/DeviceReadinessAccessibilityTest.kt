package ro.visionassist.app.ui

import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class DeviceReadinessAccessibilityTest {
    @get:Rule val compose = createComposeRule()

    @Test fun diagnosticsSampleRealProcessMemoryWithoutClaimingCameraMeasurements() {
        compose.setContent { VisionAssistTheme {
            DeveloperDiagnostics(DetectionUiState(), ScreenStatus.Stopped, true, ro.visionassist.core.voice.VoiceState())
        } }
        compose.waitUntil(10_000) {
            compose.onAllNodesWithText("PSS proces:", substring = true).fetchSemanticsNodes().any { node ->
                node.config.getOrElse(SemanticsProperties.Text) { emptyList() }.any { it.text.contains("MiB") }
            }
        }
        compose.onNodeWithText("Inferență: nu există eșantioane recente.").assertExists()
        compose.onNodeWithText("Vârsta rezultatului: indisponibilă.").assertExists()
        compose.onNodeWithText("Diagnostic dezvoltator")
            .assert(SemanticsMatcher.keyNotDefined(SemanticsProperties.LiveRegion))
    }

    @Test fun allDestinationsHaveStableTraversalGroupsAndDiagnosticsStayDeveloperOnlyAtDoubleText() {
        compose.setContent {
            var developer by remember { mutableStateOf(false) }
            CompositionLocalProvider(LocalDensity provides Density(LocalDensity.current.density, 2f)) {
                VisionAssistTheme {
                    VisionAssistScreen(ScreenStatus.Stopped, false, {}, {}, {}, {}, {},
                        preferences = UiPreferences(InterfaceLayout.Compact, developer = developer),
                        onDeveloper = { developer = it }, diagnostics = { RoText("Diagnostic de test") })
                }
            }
        }
        for ((tag, index) in listOf("primary-region" to 0f, "content-region" to 1f, "navigation-region" to 2f)) {
            compose.onNodeWithTag(tag, useUnmergedTree = true)
                .assert(SemanticsMatcher.expectValue(SemanticsProperties.IsTraversalGroup, true))
                .assert(SemanticsMatcher.expectValue(SemanticsProperties.TraversalIndex, index))
        }
        val layouts = mutableListOf<TextLayoutResult>()
        compose.onNodeWithText("Asistență", useUnmergedTree = true)
            .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { action -> assertTrue(action(layouts)) }
        assertEquals(1, layouts.single().lineCount)
        assertFalse(layouts.single().hasVisualOverflow)
        for (page in listOf("Asistență", "Asistent AI", "Setări")) {
            compose.onNodeWithText(page).performClick()
            compose.onNodeWithTag("content-region", useUnmergedTree = true)
                .assert(SemanticsMatcher.expectValue(SemanticsProperties.PaneTitle, page))
            compose.onNodeWithText("Pornește camera").assertIsDisplayed().assertHeightIsAtLeast(64.dp)
            compose.onAllNodesWithText("Diagnostic de test").assertCountEquals(0)
        }
        compose.onNodeWithText("Mod dezvoltator").performScrollTo().performClick()
        for (page in listOf("Asistență", "Asistent AI", "Setări")) {
            compose.onNodeWithText(page).performClick()
            compose.onNodeWithText("Diagnostic de test").performScrollTo().assertIsDisplayed()
        }
    }

    @Test fun cameraAndAnalysisErrorsExposeRetryWithoutClaimingDetection() {
        var retriedCamera = false
        var retriedAnalysis = false
        compose.setContent {
            VisionAssistTheme {
                VisionAssistScreen(ScreenStatus.Error, false, { retriedCamera = true }, {}, {}, {}, {},
                    detectionState = DetectionUiState(DetectionPhase.Error),
                    onRetryDetection = { retriedAnalysis = true })
            }
        }
        compose.onNodeWithText("Încearcă din nou").assertHasClickAction().performClick()
        compose.onNodeWithText("Repornește analiza locală").performScrollTo().performClick()
        compose.runOnIdle { assertTrue(retriedCamera); assertTrue(retriedAnalysis) }
        compose.onAllNodesWithText("Analiza locală este activă").assertCountEquals(0)
    }

    @Test fun onboardingSaveFailureKeepsChoiceAndRetryAvailable() {
        var attempts = 0
        val choices = mutableListOf<InterfaceLayout>()
        compose.setContent {
            var error by remember { mutableStateOf<String?>(null) }
            VisionAssistTheme {
                OnboardingScreen(false, error) { choices += it; attempts++; error = "Preferința nu a fost salvată. Încearcă din nou." }
            }
        }
        compose.onNodeWithText("Compact").performScrollTo().performClick()
        compose.onNodeWithText("Salvează și continuă").performClick()
        compose.onNodeWithText("Preferința nu a fost salvată. Încearcă din nou.").performScrollTo().assertExists()
        compose.onNodeWithText("Salvează și continuă").assertIsEnabled().performClick()
        compose.runOnIdle { assertEquals(2, attempts); assertEquals(listOf(InterfaceLayout.Compact, InterfaceLayout.Compact), choices) }
    }
}
