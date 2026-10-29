package ro.visionassist.app.ui

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import org.junit.Rule
import org.junit.Test
import ro.visionassist.app.MainActivity

/** Uses the actual MainActivity/DataStore, never starts camera, microphone or a cloud session. */
class InterfaceFlowTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun chosenLayoutCanChangeInSettingsAndSurvivesActivityRecreation() {
        completeOnboardingIfNeeded(compose)
        compose.onNodeWithText("Setări").performClick()
        compose.onNodeWithText("Compact").performScrollTo().performClick()
        compose.waitUntil(10_000) {
            compose.onAllNodes(isSelected() and (hasText("Compact") or hasAnyDescendant(hasText("Compact")))).fetchSemanticsNodes().isNotEmpty()
        }
        compose.activityRule.scenario.recreate()
        compose.waitUntil(15_000) { compose.onAllNodesWithText("Aspectul interfeței").fetchSemanticsNodes().isNotEmpty() }
        compose.onNode(isSelected() and (hasText("Compact") or hasAnyDescendant(hasText("Compact")))).assertExists()
        compose.onAllNodesWithText("Bun venit în VisionAssist").assertCountEquals(0)
        compose.onNodeWithText("Cameră în prim-plan").performScrollTo().performClick()
        compose.waitUntil(10_000) {
            compose.onAllNodes(isSelected() and (hasText("Cameră în prim-plan") or hasAnyDescendant(hasText("Cameră în prim-plan")))).fetchSemanticsNodes().isNotEmpty()
        }
        compose.onNodeWithText("Mod dezvoltator").performScrollTo().assertIsToggleable().performClick()
        compose.onNodeWithText("Întunecată").performScrollTo().performClick()
        compose.waitUntil(10_000) {
            compose.onAllNodes(isSelected() and (hasText("Întunecată") or hasAnyDescendant(hasText("Întunecată")))).fetchSemanticsNodes().isNotEmpty()
        }
        compose.onNodeWithText("Asistent AI").performClick()
        compose.onNodeWithText("Pornește conversația AI").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Asistență").performClick()
        compose.onNodeWithText("Anunțuri recente").performScrollTo().assertIsDisplayed()
    }
}
