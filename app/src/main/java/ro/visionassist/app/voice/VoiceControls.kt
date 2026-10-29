package ro.visionassist.app.voice

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.intl.LocaleList
import androidx.compose.ui.unit.dp
import androidx.core.net.toUri
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch
import ro.visionassist.app.BuildConfig
import ro.visionassist.core.camera.CameraSnapshotRequest
import ro.visionassist.core.voice.*

@Composable private fun Ro(text: String, modifier: Modifier = Modifier) {
    Text(AnnotatedString(text, SpanStyle(localeList = LocaleList("ro-RO"))), modifier = modifier)
}

@Composable
fun VoiceControls(client: VoiceClient, announcements: LocalAnnouncements,
                  snapshots: CameraSnapshotRequest, cameraActive: Boolean, foreground: Boolean,
                  showConversation: Boolean = true, showLocal: Boolean = true,
                  localEnabled: Boolean = announcements.enabled,
                  onLocalEnabledChange: (Boolean) -> Unit = { announcements.enabled = it },
                  settingsStore: BackendSettingsStore? = null) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val state by client.state.collectAsStateWithLifecycle()
    val localStatus by announcements.status.collectAsStateWithLifecycle()
    val store = remember(context, settingsStore) { settingsStore ?: BackendSettingsStore(context) }
    var loaded by remember(store) { mutableStateOf(store.load()) }
    val settings = (loaded as? BackendSettingsLoadResult.Available)?.settings ?: BackendSettings("", "", VoiceProvider.Gemini)
    var showSettings by remember { mutableStateOf(false) }
    var permissionDenied by remember { mutableStateOf(false) }
    var startWhenResumed by remember { mutableStateOf(false) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        permissionDenied = !granted; startWhenResumed = granted
    }
    LaunchedEffect(startWhenResumed, foreground) {
        if (startWhenResumed && foreground) { startWhenResumed = false; client.start(settings) }
    }
    val running = state.phase in setOf(VoicePhase.Connecting, VoicePhase.Listening, VoicePhase.Speaking)
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (loaded == BackendSettingsLoadResult.Unreadable) {
            Ro("Configurația vocală salvată nu a putut fi citită. Datele nu au fost șterse. Reintrodu adresa și codul de acces în configurarea serverului.",
                Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        }
        if (showConversation) {
        Ro("Asistent vocal în română", Modifier.semantics { heading() })
        val phase = when (state.phase) {
            VoicePhase.Disconnected -> "Deconectat"
            VoicePhase.Connecting -> "Se conectează"
            VoicePhase.Listening -> "Ascultă"
            VoicePhase.Speaking -> "Vorbește"
            VoicePhase.Error -> "Eroare de conexiune"
        }
        Ro(if (state.warningActive) "$phase. Anunțul local are prioritate; microfonul și asistentul sunt dezactivate temporar." else phase,
            Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        Ro(state.message)
        Ro(if (loaded == BackendSettingsLoadResult.Unreadable) "Reconfigurează furnizorul vocal înainte de a porni conversația."
            else "Pornirea trimite vocea către ${settings.provider.label}. Fotografiile necesită confirmarea ta.")
        Button(onClick = {
            if (running) { startWhenResumed = false; client.stop() }
            else if (settings.url.isBlank() || settings.accessToken.isBlank()) showSettings = true
            else if (context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) client.start(settings)
            else launcher.launch(Manifest.permission.RECORD_AUDIO)
        }, enabled = running || !state.warningActive, modifier = Modifier.fillMaxWidth().heightIn(min = 64.dp)) {
            Ro(if (running) "Oprește conversația AI" else "Pornește conversația AI")
        }
        Ro("Oprirea conversației sau ieșirea din aplicație închide microfonul.")
        if (settings.provider == VoiceProvider.Gemini) Ro("Gemini are o cotă gratuită limitată. Un anunț local oprește conversația Gemini; o poți reporni după anunț.")
        if (permissionDenied) {
            Ro("Microfonul nu este permis. Camera și recunoașterea locală pot continua.")
            OutlinedButton(onClick = { context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, "package:${context.packageName}".toUri())) },
                modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) { Ro("Setări pentru microfon") }
        }
        val canSend = state.phase in setOf(VoicePhase.Listening, VoicePhase.Speaking) && cameraActive && !state.warningActive && !state.imageBusy
        if (state.imageRequested) Ro("Asistentul solicită o fotografie. Apasă butonul de mai jos doar dacă dorești să o trimiți.", Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        OutlinedButton(onClick = { scope.launch { client.sendRequestedImage { snapshots.capture() } } }, enabled = canSend,
            modifier = Modifier.fillMaxWidth().heightIn(min = 64.dp)) {
            Ro(if (state.imageBusy) "Se pregătește fotografia…" else "Ce este în fața mea? Trimite o fotografie")
        }
        if (state.imageRequested || state.imageBusy) TextButton(onClick = { client.declineImage() }, modifier = Modifier.heightIn(min = 56.dp)) { Ro("Nu trimite fotografia") }
        if (!cameraActive) Ro("Pornește camera pentru a putea trimite o fotografie nouă.")
        }
        if (!showConversation) Ro(if (loaded == BackendSettingsLoadResult.Unreadable) "Furnizorul vocal nu poate fi citit din configurația salvată."
            else "Furnizor vocal: ${settings.provider.label}. Oprește conversația pentru a modifica serverul.")
        OutlinedButton(onClick = { showSettings = true }, enabled = !running,
            modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) { Ro("Configurarea serverului vocal") }
        if (showLocal) {
        Ro("Anunțuri locale", Modifier.semantics { heading() })
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Ro("Anunță obiectele recunoscute", Modifier.weight(1f))
            Switch(checked = localEnabled, onCheckedChange = onLocalEnabledChange,
                modifier = Modifier.semantics { contentDescription = "Anunțuri locale despre obiecte" })
        }
        Ro(localStatus)
        OutlinedButton(onClick = announcements::testVoice, enabled = announcements.isReady, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) { Ro("Testează vocea locală și prioritatea audio") }
        Ro("Anunțurile descriu recunoașterea modelului, nu pericole confirmate. Nu sunt estimate distanțe.")
        }
    }
    if (showSettings) {
        var url by remember { mutableStateOf(settings.url) }
        var token by remember { mutableStateOf(settings.accessToken) }
        var provider by remember { mutableStateOf(settings.provider) }
        var error by remember { mutableStateOf<String?>(null) }
        AlertDialog(onDismissRequest = { showSettings = false }, title = { Ro("Serverul VisionAssist") }, text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Ro("Alege furnizorul. Cheile Google și OpenAI rămân exclusiv pe server. Introdu adresa serverului și codul său privat de acces.")
                Column(Modifier.selectableGroup()) {
                    VoiceProvider.entries.forEach { option ->
                        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).selectable(
                            selected = provider == option, onClick = { provider = option }, role = Role.RadioButton)) {
                            RadioButton(selected = provider == option, onClick = null)
                            Ro(option.label, Modifier.padding(12.dp))
                        }
                    }
                }
                OutlinedTextField(value = url, onValueChange = { url = it }, label = { Ro("Adresa HTTPS a serverului") }, singleLine = true)
                OutlinedTextField(value = token, onValueChange = { token = it }, label = { Ro("Cod de acces al serverului") },
                    visualTransformation = PasswordVisualTransformation(), singleLine = true)
                error?.let { Ro(it, Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
            }
        }, confirmButton = {
            TextButton(onClick = {
                val value = BackendSettings(url.trim(), token.trim(), provider)
                try { value.validate(BuildConfig.DEBUG) }
                catch (_: Exception) {
                    error = "Verifică adresa și codul de acces (minimum 32 de caractere). Cheile Google și OpenAI nu sunt acceptate aici."
                    return@TextButton
                }
                try {
                    store.save(value); loaded = BackendSettingsLoadResult.Available(value); showSettings = false
                } catch (_: Exception) { error = "Configurația vocală nu a putut fi salvată. Încearcă din nou. Datele de acces nu sunt afișate." }
            }, modifier = Modifier.heightIn(min = 56.dp)) { Ro("Salvează") }
        }, dismissButton = { TextButton(onClick = { showSettings = false }, modifier = Modifier.heightIn(min = 56.dp)) { Ro("Anulează") } })
    }
}
