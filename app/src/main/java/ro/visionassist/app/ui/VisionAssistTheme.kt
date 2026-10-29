package ro.visionassist.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.foundation.isSystemInDarkTheme
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
    secondaryContainer = Color(0xFF234B40),
    onSecondaryContainer = Color(0xFFCEF6E6),
    surfaceContainer = Color(0xFF182830),
    surfaceContainerHigh = Color(0xFF24323E),
    outline = Color(0xFFB1C1CD)
)

@Composable
fun VisionAssistTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (darkTheme) colors else lightColors, content = content)
}

private val lightColors = lightColorScheme(
    primary = Color(0xFF00634E), onPrimary = Color.White,
    background = Color(0xFFF6FAF8), onBackground = Color(0xFF10231D),
    surface = Color(0xFFF6FAF8), onSurface = Color(0xFF10231D),
    surfaceVariant = Color(0xFFDFEAE4), onSurfaceVariant = Color(0xFF35483F),
    secondaryContainer = Color(0xFFC8EBDD), onSecondaryContainer = Color(0xFF102E22),
    surfaceContainer = Color(0xFFECF4EF), surfaceContainerHigh = Color(0xFFE5EFE9),
    outline = Color(0xFF52685D)
)
