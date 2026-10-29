package ro.visionassist.app.ui

import androidx.compose.ui.test.junit4.AndroidComposeTestRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.rules.ActivityScenarioRule
import ro.visionassist.app.MainActivity

internal fun completeOnboardingIfNeeded(compose: AndroidComposeTestRule<ActivityScenarioRule<MainActivity>, MainActivity>) {
    compose.waitUntil(15_000) {
        compose.onAllNodesWithText("Salvează și continuă").fetchSemanticsNodes().isNotEmpty() ||
            compose.onAllNodesWithText("VisionAssist").fetchSemanticsNodes().isNotEmpty()
    }
    if (compose.onAllNodesWithText("Salvează și continuă").fetchSemanticsNodes().isNotEmpty()) {
        compose.onNodeWithText("Salvează și continuă").performClick()
        compose.waitUntil(15_000) { compose.onAllNodesWithText("VisionAssist").fetchSemanticsNodes().isNotEmpty() }
    }
}
