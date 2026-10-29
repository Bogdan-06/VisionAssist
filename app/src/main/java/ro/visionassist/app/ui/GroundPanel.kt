package ro.visionassist.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.intl.LocaleList
import androidx.compose.ui.unit.dp
import ro.visionassist.core.ground.GroundMetrics
import kotlin.math.roundToInt

@Composable
fun GroundPanel(enabled: Boolean, state: DetectionUiState, metrics: GroundMetrics?, onToggle: () -> Unit,
                onDepth: () -> Unit = {}) {
    fun ro(text: String) = AnnotatedString(text, SpanStyle(localeList = LocaleList("ro-RO")))
    Column {
        Text(ro("Gropi · model experimental"), Modifier.semantics { heading() })
        Text(ro("Analiza rulează pe telefon. Modelul poate rata gropi și poate confunda alte suprafețe cu gropi. Nu detectează borduri, trepte sau denivelări generale."))
        Text(ro("Detectorul experimental este dezactivat până la validare. Avertizările pentru gropi nu sunt disponibile."))
        OutlinedButton(onClick=onToggle, enabled=false, modifier=Modifier.fillMaxWidth().heightIn(min=56.dp)) {
            Text(ro("Analiză experimentală indisponibilă"))
        }
        OutlinedButton(onClick=onDepth, modifier=Modifier.fillMaxWidth().heightIn(min=56.dp)) {
            Text(ro("Deschide experimentul de adâncime"))
        }
        if (enabled) {
            Text(ro(when(state.phase) {
                DetectionPhase.Idle -> "Pornește camera pentru analiză."
                DetectionPhase.Loading -> "Se încarcă modelul local de gropi…"
                DetectionPhase.Error -> "Analiza gropilor nu este disponibilă. Oprește și repornește analiza pentru a reîncerca."
                DetectionPhase.Stale -> "Nu există rezultate recente pentru gropi."
                DetectionPhase.Active -> if (state.result?.objects.isNullOrEmpty()) "Nicio posibilă groapă identificată în ultimul cadru. Aceasta nu confirmă un traseu sigur."
                    else "Posibile gropi în imagine: ${state.result?.objects?.size}."
            }))
            state.result?.objects?.take(5)?.forEach { obj ->
                val direction = when(obj.bounds.direction) {
                    ro.visionassist.core.detection.Direction.Left -> "în stânga imaginii"
                    ro.visionassist.core.detection.Direction.Center -> "în centrul imaginii"
                    ro.visionassist.core.detection.Direction.Right -> "în dreapta imaginii"
                }
                Text(ro("Posibilă groapă $direction. Scor model ${(obj.confidence*100).roundToInt()} din 100; nu este o probabilitate de pericol. Distanță necunoscută."))
            }
            Text(ro("Avertismentele pentru gropi sunt indisponibile: precizia modelului nu a trecut evaluarea."))
            metrics?.let { Text(ro("Ultima inferență: ${it.inferenceMs} milisecunde. Cadre analizate: ${it.processed}.")) }
        }
    }
}
