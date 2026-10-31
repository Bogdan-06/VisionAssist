package ro.visionassist.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.intl.LocaleList
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ro.visionassist.app.R
import ro.visionassist.core.detection.DetectionResult

@Composable
internal fun RoText(text: String, modifier: Modifier = Modifier, title: Boolean = false) {
    Text(AnnotatedString(text, SpanStyle(localeList = LocaleList("ro-RO"))),
        modifier = if (title) modifier.semantics { heading() } else modifier,
        style = if (title) MaterialTheme.typography.titleLarge else MaterialTheme.typography.bodyLarge)
}

enum class Destination(val title: String) { Home("Asistență"), Voice("Asistent AI"), Settings("Setări") }

@Composable
fun OnboardingScreen(saving: Boolean, error: String?, onChoose: (InterfaceLayout) -> Unit) {
    var selected by rememberSaveable { mutableStateOf(InterfaceLayout.CameraFocused) }
    Scaffold(bottomBar = {
        Surface(shadowElevation = 8.dp) {
            Button(onClick = { onChoose(selected) }, enabled = !saving,
                modifier = Modifier.navigationBarsPadding().padding(20.dp).fillMaxWidth().heightIn(min = 64.dp)) {
                RoText(if (saving) "Se salvează…" else "Salvează și continuă")
            }
        }
    }) { insets ->
        Column(Modifier.fillMaxSize().padding(insets).verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp)) {
            RoText("Bun venit în VisionAssist", title = true)
            RoText("Alege interfața potrivită pentru tine. O poți schimba oricând din Setări.")
            LayoutOptions(selected) { selected = it }
            RoText(stringResource(R.string.safety_body))
            RoText("Camera pornește doar la cererea ta. Conversația online și trimiterea unei fotografii sunt opționale.")
            error?.let { RoText(it, Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
        }
    }
}

@Composable
internal fun LayoutOptions(selected: InterfaceLayout?, onSelect: (InterfaceLayout) -> Unit) {
    Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InterfaceLayout.entries.forEach { option ->
            OutlinedCard(Modifier.fillMaxWidth().selectable(selected == option,
                onClick = { onSelect(option) }, role = Role.RadioButton)) {
                Row(Modifier.padding(16.dp).heightIn(min = 64.dp), verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected == option, onClick = null)
                    Column(Modifier.padding(start = 12.dp).weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        RoText(option.title)
                        Text(option.description, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}

/** The preview slot is always at the same composition location and measured size on navigation.
 * Opaque destination surfaces cover it; analysis/voice ownership stays in the route.
 */
@Composable
fun VisionAssistScreen(
    status: ScreenStatus, showHelp: Boolean, onPrimary: () -> Unit, onSettings: () -> Unit,
    onHelp: () -> Unit, onDismissHelp: () -> Unit, preview: @Composable (Modifier) -> Unit,
    detectionState: DetectionUiState = DetectionUiState(), onRetryDetection: () -> Unit = {},
    voiceControls: @Composable () -> Unit = {}, groundResult: DetectionResult? = null,
    preferences: UiPreferences = UiPreferences(InterfaceLayout.Compact),
    settingsControls: @Composable () -> Unit = {},
    onLayout: (InterfaceLayout) -> Unit = {}, onTheme: (ThemeChoice) -> Unit = {},
    onDeveloper: (Boolean) -> Unit = {}, connectionSummary: String = "Asistent AI: deconectat",
    recentAnnouncements: List<String> = emptyList(), preferenceError: String? = null,
    recentHazardWarnings: List<String> = emptyList(),
    diagnostics: @Composable () -> Unit = {}
) {
    var destination by rememberSaveable { mutableStateOf(Destination.Home) }
    val navigationHeight = 80.dp + 64.dp * (LocalDensity.current.fontScale - 1f).coerceAtLeast(0f)
    BackHandler(destination != Destination.Home) { destination = Destination.Home }
    val statusText = when (status) {
        ScreenStatus.PermissionRequired -> R.string.status_permission
        ScreenStatus.PermissionDenied -> R.string.status_denied
        ScreenStatus.Stopped -> R.string.status_paused
        ScreenStatus.Starting -> R.string.status_starting
        ScreenStatus.Streaming -> R.string.status_streaming
        ScreenStatus.Unavailable -> R.string.status_unavailable
        ScreenStatus.Error -> R.string.status_error
    }
    val buttonText = when (status) {
        ScreenStatus.PermissionRequired, ScreenStatus.PermissionDenied -> R.string.allow_camera
        ScreenStatus.Starting, ScreenStatus.Streaming -> R.string.stop_camera
        ScreenStatus.Unavailable, ScreenStatus.Error -> R.string.retry_camera
        ScreenStatus.Stopped -> R.string.start_camera
    }
    Scaffold(
        modifier = Modifier.semantics { isTraversalGroup = true },
        topBar = {
            Surface(tonalElevation = 3.dp, modifier = Modifier.testTag("primary-region").semantics {
                isTraversalGroup = true; traversalIndex = 0f
            }) {
                Column(Modifier.statusBarsPadding().fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically) {
                        Text("VisionAssist", style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f).semantics { heading() })
                        Text("PROTOTIP", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                    }
                    RoText(stringResource(statusText), Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                    Button(onPrimary, Modifier.fillMaxWidth().heightIn(min = 64.dp)) {
                        RoText(stringResource(buttonText))
                    }
                }
            }
        },
        bottomBar = {
            Column(Modifier.testTag("navigation-region").semantics { isTraversalGroup = true; traversalIndex = 2f }) {
            NavigationBar(modifier = Modifier.heightIn(min = navigationHeight), windowInsets = WindowInsets(0, 0, 0, 0)) {
                Destination.entries.forEach { page ->
                    NavigationBarItem(selected = page == destination, onClick = { destination = page },
                        icon = { DestinationIcon(page) }, label = {
                            Text(AnnotatedString(page.title, SpanStyle(localeList = LocaleList("ro-RO"))),
                                modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center)
                        }, alwaysShowLabel = true)
                }
            }
            Spacer(Modifier.fillMaxWidth().windowInsetsBottomHeight(WindowInsets.navigationBars).background(Color(0xFF101820)))
            }
        }
    ) { insets ->
        BoxWithConstraints(Modifier.fillMaxSize().padding(insets).testTag("content-region").semantics {
            isTraversalGroup = true; traversalIndex = 1f; paneTitle = destination.title
        }) {
            val cameraHeight = maxHeight * if (preferences.layout == InterfaceLayout.CameraFocused) .48f else .26f
            Column(Modifier.fillMaxSize()) {
                // Do not move this host into a destination branch, or change its size with destination.
                Box(Modifier.fillMaxWidth().height(cameraHeight).padding(16.dp, 10.dp)
                    .clip(RoundedCornerShape(24.dp)).background(Color.Black)
                    .clearAndSetSemantics {
                        if (destination == Destination.Home) contentDescription = "Previzualizarea camerei din spate. Rezultatele sunt disponibile în lista de obiecte."
                        else hideFromAccessibility()
                    }, contentAlignment = Alignment.Center) {
                    if (status != ScreenStatus.Streaming) Text(stringResource(R.string.preview_placeholder), color = Color.White)
                    preview(Modifier.fillMaxSize())
                    if (status == ScreenStatus.Streaming && (preferences.layout == InterfaceLayout.CameraFocused || preferences.developer)) {
                        DetectionOverlay(detectionState.result, Modifier.fillMaxSize(), showConfidence = preferences.developer)
                    }
                }
                if (destination == Destination.Home) {
                    Column(Modifier.fillMaxWidth().weight(1f).verticalScroll(rememberScrollState()).padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(18.dp)) {
                        RoText("Asistență locală", title = true)
                        SummaryCard { RoText(connectionSummary); RoText("Când este pornită, asistența locală continuă și pe celelalte ecrane. Se oprește în fundal.") }
                        if (status == ScreenStatus.PermissionRequired) RoText(stringResource(R.string.permission_body))
                        if (status == ScreenStatus.PermissionDenied || status == ScreenStatus.Error) {
                            RoText(stringResource(if (status == ScreenStatus.PermissionDenied) R.string.denied_body else R.string.error_body))
                            OutlinedButton(onSettings, Modifier.fillMaxWidth().heightIn(min = 56.dp)) { RoText(stringResource(R.string.open_settings)) }
                        }
                        DetectionPanel(detectionState, onRetryDetection, developer = preferences.developer)
                        if (preferences.developer) diagnostics()
                        RoText("Avertizări recente", title = true)
                        if (recentHazardWarnings.isEmpty()) RoText("Nu există avertizări recente. Detectoarele experimentale pentru sol sunt dezactivate până la validare.")
                        recentHazardWarnings.forEach { SummaryCard { RoText(it) } }
                        RoText("Anunțuri recente", title = true)
                        RoText("Recunoașteri anunțate de vocea locală; nu sunt pericole confirmate.")
                        if (recentAnnouncements.isEmpty()) RoText("Nu există anunțuri recente.")
                        recentAnnouncements.forEach { SummaryCard { RoText(it) } }
                        RoText(stringResource(R.string.active_body))
                        RoText(stringResource(R.string.safety_body))
                        TextButton(onHelp, Modifier.heightIn(min = 56.dp)) { RoText(stringResource(R.string.help_button)) }
                    }
                }
            }
            if (destination != Destination.Home) {
                Surface(Modifier.fillMaxSize()) {
                    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(20.dp)) {
                        if (destination == Destination.Voice) {
                            RoText("Asistent vocal · OpenAI / Gemini", title = true)
                            RoText("Conversație în română, prin internet.")
                            voiceControls()
                            if (preferences.developer) diagnostics()
                        } else {
                            RoText("Setări", title = true)
                            preferenceError?.let { RoText(it, Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
                            RoText("Aspectul interfeței", title = true)
                            LayoutOptions(preferences.layout, onLayout)
                            RoText("Temă", title = true)
                            Column(Modifier.selectableGroup()) {
                                ThemeChoice.entries.forEach { option ->
                                    Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).selectable(
                                        selected = preferences.theme == option, onClick = { onTheme(option) }, role = Role.RadioButton),
                                        verticalAlignment = Alignment.CenterVertically) {
                                        RadioButton(preferences.theme == option, onClick = null)
                                        RoText(option.title, Modifier.padding(start = 12.dp))
                                    }
                                }
                            }
                            Row(Modifier.fillMaxWidth().heightIn(min = 64.dp).toggleable(preferences.developer,
                                onValueChange = onDeveloper, role = Role.Switch), verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    RoText("Mod dezvoltator")
                                    Text("Chenare, scoruri, FPS analiză și latență măsurată.", style = MaterialTheme.typography.bodyMedium)
                                }
                                Switch(preferences.developer, onCheckedChange = null)
                            }
                            settingsControls()
                            if (preferences.developer) diagnostics()
                            TextButton(onSettings, Modifier.fillMaxWidth().heightIn(min = 56.dp)) { RoText(stringResource(R.string.open_settings)) }
                            TextButton(onHelp, Modifier.fillMaxWidth().heightIn(min = 56.dp)) { RoText(stringResource(R.string.help_button)) }
                            RoText(stringResource(R.string.privacy_label))
                            RoText(stringResource(R.string.safety_body))
                        }
                    }
                }
            }
        }
    }
    if (showHelp) AlertDialog(onDismissHelp, title = { RoText(stringResource(R.string.help_title)) },
        text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            RoText(stringResource(R.string.help_body)); RoText(stringResource(R.string.safety_body))
        } }, confirmButton = { TextButton(onDismissHelp, Modifier.heightIn(min = 56.dp)) { RoText(stringResource(R.string.close_help)) } })
}

@Composable
private fun SummaryCard(content: @Composable ColumnScope.() -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
    }
}

