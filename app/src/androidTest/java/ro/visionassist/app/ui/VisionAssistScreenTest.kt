package ro.visionassist.app.ui

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.unit.Density
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class VisionAssistScreenTest {
    @get:Rule val compose = createComposeRule()

    @Test fun permissionControlIsLabeledAndActionable() {
        var clicked = false
        compose.setContent {
            VisionAssistTheme {
                VisionAssistScreen(ScreenStatus.PermissionRequired, false, { clicked = true }, {}, {}, {}, {})
            }
        }
        compose.onNodeWithText("Permite accesul la cameră").performScrollTo()
            .assertIsDisplayed().assertHasClickAction()
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.Button)).performClick()
        compose.runOnIdle { assertTrue(clicked) }
        compose.onNodeWithText("Este necesar accesul la cameră")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.LiveRegion, LiveRegionMode.Polite))
    }

    @Test fun deniedPermissionOffersSettingsAtLargeFontScale() {
        var opened = false
        compose.setContent {
            CompositionLocalProvider(LocalDensity provides Density(LocalDensity.current.density, 2f)) {
                VisionAssistTheme {
                    VisionAssistScreen(ScreenStatus.PermissionDenied, false, {}, { opened = true }, {}, {}, {})
                }
            }
        }
        compose.onNodeWithText("Deschide setările aplicației").performScrollTo()
            .assertIsDisplayed().performClick()
        compose.runOnIdle { assertTrue(opened) }
    }

    @Test fun activePreviewExposesStopAndHonestLimitations() {
        var stopped = false
        compose.setContent {
            VisionAssistTheme {
                VisionAssistScreen(ScreenStatus.Streaming, false, { stopped = true }, {}, {}, {}, {})
            }
        }
        compose.onNodeWithText("Obiectele recunoscute apar în chenar și în lista de sub cameră. Nu sunt estimate distanțe sau trasee sigure.")
            .performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Oprește camera").performScrollTo().performClick()
        compose.runOnIdle { assertTrue(stopped) }
    }

    @Test fun helpCanBeDismissed() {
        var dismissed = false
        compose.setContent {
            VisionAssistTheme {
                VisionAssistScreen(ScreenStatus.Stopped, true, {}, {}, {}, { dismissed = true }, {})
            }
        }
        compose.onNodeWithText("Am înțeles").assertHasClickAction().performClick()
        compose.runOnIdle { assertTrue(dismissed) }
    }
}
