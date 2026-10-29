package ro.visionassist.app.ui

import android.Manifest
import android.content.pm.PackageManager
import android.util.Log
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.core.content.ContextCompat
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import ro.visionassist.app.depth.DepthActivity
import kotlin.math.abs
import kotlin.math.max

/** Opt-in only: requires a prepared physical scene and an independently measured distance. */
class PhysicalDepthMeasurementTest {
    @get:Rule val compose=createEmptyComposeRule()

    @Test fun centralSurfaceAgreesWithPreparedReference() {
        val instrumentation=InstrumentationRegistry.getInstrumentation()
        val arguments=InstrumentationRegistry.getArguments()
        assumeTrue("Requires explicit prepared-scene opt-in",arguments.getString("allow_physical_depth")=="true")
        val expected=requireNotNull(arguments.getString("known_distance_m")?.toFloatOrNull()) {
            "Supply the real rear-camera-to-surface distance in metres"
        }
        require(expected.isFinite() && expected in .5f..8f)
        val context=instrumentation.targetContext
        require(ContextCompat.checkSelfPermission(context,Manifest.permission.CAMERA)==PackageManager.PERMISSION_GRANTED) {
            "Grant camera permission in the app before the prepared-scene test"
        }
        val pattern=Regex("Suprafața centrală: aproximativ ([0-9]+[,.][0-9]+) metri")
        var reading:Float?=null
        ActivityScenario.launch(DepthActivity::class.java).use {
            compose.waitUntil(timeoutMillis=60_000) {
                reading=compose.onAllNodesWithText("Suprafața centrală: aproximativ",substring=true)
                    .fetchSemanticsNodes().firstNotNullOfOrNull { node ->
                        node.config[SemanticsProperties.Text].firstNotNullOfOrNull { text ->
                            pattern.find(text.text)?.groupValues?.get(1)?.replace(',','.')?.toFloatOrNull()
                        }
                    }
                reading!=null
            }
            val actual=requireNotNull(reading)
            val tolerance=max(.15f,expected*.15f)
            Log.i("PhysicalDepthCheck","reference_m=$expected center_m=$actual tolerance_m=$tolerance; single rounded UI reading, not a navigation accuracy study")
            assertTrue("Measured $actual m, reference $expected m, coarse tolerance $tolerance m",abs(actual-expected)<=tolerance)
        }
    }
}
