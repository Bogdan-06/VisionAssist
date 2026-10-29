package ro.visionassist.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import ro.visionassist.core.detection.DetectionResult

/** Decorative boxes; the adjacent Romanian text panel provides the accessible equivalent. */
@Composable
fun GroundOverlay(result: DetectionResult?, modifier: Modifier = Modifier) {
    Canvas(modifier) {
        result?.objects?.forEach { obj ->
            val b=obj.bounds
            drawRect(Color(0xFFFFB300),Offset(b.left*size.width,b.top*size.height),
                Size((b.right-b.left)*size.width,(b.bottom-b.top)*size.height),style=Stroke(3.dp.toPx()))
        }
    }
}
