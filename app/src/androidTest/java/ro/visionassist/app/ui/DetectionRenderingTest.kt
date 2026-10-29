package ro.visionassist.app.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.width
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.unit.dp
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import ro.visionassist.core.detection.DetectedObject
import ro.visionassist.core.detection.DetectionResult
import ro.visionassist.core.detection.ObjectDetector
import ro.visionassist.core.detection.visibleBox
import java.io.File

class DetectionRenderingTest {
    @get:Rule val compose = createComposeRule()

    @Test fun actualModelResultsRenderBoxesLabelsConfidenceAndDirections() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val bitmap = instrumentation.context.assets.open("cats_and_dogs.jpg").use { BitmapFactory.decodeStream(it) }
        val detections = ObjectDetector(instrumentation.targetContext).use { detector ->
            detector.detect(bitmap.copy(Bitmap.Config.ARGB_8888, false))
        }
        val objects = detections.mapNotNull { obj ->
            visibleBox(obj.bounds,bitmap.width,bitmap.height)?.let { DetectedObject(obj.label,obj.confidence,it) }
        }
        assertTrue(objects.isNotEmpty())
        val result = DetectionResult(objects,0,0)
        compose.setContent {
            VisionAssistTheme {
                Column {
                    Box(Modifier.width(360.dp).aspectRatio(bitmap.width.toFloat()/bitmap.height).testTag("detected-image")) {
                        Image(bitmap.asImageBitmap(),contentDescription = "Imagine de test",modifier = Modifier.fillMaxSize())
                        DetectionOverlay(result,Modifier.fillMaxSize())
                    }
                    DetectionPanel(DetectionUiState(DetectionPhase.Active,result),{})
                }
            }
        }
        objects.forEach { compose.onNodeWithText(DetectionLabels.description(it)).assertExists() }
        val screenshot = compose.onNodeWithTag("detected-image").captureToImage().asAndroidBitmap()
        File(instrumentation.targetContext.getExternalFilesDir(null),"detection-render.png").outputStream().use {
            screenshot.compress(Bitmap.CompressFormat.PNG,100,it)
        }
        // Bitmap remains owned by the composable until the test Activity is disposed.
    }
}
