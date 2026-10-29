package ro.visionassist.core.voice

import org.json.JSONArray
import org.json.JSONObject

internal object RealtimeEvents {
    fun simple(type: String) = JSONObject().put("type", type)
    fun toolResult(callId: String, status: String) = simple("conversation.item.create").put("item",
        JSONObject().put("type", "function_call_output").put("call_id", callId)
            .put("output", JSONObject().put("status", status).toString()))
    fun image(bytes: ByteArray, encoded: String): JSONObject {
        require(bytes.size <= 44_000)
        return simple("conversation.item.create").put("item", JSONObject()
            .put("type", "message").put("role", "user").put("content", JSONArray()
                .put(JSONObject().put("type", "input_text").put("text",
                    "Descrie în română această fotografie făcută acum, la cererea mea. Nu estima distanțe și nu declara traseul sigur."))
                .put(JSONObject().put("type", "input_image").put("image_url", "data:image/jpeg;base64,$encoded"))))
    }
}
