package ro.visionassist.app.ui

import android.Manifest
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModelProvider
import androidx.test.rule.GrantPermissionRule
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import ro.visionassist.app.MainActivity

/** Runs against CameraX and the emulator/device camera, with no mocked stream events. */
class CameraLifecycleTest {
    @get:Rule(order = 0) val permission: GrantPermissionRule = GrantPermissionRule.grant(Manifest.permission.CAMERA)
    @get:Rule(order = 1) val compose = createAndroidComposeRule<MainActivity>()

    @Before fun onboarding() { completeOnboardingIfNeeded(compose) }

    private fun waitForStreaming() {
        compose.waitUntil(timeoutMillis = 20_000) {
            compose.onAllNodesWithText("Camera din spate este activă").fetchSemanticsNodes().isNotEmpty()
        }
        compose.waitUntil(timeoutMillis = 45_000) {
            compose.onAllNodesWithText("Analiza locală este activă").fetchSemanticsNodes().isNotEmpty()
        }
    }

    @Test fun previewStreamsRestartsAfterBackgroundAndRetainsExplicitStop() {
        compose.onNodeWithText("Pornește camera").performClick()
        waitForStreaming()
        compose.activityRule.scenario.moveToState(Lifecycle.State.CREATED)
        compose.activityRule.scenario.moveToState(Lifecycle.State.RESUMED)
        waitForStreaming()
        compose.activityRule.scenario.recreate()
        waitForStreaming()
        compose.onNodeWithText("Oprește camera").performClick()
        compose.onNodeWithText("Camera este oprită").assertIsDisplayed()
        compose.activityRule.scenario.recreate()
        compose.onNodeWithText("Camera este oprită").assertIsDisplayed()
        compose.onNodeWithText("Pornește camera").performClick()
        waitForStreaming()
        compose.onNodeWithText("Oprește camera").performClick()
    }

    @Test fun navigationPreservesAnalysisAndExperimentalGroundStaysDisabled() {
        compose.onNodeWithText("Pornește camera").performClick()
        waitForStreaming()
        lateinit var detector: DetectionViewModel
        compose.runOnIdle { detector = ViewModelProvider(compose.activity)[DetectionViewModel::class.java] }
        val beforeVoice = detector.state.value.result!!.receivedAtMs
        compose.onNodeWithText("Asistent AI").performClick()
        compose.onNodeWithText("Camera din spate este activă").assertIsDisplayed()
        compose.onNodeWithText("Pornește conversația AI").assertExists()
        compose.waitUntil(20_000) { (detector.state.value.result?.receivedAtMs ?: 0) > beforeVoice }
        val beforeSettings = detector.state.value.result!!.receivedAtMs
        compose.onNodeWithText("Setări").performClick()
        compose.waitUntil(20_000) { (detector.state.value.result?.receivedAtMs ?: 0) > beforeSettings }
        compose.onNodeWithText("Analiză experimentală indisponibilă").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithText("Asistență").performClick()
        waitForStreaming()
        compose.onNodeWithText("Oprește camera").performClick()
        compose.onNodeWithText("Camera este oprită").assertIsDisplayed()
    }
}
