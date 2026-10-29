package ro.visionassist.app.voice

import android.Manifest
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.AudioManager
import androidx.compose.material3.Text
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.rule.GrantPermissionRule
import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import ro.visionassist.core.voice.BackendSettings
import ro.visionassist.core.voice.SelectableVoiceClient
import ro.visionassist.core.voice.VoiceProvider
import ro.visionassist.core.voice.VoicePhase
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean

/** Opt-in integration test. Calls the real API; never runs in the offline/default suite.
 * Only a separate backend access token is provided in app-private live-test.json.
 * Uploads the public cats-and-dogs fixture, not any personal camera image.
 */
class LiveRealtimeTest {
    @get:Rule(order = 0) val permission: GrantPermissionRule = GrantPermissionRule.grant(Manifest.permission.RECORD_AUDIO)
    @get:Rule(order = 1) val compose = createComposeRule()
    private var client: SelectableVoiceClient? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    @After fun cleanup() {
        compose.runOnIdle { client?.close(); scope.cancel() }
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        File(context.filesDir, "live-test.json").delete()
    }

    @Test fun realSessionStreamsImageResponseHonorsPriorityAndClosesMicrophone() {
        assumeTrue("Requires explicit live=1 and private test credentials",
            InstrumentationRegistry.getArguments().getString("live") == "1")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val file = File(context.filesDir, "live-test.json")
        assertTrue("App-private live test configuration is required", file.isFile)
        val json = JSONObject(file.readText())
        val settings = BackendSettings(json.getString("url"), json.getString("accessToken"), VoiceProvider.valueOf(json.optString("provider", "OpenAI")))
        file.delete()
        val audio = context.getSystemService(AudioManager::class.java)
        val speaking = AtomicBoolean(false)
        compose.setContent { Text("Test vocal real VisionAssist") }
        compose.runOnIdle {
            client = SelectableVoiceClient(context, true)
            scope.launch { client!!.state.collect { if (it.phase == VoicePhase.Speaking) speaking.set(true) } }
            client!!.start(settings)
        }
        compose.waitUntil(45_000) { client!!.state.value.phase in setOf(VoicePhase.Listening, VoicePhase.Error) }
        assertEquals("Live connection: ${client!!.state.value.message}", VoicePhase.Listening, client!!.state.value.phase)
        compose.waitUntil(10_000) { audio.activeRecordingConfigurations.isNotEmpty() }

        val original = instrumentation.context.assets.open("cats_and_dogs.jpg").use { BitmapFactory.decodeStream(it) }
        val scale = minOf(1f, 256f / maxOf(original.width, original.height))
        val image = Bitmap.createScaledBitmap(original, (original.width * scale).toInt(), (original.height * scale).toInt(), true)
        val jpeg = ByteArrayOutputStream().use { image.compress(Bitmap.CompressFormat.JPEG, 60, it); it.toByteArray() }
        if (image !== original) image.recycle()
        original.recycle()
        assertTrue(jpeg.size <= 44_000)
        compose.runOnIdle { scope.launch { client!!.sendRequestedImage { jpeg } } }
        compose.waitUntil(45_000) { speaking.get() || client!!.state.value.phase == VoicePhase.Error }
        assertTrue("Real streamed response: ${client!!.state.value.message}", speaking.get())

        compose.runOnIdle { client!!.beginLocalWarning("live-priority") }
        assertTrue(client!!.state.value.warningActive)
        if (settings.provider == VoiceProvider.Gemini) {
            assertEquals(VoicePhase.Disconnected, client!!.state.value.phase)
            compose.waitUntil(10_000) { audio.activeRecordingConfigurations.isEmpty() }
        }
        // Allow the real buffer-clear acknowledgement/timeout to resolve while muted.
        Thread.sleep(3_500)
        assertNotEquals("Local interruption failed: ${client!!.state.value.message}", VoicePhase.Error, client!!.state.value.phase)
        compose.runOnIdle { client!!.endLocalWarning("live-priority") }
        assertFalse(client!!.state.value.warningActive)
        compose.runOnIdle { client!!.stop() }
        assertEquals(VoicePhase.Disconnected, client!!.state.value.phase)
        compose.waitUntil(10_000) { audio.activeRecordingConfigurations.isEmpty() }
        compose.runOnIdle { client!!.close(); client!!.close() }
    }
}
