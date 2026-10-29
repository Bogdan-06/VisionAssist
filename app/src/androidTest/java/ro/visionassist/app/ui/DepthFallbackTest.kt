package ro.visionassist.app.ui

import android.Manifest
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performClick
import androidx.test.rule.GrantPermissionRule
import com.google.ar.core.ArCoreApk
import org.junit.Assume.assumeFalse
import org.junit.Rule
import org.junit.Test
import ro.visionassist.app.MainActivity

/** Actual unsupported runtime path. A supported device must be tested separately for real depth. */
class DepthFallbackTest {
    @get:Rule(order=0) val permission:GrantPermissionRule=GrantPermissionRule.grant(Manifest.permission.CAMERA)
    @get:Rule(order=1) val compose=createAndroidComposeRule<MainActivity>()

    @Test fun unsupportedDeviceShowsFallbackAndNoMeasuredDistance() {
        val availability=ArCoreApk.getInstance().checkAvailability(compose.activity)
        assumeFalse("Supported runtime requires physical depth validation",availability.isSupported)
        compose.onNodeWithText("Deschide experimentul de adâncime").performScrollTo().performClick()
        compose.waitUntil(timeoutMillis=15_000) {
            compose.onAllNodesWithText("ARCore nu este disponibil pe acest dispozitiv.",substring=true).fetchSemanticsNodes().isNotEmpty()
        }
        compose.onNodeWithText("Înapoi la VisionAssist").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Nu există rezultate recente.").performScrollTo().assertIsDisplayed()
        org.junit.Assert.assertTrue(compose.onAllNodesWithText("metri față de planul camerei",substring=true).fetchSemanticsNodes().isEmpty())
        compose.onNodeWithText("Înapoi la VisionAssist").performScrollTo().performClick()
        compose.onNodeWithText("Pornește camera").performScrollTo().performClick()
        compose.waitUntil(timeoutMillis=45_000) {
            compose.onAllNodesWithText("Camera din spate este activă").fetchSemanticsNodes().isNotEmpty() &&
                compose.onAllNodesWithText("Analiza locală este activă").fetchSemanticsNodes().isNotEmpty()
        }
        compose.onNodeWithText("Oprește camera").performScrollTo().performClick()
    }
}