@Composable
private fun DestinationIcon(page: Destination) {
    val color = MaterialTheme.colorScheme.onSurface
    Canvas(Modifier.size(24.dp).clearAndSetSemantics {}) {
        val w = size.width; val h = size.height; val stroke = Stroke(2.dp.toPx())
        when (page) {
            Destination.Home -> {
                val path = Path().apply { moveTo(w*.1f,h*.45f); lineTo(w*.5f,h*.12f); lineTo(w*.9f,h*.45f)
                    moveTo(w*.22f,h*.4f); lineTo(w*.22f,h*.88f); lineTo(w*.78f,h*.88f); lineTo(w*.78f,h*.4f) }
                drawPath(path,color,style=stroke)
            }
            Destination.Voice -> {
                drawRoundRect(color, Offset(w*.3f,h*.08f), androidx.compose.ui.geometry.Size(w*.4f,h*.57f),
                    androidx.compose.ui.geometry.CornerRadius(w*.2f), style=stroke)
                drawArc(color,0f,180f,false, Offset(w*.12f,h*.3f), androidx.compose.ui.geometry.Size(w*.76f,h*.48f), style=stroke)
                drawLine(color,Offset(w*.5f,h*.78f),Offset(w*.5f,h*.95f),2.dp.toPx())
            }
            Destination.Settings -> {
                drawCircle(color,w*.35f,style=stroke); drawCircle(color,w*.12f,style=stroke)
                repeat(8) { i ->
                    val a = i*Math.PI/4; drawLine(color,Offset(w*.5f+ kotlin.math.cos(a).toFloat()*w*.35f,h*.5f+kotlin.math.sin(a).toFloat()*h*.35f),
                        Offset(w*.5f+kotlin.math.cos(a).toFloat()*w*.47f,h*.5f+kotlin.math.sin(a).toFloat()*h*.47f),2.dp.toPx())
                }
            }
        }
    }
}
