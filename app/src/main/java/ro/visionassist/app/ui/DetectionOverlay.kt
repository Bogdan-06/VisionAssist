package ro.visionassist.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ro.visionassist.core.detection.DetectionResult

/** Drawing coordinates are normalized by the CameraX mapper, never guessed from box size. */
@Composable
fun DetectionOverlay(result: DetectionResult?, modifier: Modifier = Modifier) {
    val measurer = rememberTextMeasurer()
    Canvas(modifier) {
        val placedLabels = mutableListOf<Rect>()
        result?.objects?.forEach { obj ->
            val b = obj.bounds
            val topLeft = Offset(b.left * size.width, b.top * size.height)
            drawRect(Color(0xFFA5E8D3), topLeft,
                Size((b.right - b.left) * size.width, (b.bottom - b.top) * size.height), style = Stroke(3.dp.toPx()))
            val padding = 4.dp.toPx()
            val text = measurer.measure(
                DetectionLabels.description(obj),
                style = TextStyle(color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold),
                constraints = Constraints(maxWidth = (size.width - padding * 2).toInt().coerceAtLeast(1))
            )
            val labelSize = Size(text.size.width + padding * 2, text.size.height + padding * 2)
            val x = topLeft.x.coerceIn(0f, (size.width - labelSize.width).coerceAtLeast(0f))
            val maxY = (size.height - labelSize.height).coerceAtLeast(0f)
            val preferredY = (topLeft.y - labelSize.height).coerceIn(0f, maxY)
            val candidates = listOf(preferredY, topLeft.y.coerceIn(0f, maxY),
                (b.bottom * size.height).coerceIn(0f, maxY)) +
                generateSequence(0f) { it + labelSize.height + padding }.takeWhile { it <= maxY }.toList()
            val y = candidates.firstOrNull { candidate ->
                val rect = Rect(Offset(x, candidate), labelSize)
                placedLabels.none { it.overlaps(rect) }
            } ?: preferredY // Dense scenes still have the complete accessible text list below.
            val origin = Offset(x, y)
            placedLabels += Rect(origin, labelSize)
            if (y != preferredY) {
                drawLine(Color(0xFFA5E8D3), Offset(x + labelSize.width / 2, y), topLeft, 1.dp.toPx())
            }
            drawRect(Color.Black.copy(alpha = 0.9f), origin, labelSize)
            drawText(text, topLeft = origin + Offset(padding, padding))
        }
    }
}
