package ro.visionassist.app.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.Density
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/** UI ownership test. CameraLifecycleTest separately exercises actual CameraX frames. */
class NavigationRetentionTest {
    @get:Rule val compose = createComposeRule()
    @Test fun largeTextNavigationLabelsDoNotOverlapAndPrimaryControlNeedsNoScrolling() {
        compose.setContent {
            CompositionLocalProvider(LocalDensity provides Density(LocalDensity.current.density, 2f)) {
                VisionAssistTheme(darkTheme = true) {
                    VisionAssistScreen(ScreenStatus.Stopped, false, {}, {}, {}, {}, {})
                }
            }
        }
        compose.onNodeWithText("Pornește camera").assertIsDisplayed()
        val labels = listOf("Asistență", "Asistent AI", "Setări").map {
            compose.onNodeWithText(it, useUnmergedTree = true).assertIsDisplayed().fetchSemanticsNode().boundsInRoot
        }
        assertTrue(labels[0].right <= labels[1].left)
        assertTrue(labels[1].right <= labels[2].left)
        compose.onNodeWithText("Asistent AI").performClick()
        compose.onNodeWithText("Pornește camera").assertIsDisplayed()
    }
    @Test fun navigationKeepsCameraHostMountedAndMeasuredAndStopVisible() {
        var mounts = 0; var disposals = 0; var measured = IntSize.Zero; var stops = 0
        compose.setContent {
            VisionAssistTheme {
                VisionAssistScreen(ScreenStatus.Streaming, false, { stops++ }, {}, {}, {},
                    preview = { modifier ->
                        DisposableEffect(Unit) { mounts++; onDispose { disposals++ } }
                        Box(modifier.onSizeChanged { measured = it })
                    })
            }
        }
        var initial = IntSize.Zero
        compose.runOnIdle { initial = measured; assertTrue(initial.width > 0 && initial.height > 0) }
        compose.onNodeWithText("Asistent AI").performClick()
        compose.onNodeWithText("Oprește camera").assertIsDisplayed().performClick()
        compose.onNodeWithText("Setări").performClick()
        compose.onNodeWithText("Oprește camera").assertIsDisplayed()
        compose.onNodeWithText("Asistență").performClick()
        compose.runOnIdle {
            assertEquals(1, mounts); assertEquals(0, disposals); assertEquals(initial, measured); assertEquals(1, stops)
        }
    }
}
