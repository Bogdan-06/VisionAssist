package ro.visionassist.core.voice

import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.webrtc.*
import org.webrtc.audio.JavaAudioDeviceModule
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.lang.reflect.Proxy

class RealtimeProtocolTest {
    @Test fun imageUsesGaUserItemAndToolOutputNeverContainsImageWithoutExplicitCall() {
        val image = RealtimeEvents.image(byteArrayOf(1, 2, 3), "AQID")
        assertEquals("conversation.item.create", image.getString("type"))
        val content = image.getJSONObject("item").getJSONArray("content")
        assertEquals("user", image.getJSONObject("item").getString("role"))
        assertEquals("input_image", content.getJSONObject(1).getString("type"))
        assertEquals("data:image/jpeg;base64,AQID", content.getJSONObject(1).getString("image_url"))
        assertThrows(IllegalArgumentException::class.java) { RealtimeEvents.image(ByteArray(44_001), "") }
        assertEquals("function_call_output", RealtimeEvents.toolResult("call-1", "user_declined").getJSONObject("item").getString("type"))
    }

    @Test fun bundledNativeWebRtcCreatesAudioAndDataOfferAndReleasesResources() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        PeerConnectionFactory.initialize(PeerConnectionFactory.InitializationOptions.builder(context).createInitializationOptions())
        val device = JavaAudioDeviceModule.builder(context).createAudioDeviceModule()
        val factory = PeerConnectionFactory.builder().setAudioDeviceModule(device).createPeerConnectionFactory()
        val observer = Proxy.newProxyInstance(PeerConnection.Observer::class.java.classLoader, arrayOf(PeerConnection.Observer::class.java)) { _, _, _ -> null } as PeerConnection.Observer
        val peer = factory.createPeerConnection(PeerConnection.RTCConfiguration(emptyList()).apply {
            sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN
        }, observer)!!
        val source = factory.createAudioSource(MediaConstraints())
        val track = factory.createAudioTrack("test-microphone", source)
        val data = peer.createDataChannel("oai-events", DataChannel.Init())
        try {
            device.setMicrophoneMute(true); device.setSpeakerMute(true)
            peer.addTrack(track, listOf("test"))
            val done = CountDownLatch(1)
            var sdp: String? = null
            peer.createOffer(object : SdpObserver {
                override fun onCreateSuccess(value: SessionDescription) { sdp = value.description; done.countDown() }
                override fun onCreateFailure(error: String) { done.countDown() }
                override fun onSetSuccess() = Unit
                override fun onSetFailure(error: String) = Unit
            }, MediaConstraints())
            assertTrue(done.await(10, TimeUnit.SECONDS))
            assertTrue(sdp?.contains("m=audio") == true)
            assertTrue(sdp?.contains("m=application") == true)
            assertFalse(sdp?.contains("m=video") == true)
        } finally {
            data.close(); data.dispose(); peer.close(); peer.dispose(); track.dispose(); source.dispose(); factory.dispose(); device.release()
        }
    }
}
