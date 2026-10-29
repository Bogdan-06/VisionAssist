package ro.visionassist.app.depth

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.SystemClock
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ro.visionassist.app.ui.UiPreferencesViewModel
import ro.visionassist.app.ui.ThemeChoice
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.intl.LocaleList
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.ar.core.ArCoreApk
import com.google.ar.core.Config
import com.google.ar.core.Session
import ro.visionassist.app.ui.VisionAssistTheme
import ro.visionassist.core.depth.DepthCameraView
import ro.visionassist.core.depth.DepthProbeResult
import java.util.Locale
import java.util.concurrent.Executors

/** Optional isolated mode: MainActivity's CameraX and conversational microphone are paused. */
class DepthActivity:ComponentActivity() {
    private lateinit var cameraView:DepthCameraView
    private var session:Session?=null
    private var running=false
    private var resumed=false
    private var installRequested=false
    private var status by mutableStateOf("Se verifică suportul ARCore Depth…")
    private var result by mutableStateOf<DepthProbeResult?>(null)
    private val permission=registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted && resumed) startDepth() else status="Camera este necesară pentru măsurători. Camera obișnuită rămâne disponibilă la întoarcere."
    }

    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        cameraView=DepthCameraView(this,onResult={ value -> runOnUiThread {
            if (running && SystemClock.elapsedRealtime()-value.receivedAtMs < 1_000) {
                result=value
                status=if(value.hasFreshDepth) "Date de adâncime disponibile pentru acest cadru." else "Nu există măsurători recente. Distanță necunoscută."
                cameraView.postDelayed({ if (result===value) result=null },1_000)
            }
        } },onStatus={ message -> runOnUiThread { if(running) { status=message; result=null } } })
        fun ro(text:String)=AnnotatedString(text,SpanStyle(localeList=LocaleList("ro-RO")))
        setContent {
            val preferences: UiPreferencesViewModel = viewModel()
            val settings by preferences.state.collectAsStateWithLifecycle()
            val dark = when(settings.value?.theme) {
                ThemeChoice.Dark -> true
                ThemeChoice.Light -> false
                else -> isSystemInDarkTheme()
            }
            VisionAssistTheme(dark) { Scaffold { insets ->
            Column(Modifier.padding(insets).verticalScroll(rememberScrollState()).padding(24.dp),
                verticalArrangement=Arrangement.spacedBy(16.dp)) {
                Text(ro("Adâncime · experiment"),style=MaterialTheme.typography.headlineMedium,modifier=Modifier.semantics { heading() })
                Text(ro("Camera obișnuită și conversația sunt oprite în acest mod. Măsurătorile nu indică un traseu sigur. Folosește acest experiment numai staționar."))
                Text(ro(status))
                Button(onClick={ finish() },modifier=Modifier.fillMaxWidth().heightIn(min=64.dp)) { Text(ro("Înapoi la VisionAssist")) }
                Button(onClick={
                    if(ContextCompat.checkSelfPermission(this@DepthActivity,Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED)
                        permission.launch(Manifest.permission.CAMERA)
                    else { pauseDepth(); startDepth() }
                },modifier=Modifier.fillMaxWidth().heightIn(min=56.dp)) { Text(ro("Reîncearcă măsurarea")) }
                AndroidView(factory={cameraView},modifier=Modifier.fillMaxWidth().height(240.dp))
                val current=result
                if(current==null) Text(ro("Nu există rezultate recente."))
                else {
                    val center=current.centerDepth
                    Text(ro(if(center==null) "Suprafața centrală: distanță necunoscută. Măsurători insuficiente sau neuniforme."
                        else "Suprafața centrală: aproximativ ${String.format(Locale.forLanguageTag("ro-RO"),"%.2f",center.medianMeters)} metri față de planul camerei. Aceasta este o măsurătoare de suprafață, nu o detectare de pericol sau o distanță de mers."))
                    Text(ro("Detectorul experimental de gropi este dezactivat. Sunt disponibile doar măsurători de suprafață, fără evaluarea siguranței traseului."))
                    current.candidates.take(5).forEach { candidate ->
                        val depth=candidate.regionDepth
                        Text(ro(if(depth==null) "Posibilă groapă. Distanță necunoscută: măsurători insuficiente sau neuniforme."
                            else "Posibilă groapă. Adâncimea mediană a suprafeței din regiune: aproximativ ${String.format(Locale.forLanguageTag("ro-RO"),"%.1f",depth.medianMeters)} metri față de planul camerei. Nu este distanța de mers sau adâncimea gropii."))
                    }
                    current.diagnostic?.let {
                        Text(ro("Diagnostic de suprafață: ${it.abruptPairs} salturi de adâncime din ${it.validPairs} perechi valide. Marginile obiectelor și perspectiva pot produce aceste salturi; nu confirmă trepte sau borduri."))
                    }
                }
                Text(ro("Modelul de gropi are precizie insuficientă; avertismentele sunt dezactivate. Nu sunt detectate borduri, trepte sau denivelări generale."))
            }
        } } }
    }

    override fun onResume() { super.onResume(); resumed=true; startDepth() }

    private fun startDepth() {
        if(running || !resumed) return
        if(ContextCompat.checkSelfPermission(this,Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED) {
            status="Permite accesul la cameră folosind butonul Reîncearcă măsurarea."; return
        }
        try {
            val availability=ArCoreApk.getInstance().checkAvailability(this)
            if(availability.isTransient) {
                status="Se verifică disponibilitatea ARCore…"
                cameraView.postDelayed({ if(resumed) startDepth() },1_000); return
            }
            if(!availability.isSupported) { status="ARCore nu este disponibil pe acest dispozitiv. Folosește camera obișnuită fără distanțe."; return }
            if(ArCoreApk.getInstance().requestInstall(this,!installRequested)==ArCoreApk.InstallStatus.INSTALL_REQUESTED) {
                installRequested=true; status="Instalează sau actualizează Google Play Services for AR pentru acest mod opțional."; return
            }
            val active=session ?: Session(this).also { session=it }
            if(!active.isDepthModeSupported(Config.DepthMode.RAW_DEPTH_ONLY)) {
                status="ARCore Depth nu este acceptat. Camera obișnuită funcționează fără măsurători de distanță."; return
            }
            active.configure(active.config.apply { depthMode=Config.DepthMode.RAW_DEPTH_ONLY; focusMode=Config.FocusMode.AUTO })
            active.resume(); cameraView.arSession=active; running=true; cameraView.onResume()
            status="Se așteaptă urmărirea și datele reale de adâncime. Distanță necunoscută."
        } catch (_: Exception) {
            status="Modul de adâncime nu a pornit. Reîncearcă sau revino la camera obișnuită."
        }
    }

    private fun pauseDepth() {
        running=false; result=null
        cameraView.onPause(); cameraView.arSession=null
        try { session?.pause() } catch (_: Exception) { /* No active camera remains usable here. */ }
    }
    override fun onPause() { resumed=false; pauseDepth(); super.onPause() }
    override fun onDestroy() {
        cameraView.close()
        val old=session; session=null
        Executors.newSingleThreadExecutor().apply { execute { old?.close() }; shutdown() }
        super.onDestroy()
    }
}
