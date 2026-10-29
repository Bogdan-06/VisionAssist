package ro.visionassist.core.ground

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Debug
import android.os.Build
import android.os.SystemClock
import android.util.Log
import androidx.test.platform.app.InstrumentationRegistry
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.core.Delegate
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.objectdetector.ObjectDetector
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.ceil
import org.json.JSONObject
import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Test

/** Models in this test exist ONLY in instrumentation assets, never production assets. */
class BarrierModelCompatibilityTest {
    @Test fun threeClassMetadataModelRunsOfflineOnReviewedImages() {
        val context=InstrumentationRegistry.getInstrumentation().context
        context.deleteFile("barrier-runtime-results.json")
        fun sha(bytes:ByteArray)=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        val arguments=InstrumentationRegistry.getArguments()
        val folder=arguments.getString("barrier_fixture","barrier-compat")
        require(folder.matches(Regex("[a-z][a-z0-9-]{0,40}")))
        val expectedSha=arguments.getString("barrier_model_sha256") ?: run {
            require(folder=="barrier-compat") { "Supply the candidate model SHA-256" }
            TEST_MODEL_SHA
        }
        require(expectedSha.matches(Regex("[0-9a-f]{64}")))
        for (permission in listOf(Manifest.permission.INTERNET,Manifest.permission.CAMERA,Manifest.permission.RECORD_AUDIO)) {
            assertEquals("Fixture test must not have $permission",PackageManager.PERMISSION_DENIED,
                context.checkSelfPermission(permission))
        }
        val fixtureBytes=context.assets.open("$folder/fixture.json").use { it.readBytes() }
        val fixture=JSONObject(fixtureBytes.toString(Charsets.UTF_8))
        assertTrue(fixture.getBoolean("test_only"))
        assertFalse(fixture.getBoolean("warning_eligible"))
        val model=context.assets.open("$folder/model.tflite").use { it.readBytes() }
        assertEquals(expectedSha,sha(model))
        assertEquals(expectedSha,fixture.getString("model_sha256"))
        val buffer=ByteBuffer.allocateDirect(model.size).order(ByteOrder.nativeOrder()).apply { put(model); rewind() }
        val labels=fixture.getJSONArray("labels")
        assertEquals(listOf("background","stairs","curb","step"),(0 until labels.length()).map { labels.getString(it) })
        val options=ObjectDetector.ObjectDetectorOptions.builder()
            .setBaseOptions(BaseOptions.builder().setModelAssetBuffer(buffer).setDelegate(Delegate.CPU).build())
            .setRunningMode(RunningMode.IMAGE).setMaxResults(100).setScoreThreshold(.05f)
            .setCategoryAllowlist(listOf("stairs","curb","step")).build()
        val times=mutableListOf<Long>()
        val before=Debug.MemoryInfo().also { Debug.getMemoryInfo(it) }.totalPss
        var observed=0
        var validProjections=0
        val observedIndices=mutableSetOf<Int>()
        val frameReports=JSONArray()
        ObjectDetector.createFromOptions(context,options).use { detector ->
            val records=fixture.getJSONArray("records")
            assertEquals(4,records.length())
            for (index in 0 until records.length()) {
                val record=records.getJSONObject(index)
                val file=record.getString("file")
                require(file.matches(Regex("frame-[0-9]+\\.png")))
                val bytes=context.assets.open("$folder/$file").use { it.readBytes() }
                assertEquals(record.getString("png_sha256"),sha(bytes))
                val bitmap=requireNotNull(BitmapFactory.decodeByteArray(bytes,0,bytes.size))
                try {
                    assertEquals(record.getInt("width"),bitmap.width)
                    assertEquals(record.getInt("height"),bitmap.height)
                    val pixels=IntArray(bitmap.width*bitmap.height)
                    bitmap.getPixels(pixels,0,bitmap.width,0,0,bitmap.width,bitmap.height)
                    val rgb=ByteArray(pixels.size*3)
                    for (i in pixels.indices) {
                        rgb[i*3]=((pixels[i] shr 16) and 255).toByte()
                        rgb[i*3+1]=((pixels[i] shr 8) and 255).toByte()
                        rgb[i*3+2]=(pixels[i] and 255).toByte()
                    }
                    val rgbSha=sha(rgb)
                    assertEquals("Decoded RGB differs from Python",record.getString("rgb_sha256"),rgbSha)
                    repeat(4) { iteration ->
                        // MPImage owns/recycles its bitmap. Preserve the caller's pixels.
                        val copy=requireNotNull(bitmap.copy(Bitmap.Config.ARGB_8888,false))
                        val image=BitmapImageBuilder(copy).build()
                        try {
                            val started=SystemClock.elapsedRealtime()
                            val result=detector.detect(image)
                            val elapsed=SystemClock.elapsedRealtime()-started
                            if (iteration>0) times+=elapsed
                            assertTrue(result.detections().size<=100)
                            observed+=result.detections().size
                            val predictions=JSONArray()
                            val rawPredictions=JSONArray()
                            for (detection in result.detections()) {
                                val category=detection.categories().first()
                                observedIndices+=category.index()
                                assertTrue("Unknown model label: ${category.categoryName()}",
                                    category.categoryName() in setOf("stairs","curb","step"))
                                // Category.index is optional: this SDK returns -1 when
                                // DetectionProto does not carry label_id. Use exact names.
                                if (category.index()>=0) {
                                    assertTrue("Unexpected index ${category.index()}",category.index() in 1..3)
                                    assertEquals(labels.getString(category.index()),category.categoryName())
                                } else assertEquals("Only -1 represents an unset index",-1,category.index())
                                assertTrue(category.score().isFinite() && category.score() in .05f..1f)
                                val box=detection.boundingBox()
                                assertTrue(listOf(box.left,box.top,box.right,box.bottom).all { it.isFinite() })
                                rawPredictions.put(JSONObject().put("class",category.categoryName())
                                    .put("score",category.score()).put("index",category.index())
                                    .put("box",JSONArray(listOf(box.left,box.top,box.right,box.bottom))))
                                // Raw task boxes may project outside the image. Only a
                                // nonempty clipped projection could become a UI candidate.
                                val left=box.left.coerceIn(0f,bitmap.width.toFloat())
                                val top=box.top.coerceIn(0f,bitmap.height.toFloat())
                                val right=box.right.coerceIn(0f,bitmap.width.toFloat())
                                val bottom=box.bottom.coerceIn(0f,bitmap.height.toFloat())
                                if (right>left && bottom>top) {
                                    validProjections++
                                    assertTrue(left/bitmap.width in 0f..1f && right/bitmap.width in 0f..1f)
                                    assertTrue(top/bitmap.height in 0f..1f && bottom/bitmap.height in 0f..1f)
                                    predictions.put(JSONObject().put("class",category.categoryName())
                                        .put("score",category.score()).put("index",category.index())
                                        .put("box",JSONArray(listOf(left,top,right,bottom))))
                                }
                            }
                            if (iteration==0) frameReports.put(JSONObject().put("file",file)
                                .put("png_sha256",sha(bytes)).put("width",bitmap.width).put("height",bitmap.height)
                                .put("rgb_sha256",rgbSha)
                                .put("predictions",predictions).put("raw_predictions",rawPredictions))
                        } finally { image.close() }
                        assertFalse("Caller bitmap was recycled",bitmap.isRecycled)
                    }
                } finally { bitmap.recycle() }
            }
            val report=JSONObject().put("test_only",true).put("warning_eligible",false)
                .put("model_sha256",expectedSha).put("fixture_sha256",sha(fixtureBytes))
                .put("smoke_model",fixture.getBoolean("smoke_model"))
                .put("device",Build.MODEL).put("android_api",Build.VERSION.SDK_INT)
                .put("runtime","MediaPipe Tasks Android CPU, Gradle pin 0.10.32")
                .put("captured_epoch_ms",System.currentTimeMillis()).put("records",frameReports)
            context.openFileOutput("barrier-runtime-results.json",Context.MODE_PRIVATE).bufferedWriter().use {
                it.write(report.toString(2))
            }
            if (fixture.getBoolean("smoke_model")) {
                assertTrue("The real smoke fixture must exercise metadata decoding",observed>0)
                assertTrue("Fixture produced no usable image projections",validProjections>0)
            }
            times.sort()
            val median=(times[(times.size-1)/2]+times[times.size/2])/2.0
            val p95=times[ceil(.95*times.size).toInt()-1]
            val during=Debug.MemoryInfo().also { Debug.getMemoryInfo(it) }.totalPss
            Log.i("BarrierCompatibility","actual Task CPU inference; samples=${times.size} median_ms=$median p95_ms=$p95; pss_kb before=$before loaded=$during; includes task pre/postprocessing, excludes bitmap copy and camera")
            Log.i("BarrierCompatibility","Structural compatibility only; smoke=${fixture.getBoolean("smoke_model")}; no accuracy, numeric parity, warnings, camera or microphone check")
            Log.i("BarrierCompatibility","raw_detections=$observed nonempty_clipped_projections=$validProjections category_indices=$observedIndices; label names remain mandatory")
        }
    }

    companion object { const val TEST_MODEL_SHA="0097090945bbf0b73301c33803c00c5d200f564d1e9d75bd42682a274e22e7ed" }
}
