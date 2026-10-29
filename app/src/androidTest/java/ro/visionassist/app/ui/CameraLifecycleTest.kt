package ro.visionassist.app.ui

import android.Manifest
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.lifecycle.Lifecycle
import androidx.test.rule.GrantPermissionRule
import org.junit.Rule
import org.junit.Test
import ro.visionassist.app.MainActivity

/** Runs against CameraX and the emulator/device camera, with no mocked stream events. */
class CameraLifecycleTest {
    @get:Rule(order = 0) val permission: GrantPermissionRule = GrantPermissionRule.grant(Manifest.permission.CAMERA)
    @get:Rule(order = 1) val compose = createAndroidComposeRule<MainActivity>()

    private fun waitForStreaming() {
        compose.waitUntil(timeoutMillis = 20_000) {
            compose.onAllNodesWithText("Camera din spate este activă").fetchSemanticsNodes().isNotEmpty()
        }
        compose.waitUntil(timeoutMillis = 45_000) {
            compose.onAllNodesWithText("Analiza locală este activă").fetchSemanticsNodes().isNotEmpty()
        }
    }

    @Test fun previewStreamsRestartsAfterBackgroundAndRetainsExplicitStop() {
        compose.onNodeWithText("Pornește camera").performScrollTo().performClick()
        waitForStreaming()
        compose.activityRule.scenario.moveToState(Lifecycle.State.CREATED)
        compose.activityRule.scenario.moveToState(Lifecycle.State.RESUMED)
        waitForStreaming()
        compose.activityRule.scenario.recreate()
        waitForStreaming()
        compose.onNodeWithText("Oprește camera").performScrollTo().performClick()
        compose.onNodeWithText("Camera este oprită").performScrollTo().assertIsDisplayed()
        compose.activityRule.scenario.recreate()
        compose.onNodeWithText("Camera este oprită").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Pornește camera").performScrollTo().performClick()
        waitForStreaming()
        compose.onNodeWithText("Oprește camera").performScrollTo().performClick()
    }

    @Test fun optionalGroundAnalysisRunsAlongsideObjectsAndStopsWithCamera() {
        compose.onNodeWithText("Pornește analiza experimentală a gropilor").performScrollTo().performClick()
        compose.onNodeWithText("Pornește camera").performScrollTo().performClick()
        waitForStreaming()
        compose.waitUntil(timeoutMillis=30_000) {
            compose.onAllNodesWithText("Cadre analizate:",substring=true).fetchSemanticsNodes().isNotEmpty()
        }
        compose.onNodeWithText("Avertismentele pentru gropi sunt indisponibile: precizia modelului nu a trecut evaluarea.")
            .performScrollTo().assertIsDisplayed()
        compose.activityRule.scenario.moveToState(Lifecycle.State.CREATED)
        compose.activityRule.scenario.moveToState(Lifecycle.State.RESUMED)
        waitForStreaming()
        compose.onNodeWithText("Oprește camera").performScrollTo().performClick()
        compose.onNodeWithText("Pornește camera pentru analiză.").performScrollTo().assertIsDisplayed()
    }
}
