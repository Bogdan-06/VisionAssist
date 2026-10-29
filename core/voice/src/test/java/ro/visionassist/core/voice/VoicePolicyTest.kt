package ro.visionassist.core.voice

import org.junit.Assert.*
import org.junit.Test

class VoicePolicyTest {
    @Test fun imageAlreadyDispatchedDoesNotHideAFollowingTransportErrorOrClaimRecall() {
        val failed = VoiceState(VoicePhase.Error, "Conexiunea s-a întrerupt.").afterImageDispatch()
        assertEquals(VoicePhase.Error, failed.phase)
        assertTrue(failed.message.contains("Fotografia a fost trimisă"))
        assertTrue(failed.message.contains("conversația s-a întrerupt"))
        val normal = VoiceState(VoicePhase.Listening).afterImageDispatch()
        assertEquals(VoicePhase.Listening, normal.phase)
        assertEquals("Fotografia solicitată a fost trimisă.", normal.message)
    }
    @Test fun overlappingWarningsAndLateCompletionsCannotUnmuteAi() {
        val gate = AudioPriorityGate()
        gate.begin("a"); gate.begin("b"); gate.end("a"); gate.cleared()
        assertTrue(gate.muted)
        gate.end("a"); assertTrue(gate.muted)
        gate.end("b"); assertFalse(gate.muted)
    }
    @Test fun playbackRequiresBothWarningCompletionAndClearAcknowledgement() {
        val gate = AudioPriorityGate(); gate.begin("warning"); gate.end("warning")
        assertTrue(gate.muted); gate.cleared(); assertFalse(gate.muted)
        gate.begin("new"); gate.resetTransport(); assertTrue(gate.muted)
    }
    @Test fun credentialsAndCleartextAreRestrictedToTheBackend() {
        val token = "a".repeat(40)
        BackendSettings("https://voice.example", token).validate(false)
        BackendSettings("http://127.0.0.1:8787", token).validate(true)
        for (url in listOf("http://voice.example", "https://user:password@voice.example", "https://voice.example?token=bad")) {
            assertThrows(IllegalArgumentException::class.java) { BackendSettings(url, token).validate(true) }
        }
        assertThrows(IllegalArgumentException::class.java) { BackendSettings("http://127.0.0.1", token).validate(false) }
        assertThrows(IllegalArgumentException::class.java) { BackendSettings("https://voice.example", "sk-" + token).validate(false) }
        assertThrows(IllegalArgumentException::class.java) { BackendSettings("https://voice.example", "AIza" + token, VoiceProvider.Gemini).validate(false) }
    }
}
