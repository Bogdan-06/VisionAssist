package ro.visionassist.app.voice

import android.content.Context
import android.util.Base64
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import ro.visionassist.app.ui.VisionAssistTheme
import ro.visionassist.core.camera.CameraSnapshotRequest
import ro.visionassist.core.voice.*
import java.security.KeyStore
import java.util.UUID

/** Isolated preferences and alias: never overwrite a person's saved backend or key. */
class BackendSettingsStoreTest {
    @get:Rule val compose = createComposeRule()
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val name = "backend-test-${UUID.randomUUID()}"
    private val alias = "visionassist-test-${UUID.randomUUID()}"
    private val preferences = context.getSharedPreferences(name, Context.MODE_PRIVATE)
    private val store = BackendSettingsStore(context, preferences, alias)
    private var client: VoiceClient? = null
    private var announcements: LocalAnnouncements? = null
    private val sample = BackendSettings("https://voice.example", "test-only-access-code-" + "x".repeat(40), VoiceProvider.OpenAI)

    @After fun cleanup() {
        compose.runOnIdle { announcements?.close(); client?.close() }
        context.deleteSharedPreferences(name)
        KeyStore.getInstance("AndroidKeyStore").apply { load(null); if (containsAlias(alias)) deleteEntry(alias) }
    }

    @Test fun missingDataDiffersFromCorruptedDataAndLoadDoesNotDeleteIt() {
        assertEquals(BackendSettingsLoadResult.Unconfigured, store.load())
        val broken = "not-json-and-not-a-provider-key"
        preferences.edit().putString("encrypted", broken).commit()
        assertEquals(BackendSettingsLoadResult.Unreadable, store.load())
        assertEquals(broken, preferences.getString("encrypted", null))
        assertFalse(KeyStore.getInstance("AndroidKeyStore").apply { load(null) }.containsAlias(alias))
    }

    @Test fun realKeystoreRoundTripAndTamperedAuthenticationTagAreDistinguished() {
        store.save(sample)
        val available = store.load() as BackendSettingsLoadResult.Available
        assertEquals(sample, available.settings)
        assertFalse(available.toString().contains(sample.accessToken))
        assertFalse(sample.toString().contains(sample.accessToken))
        val payload = JSONObject(preferences.getString("encrypted", null)!!)
        val bytes = Base64.decode(payload.getString("data"), Base64.NO_WRAP)
        bytes[0] = (bytes[0].toInt() xor 1).toByte()
        val broken = payload.put("data", Base64.encodeToString(bytes, Base64.NO_WRAP)).toString()
        preferences.edit().putString("encrypted", broken).commit()
        assertEquals(BackendSettingsLoadResult.Unreadable, store.load())
        assertEquals(broken, preferences.getString("encrypted", null))
    }

    @Test fun missingDecryptionKeyIsNotSilentlyRegenerated() {
        store.save(sample)
        KeyStore.getInstance("AndroidKeyStore").apply { load(null); deleteEntry(alias) }
        val saved = preferences.getString("encrypted", null)
        assertEquals(BackendSettingsLoadResult.Unreadable, store.load())
        assertEquals(saved, preferences.getString("encrypted", null))
        assertFalse(KeyStore.getInstance("AndroidKeyStore").apply { load(null) }.containsAlias(alias))
    }

    @Test fun unreadableSettingsShowRedactedRecoveryAndCancelPreservesCiphertext() {
        val broken = "broken-private-value-not-to-display"
        preferences.edit().putString("encrypted", broken).commit()
        compose.runOnIdle {
            client = RealtimeVoiceClient(context, true)
            announcements = LocalAnnouncements(context, client!!)
        }
        compose.setContent {
            VisionAssistTheme { Column(Modifier.verticalScroll(rememberScrollState())) {
                VoiceControls(client!!, announcements!!, CameraSnapshotRequest(), false, true, settingsStore = store)
            } }
        }
        compose.onNodeWithText("Configurația vocală salvată nu a putut fi citită.", substring = true).assertExists()
        compose.onAllNodesWithText(broken, substring = true).assertCountEquals(0)
        compose.onNodeWithText("Pornește conversația AI").performScrollTo().performClick()
        compose.onNodeWithText("Adresa HTTPS a serverului").assertExists()
        compose.onNodeWithText("Anulează").performClick()
        compose.runOnIdle { assertEquals(VoicePhase.Disconnected, client!!.state.value.phase) }
        assertEquals(broken, preferences.getString("encrypted", null))
    }
}
