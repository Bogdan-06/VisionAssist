package ro.visionassist.core.voice

import android.util.Base64
import org.junit.Assert.*
import org.junit.Test

class GeminiEventsTest {
    @Test fun imageAndRequestRemainOneExplicitUserTurn() {
        val bytes = byteArrayOf(1, 2, 3)
        val content = GeminiEvents.image(bytes).getJSONObject("clientContent")
        assertTrue(content.getBoolean("turnComplete"))
        val turn = content.getJSONArray("turns").getJSONObject(0)
        assertEquals("user", turn.getString("role"))
        val parts = turn.getJSONArray("parts")
        assertArrayEquals(bytes, Base64.decode(parts.getJSONObject(0).getJSONObject("inlineData").getString("data"), Base64.DEFAULT))
        assertTrue(parts.getJSONObject(1).getString("text").contains("Nu inventa"))
        assertEquals("audio/pcm;rate=16000", GeminiEvents.audio(bytes).getJSONObject("realtimeInput").getJSONObject("audio").getString("mimeType"))
    }
    @Test fun declinedPhotoCorrelatesWithOriginalToolCall() {
        val response = GeminiEvents.toolResult("call-42", "request_camera_image", "user_declined")
            .getJSONObject("toolResponse").getJSONArray("functionResponses").getJSONObject(0)
        assertEquals("call-42", response.getString("id"))
        assertEquals("user_declined", response.getJSONObject("response").getString("status"))
        assertFalse(response.has("inlineData"))
    }
}
