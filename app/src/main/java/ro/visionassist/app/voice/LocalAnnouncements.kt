package ro.visionassist.app.voice

import android.content.Context
import android.media.AudioAttributes
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import ro.visionassist.app.ui.DetectionLabels
import ro.visionassist.core.detection.DetectionPolicy
import ro.visionassist.core.detection.DetectionResult
import ro.visionassist.core.voice.VoiceClient
import ro.visionassist.core.ground.GroundBox
import ro.visionassist.core.ground.GroundCandidate
import ro.visionassist.core.ground.GroundWarningPolicy
import ro.visionassist.core.ground.GroundModelReadiness
import java.util.Locale
import java.util.UUID

/** Factual recognition announcements, not danger or distance inference. All outrank AI audio. */
class LocalAnnouncements(context: Context, private val voice: VoiceClient) : AutoCloseable {
    private val main = Handler(Looper.getMainLooper())
    private var closed = false
    private var activeId: String? = null
    private var groundSpeaking = false
    private val groundPolicy = GroundWarningPolicy()
    private val vibrator = context.getSystemService(Vibrator::class.java)
    private var lastAt = Long.MIN_VALUE
    private var lastLabel: String? = null
    private val mutableStatus = MutableStateFlow("Se verifică vocea română offline…")
    val status = mutableStatus.asStateFlow()
    private val mutableRecent = MutableStateFlow<List<String>>(emptyList())
    val recent = mutableRecent.asStateFlow()
    private val mutableHazards = MutableStateFlow<List<String>>(emptyList())
    val recentHazards = mutableHazards.asStateFlow()
    private var ready = false
    val isReady get() = ready && !closed
    var enabled = false
        set(value) { field = value; if (!value) stop() }
    private val tts = TextToSpeech(context.applicationContext) { result -> main.post { initialize(result) } }

    private fun initialize(result: Int) {
        if (closed) return
        val local = if (result == TextToSpeech.SUCCESS) tts.voices?.firstOrNull {
            it.locale.language == "ro" && !it.isNetworkConnectionRequired
        } else null
        if (local == null) { mutableStatus.value = "Instalează o voce română offline în setările de sinteză vocală Android."; return }
        if (tts.setLanguage(Locale.forLanguageTag("ro-RO")) < TextToSpeech.LANG_AVAILABLE ||
            tts.setVoice(local) != TextToSpeech.SUCCESS) {
            mutableStatus.value = "Vocea română offline nu a putut fi activată. Verifică setările de sinteză vocală Android."
            return
        }
        tts.setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String) = Unit
            override fun onDone(id: String) { main.post { finish(id) } }
            @Deprecated("Android callback") override fun onError(id: String) { main.post { finish(id) } }
            @Deprecated("Android callback") override fun onError(id: String, errorCode: Int) { main.post { finish(id); mutableStatus.value = "Vocea locală nu a putut reda anunțul." } }
            @Deprecated("Android callback") override fun onStop(id: String, interrupted: Boolean) { main.post { finish(id) } }
        })
        ready = true; mutableStatus.value = "Vocea română offline este disponibilă. Anunțurile pot greși; nu indică un traseu sigur."
    }
    fun observe(result: DetectionResult) {
        if (!enabled || !ready || closed || activeId != null || !DetectionPolicy.isFresh(result.receivedAtMs, SystemClock.elapsedRealtime())) return
        val obj = result.objects.filter { it.confidence >= 0.7f }.maxByOrNull { it.confidence } ?: return
        val now = SystemClock.elapsedRealtime()
        val label = obj.label + obj.bounds.direction.name
        if (lastAt != Long.MIN_VALUE && now - lastAt < if (lastLabel == label) 12_000 else 5_000) return
        lastAt = now; lastLabel = label
        speak("Obiect recunoscut: ${DetectionLabels.description(obj)}.")
    }
    fun resetGround() { groundPolicy.reset() }
    fun observeGround(result: DetectionResult) {
        // Keep production speech gated until measured model quality justifies warnings.
        if (!GroundModelReadiness.WARNINGS_VALIDATED || !enabled || closed) return
        val candidates = result.objects.filter { it.label == "pothole" }.map {
            GroundCandidate(it.confidence,GroundBox(it.bounds.left,it.bounds.top,it.bounds.right,it.bounds.bottom))
        }
        groundPolicy.observe(candidates,result.receivedAtMs,SystemClock.elapsedRealtime()) ?: return
        if (ready) speak("Atenție, posibilă groapă în imaginea din față. Distanță necunoscută.", ground = true)
        else {
            stop()
            val id = UUID.randomUUID().toString(); activeId = id; groundSpeaking = true
            voice.beginLocalWarning(id)
            main.postDelayed({ finish(id) },700)
        }
        if (vibrator?.hasVibrator() == true) vibrator.vibrate(VibrationEffect.createWaveform(longArrayOf(0,100,80,180),-1))
    }
    fun testVoice() { if (ready && !closed && !groundSpeaking) speak("Acesta este un test al vocii locale. Nu este un avertisment despre mediul din jur.", record = false) }
    private fun speak(text: String, ground: Boolean = false, record: Boolean = true) {
        // Acquire the new interruption before releasing the old one: no AI audio gap
        // when a ground warning preempts a lower-priority object announcement.
        val previous = activeId
        val id = UUID.randomUUID().toString()
        voice.beginLocalWarning(id)
        tts.stop(); vibrator?.cancel()
        activeId = id; groundSpeaking = ground
        previous?.let { voice.endLocalWarning(it) }
        if (tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, id) == TextToSpeech.ERROR) finish(id)
        else if (record) {
            val history = if (ground) mutableHazards else mutableRecent
            history.value = (listOf(text) + history.value).take(5)
        }
        // A broken engine must never leave the microphone/AI permanently muted.
        main.postDelayed({ if (activeId == id) { tts.stop(); finish(id) } }, 8_000)
    }
    private fun finish(id: String) { voice.endLocalWarning(id); if (activeId == id) { activeId = null; groundSpeaking = false } }
    fun stop() { tts.stop(); vibrator?.cancel(); activeId?.let { finish(it) } }
    override fun close() { if (!closed) { closed = true; stop(); main.removeCallbacksAndMessages(null); tts.shutdown() } }
}
