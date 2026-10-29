package ro.visionassist.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ro.visionassist.app.ui.*
import ro.visionassist.app.ui.VisionAssistRoute
import ro.visionassist.app.ui.VisionAssistTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT)
        )
        setContent {
            val preferences: UiPreferencesViewModel = viewModel()
            val state by preferences.state.collectAsStateWithLifecycle()
            val dark = when (state.value?.theme) {
                ThemeChoice.Dark -> true
                ThemeChoice.Light -> false
                else -> isSystemInDarkTheme()
            }
            SideEffect {
                enableEdgeToEdge(
                    statusBarStyle = SystemBarStyle.auto(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT) { dark },
                    navigationBarStyle = SystemBarStyle.dark(0xFF101820.toInt())
                )
                WindowCompat.getInsetsController(window, window.decorView).apply {
                    isAppearanceLightStatusBars = !dark
                    isAppearanceLightNavigationBars = false
                }
            }
            VisionAssistTheme(dark) {
                val value = state.value
                when {
                    value == null -> Surface(Modifier.fillMaxSize()) {
                        Column(Modifier.systemBarsPadding().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                            Text(state.error ?: "Se încarcă preferințele…")
                            if (state.error != null) Button(onClick = preferences::reload) { Text("Încearcă din nou") }
                        }
                    }
                    value.layout == null -> OnboardingScreen(state.saving, state.error, preferences::layout)
                    else -> VisionAssistRoute(value, state.error, preferences::layout, preferences::theme,
                        preferences::developer, preferences::announcements)
                }
            }
        }
    }
}
