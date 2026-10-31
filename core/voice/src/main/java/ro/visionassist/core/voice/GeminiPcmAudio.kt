package ro.visionassist.core.voice

import android.annotation.SuppressLint
import android.media.*
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import kotlinx.coroutines.*
import java.util.ArrayDeque

/** Raw mono PCM: 16 kHz input, 24 kHz output. All device operations share a short lock.
 * Non-blocking IO permits synchronous flush/close before a local warning starts.
 */
internal class GeminiPcmAudio(
    private val scope: CoroutineScope,
    private val onInput: (ByteArray) -> Unit,
    private val onPlaying: (Boolean) -> Unit,
    private val onFailure: () -> Unit
) : AutoCloseable {
    private val lock = Any()
    private var recording: AudioRecord? = null
    private var playback: AudioTrack? = null
    private var echo: AcousticEchoCanceler? = null
    private var noise: NoiseSuppressor? = null
    private var reader: Job? = null
    private var writer: Job? = null
    private val queue = ArrayDeque<ByteArray>()
    private var queuedBytes = 0
    private var active = false
    private var epoch = 0
    private var writtenFrames = 0L
    private var speaking = false
    internal val isCapturing: Boolean get() = synchronized(lock) {
        active && recording?.recordingState == AudioRecord.RECORDSTATE_RECORDING
    }

    @SuppressLint("MissingPermission") // Checked by GeminiVoiceClient immediately before opening.
    fun start() = synchronized(lock) {
        check(!active)
        try {
            val inputSize = AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            val outputSize = AudioTrack.getMinBufferSize(24000, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
            check(inputSize > 0 && outputSize > 0)
            recording = AudioRecord.Builder().setAudioSource(MediaRecorder.AudioSource.VOICE_COMMUNICATION)
                .setAudioFormat(AudioFormat.Builder().setSampleRate(16000).setChannelMask(AudioFormat.CHANNEL_IN_MONO)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                .setBufferSizeInBytes(maxOf(inputSize, 6400)).build()
            playback = AudioTrack.Builder().setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                .setAudioFormat(AudioFormat.Builder().setSampleRate(24000).setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                .setTransferMode(AudioTrack.MODE_STREAM).setBufferSizeInBytes(maxOf(outputSize, 9600)).build()
            check(recording!!.state == AudioRecord.STATE_INITIALIZED && playback!!.state == AudioTrack.STATE_INITIALIZED)
            if (AcousticEchoCanceler.isAvailable()) echo = AcousticEchoCanceler.create(recording!!.audioSessionId)?.apply { enabled = true }
            if (NoiseSuppressor.isAvailable()) noise = NoiseSuppressor.create(recording!!.audioSessionId)?.apply { enabled = true }
            recording!!.startRecording(); check(recording!!.recordingState == AudioRecord.RECORDSTATE_RECORDING)
            playback!!.play(); active = true
            reader = scope.launch(Dispatchers.IO) {
                try {
                    val buffer = ByteArray(640) // 20 ms; do not accumulate microphone recordings.
                    while (isActive) {
                        synchronized(lock) {
                            if (!active) return@launch
                            val count = recording!!.read(buffer, 0, buffer.size, AudioRecord.READ_NON_BLOCKING)
                            check(count >= 0)
                            if (count > 0) onInput(buffer.copyOf(count))
                        }
                        delay(10)
                    }
                } catch (cancelled: CancellationException) { throw cancelled }
                catch (_: Exception) { onFailure() }
            }
            writer = scope.launch(Dispatchers.IO) {
                try {
                    var chunk: ByteArray? = null; var offset = 0; var chunkEpoch = epoch
                    while (isActive) {
                        synchronized(lock) {
                            if (!active) return@launch
                            if (chunkEpoch != epoch) { chunk = null; offset = 0; chunkEpoch = epoch }
                            if (chunk == null && queue.isNotEmpty()) { chunk = queue.removeFirst(); queuedBytes -= chunk!!.size; offset = 0 }
                            chunk?.let {
                                val count = playback!!.write(it, offset, it.size - offset, AudioTrack.WRITE_NON_BLOCKING)
                                check(count >= 0)
                                offset += count; writtenFrames += count / 2
                                if (count > 0 && !speaking) { speaking = true; onPlaying(true) }
                                if (offset == it.size) chunk = null
                            }
                            val played = playback!!.playbackHeadPosition.toLong() and 0xffffffffL
                            if (speaking && chunk == null && queue.isEmpty() && played >= writtenFrames) {
                                speaking = false; onPlaying(false)
                            }
                        }
                        delay(5)
                    }
                } catch (cancelled: CancellationException) { throw cancelled }
                catch (_: Exception) { onFailure() }
            }
        } catch (failure: Exception) { close(); throw failure }
    }

    fun enqueue(bytes: ByteArray): Boolean = synchronized(lock) {
        // At most 20 seconds of pending PCM, regardless of how fast the server generates it.
        if (!active || bytes.isEmpty() || bytes.size % 2 != 0 || bytes.size + queuedBytes > 960_000) return false
        queue.addLast(bytes); queuedBytes += bytes.size; true
    }
    fun interrupt() = synchronized(lock) {
        epoch++; queue.clear(); queuedBytes = 0; writtenFrames = 0
        playback?.let { it.pause(); it.flush(); it.play() }
        if (speaking) { speaking = false; onPlaying(false) }
    }
    override fun close() = synchronized(lock) {
        active = false; epoch++; reader?.cancel(); writer?.cancel(); reader = null; writer = null
        queue.clear(); queuedBytes = 0; writtenFrames = 0; speaking = false
        playback?.let { runCatching { it.setVolume(0f); it.pause(); it.flush() }; it.release() }; playback = null
        recording?.let { runCatching { it.stop() }; it.release() }; recording = null
        echo?.release(); echo = null; noise?.release(); noise = null
    }
}
