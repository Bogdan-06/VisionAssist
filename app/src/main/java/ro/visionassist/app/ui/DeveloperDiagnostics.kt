package ro.visionassist.app.ui

import android.os.SystemClock
import android.os.Debug
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ro.visionassist.core.voice.VoiceState
import java.util.Locale

/** Composed only in Developer Mode. No disk/network, image retention or frequent accessibility events. */
@Composable
fun DeveloperDiagnostics(state: DetectionUiState, camera: ScreenStatus, foreground: Boolean, voice: VoiceState) {
    var now by remember { mutableLongStateOf(SystemClock.elapsedRealtime()) }
    var heapBytes by remember { mutableStateOf<Long?>(null) }
    var pssKb by remember { mutableStateOf<Long?>(null) }
    LaunchedEffect(foreground) {
        if (!foreground) { heapBytes = null; pssKb = null; return@LaunchedEffect }
        var tick = 0
        while (true) {
            now = SystemClock.elapsedRealtime()
            val runtime = Runtime.getRuntime()
            heapBytes = runtime.totalMemory() - runtime.freeMemory()
            if (tick++ % 5 == 0) pssKb = withContext(Dispatchers.Default) {
                runCatching { Debug.getPss().takeIf { it > 0 } }.getOrNull()
            }
            delay(1_000)
        }
    }
    val stats = state.diagnostics
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        RoText("Diagnostic dezvoltator", Modifier.semantics { heading() })
        RoText("Cameră: ${camera.name}; analiză: ${state.phase.name}; aplicație: ${if (foreground) "în prim-plan" else "în fundal"}.")
        RoText(stats.fps?.let { "FPS analiză: %.1f cadre/s".format(Locale.ROOT, it) } ?: "FPS analiză: indisponibil până la două rezultate recente.")
        RoText(if (stats.samples == 0) "Inferență: nu există eșantioane recente."
            else "Apel MediaPipe detect: mediană ${stats.medianMs} ms; p95 ${stats.p95Ms} ms; ${stats.samples} eșantioane (maximum 60).")
        val currentTime = maxOf(now, SystemClock.elapsedRealtime())
        val age = state.result?.receivedAtMs?.let { if (currentTime >= it) currentTime - it else null }
        RoText(age?.let { "Vârsta rezultatului de la primirea în analyzer: $it ms." } ?: "Vârsta rezultatului: indisponibilă.")
        RoText(heapBytes?.let { "Heap Java utilizat: %.1f MiB. Nu include întreaga memorie nativă/GPU și nu reprezintă PSS.".format(Locale.ROOT, it / 1048576.0) }
            ?: "Heap Java: se așteaptă măsurarea.")
        RoText(pssKb?.let { "PSS proces: %.1f MiB (eșantion la 5 secunde, include runtime și biblioteci native).".format(Locale.ROOT, it / 1024.0) }
            ?: "PSS proces: măsurare indisponibilă sau în curs.")
        RoText("Microfon: ${if (voice.microphoneCapturing) "captură nativă pornită" else "captură nativă oprită"}; transmisie: ${if (voice.microphoneMuted) "blocată" else "permisă"}; sesiune: ${voice.phase.name}.")
        RoText("FPS-ul este rata rezultatelor analizate, nu rata senzorului. Durata detect include pre/postprocesarea MediaPipe, fără captură și conversia CameraX. Verifică separat indicatorul Android de microfon.")
    }
}
