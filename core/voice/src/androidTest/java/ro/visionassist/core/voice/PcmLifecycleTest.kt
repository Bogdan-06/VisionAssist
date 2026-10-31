package ro.visionassist.core.voice

import android.Manifest
import android.content.pm.PackageManager
import androidx.test.filters.SdkSuppress
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicBoolean

/** Real native microphone on the explicitly selected emulator. No socket or saved audio. */
class PcmLifecycleTest {
    @Test @SdkSuppress(minSdkVersion = 28)
    fun nativeCaptureCanCloseDuringInputAndRestartWithoutRetainingPlayback() = runBlocking {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        instrumentation.uiAutomation.grantRuntimePermission(context.packageName, Manifest.permission.RECORD_AUDIO)
        assertEquals(PackageManager.PERMISSION_GRANTED, context.checkSelfPermission(Manifest.permission.RECORD_AUDIO))
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        val inputs = AtomicInteger()
        val failed = AtomicBoolean()
        val audio = GeminiPcmAudio(scope, { inputs.incrementAndGet() }, {}, { failed.set(true) })
        try {
            repeat(2) {
                val before = inputs.get()
                audio.start()
                assertTrue(audio.isCapturing)
                withTimeout(5_000) { while (inputs.get() == before && !failed.get()) delay(20) }
                assertFalse(failed.get())
                assertTrue(audio.enqueue(ByteArray(960))) // Silence; no spoken content.
                audio.interrupt()
                audio.close(); audio.close()
                assertFalse(audio.isCapturing)
                assertFalse(audio.enqueue(ByteArray(960)))
                val after = inputs.get()
                delay(50)
                assertEquals(after, inputs.get())
            }
        } finally { audio.close(); scope.cancel() }
    }
}
