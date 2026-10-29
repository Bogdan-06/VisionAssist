package ro.visionassist.app.ui

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class OnboardingAccessibilityTest {
    @get:Rule val compose = createComposeRule()
    @Test fun layoutChoiceAndContinueRemainAccessibleAtDoubleTextSize() {
        var choice: InterfaceLayout? = null
        compose.setContent {
            CompositionLocalProvider(LocalDensity provides Density(LocalDensity.current.density, 2f)) {
                VisionAssistTheme(darkTheme = true) { OnboardingScreen(false, null) { choice = it } }
            }
        }
        compose.onNodeWithText("Compact").performScrollTo().performClick()
        compose.onNodeWithText("Salvează și continuă").assertIsDisplayed().assertHeightIsAtLeast(64.dp).performClick()
        compose.runOnIdle { assertEquals(InterfaceLayout.Compact, choice) }
    }
}
