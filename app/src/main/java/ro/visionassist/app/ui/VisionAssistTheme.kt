package ro.visionassist.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Deliberately stable, high-contrast colors; do not derive status meaning from color alone.
private val colors = darkColorScheme(
    primary = Color(0xFFA5E8D3),
    onPrimary = Color(0xFF082A22),
    background = Color(0xFF101820),
    onBackground = Color(0xFFF5F7FA),
    surface = Color(0xFF101820),
    onSurface = Color(0xFFF5F7FA),
    surfaceVariant = Color(0xFF24323E),
    onSurfaceVariant = Color(0xFFE1E8EE),
    secondaryContainer = Color(0xFF3C321B),
    onSecondaryContainer = Color(0xFFFFE6AB),
    outline = Color(0xFFB1C1CD)
)

@Composable
fun VisionAssistTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = colors, content = content)
}
