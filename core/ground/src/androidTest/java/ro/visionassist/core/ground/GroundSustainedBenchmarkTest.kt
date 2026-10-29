package ro.visionassist.core.ground

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.BitmapFactory
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import kotlin.math.ceil

/** Opt-in fixture benchmark. It opens no Activity, camera, microphone or network connection. */
class GroundSustainedBenchmarkTest {
    @Test fun sustainedRealFixtureInference() {
        assumeTrue("Explicit benchmark argument required",
            InstrumentationRegistry.getArguments().getString("allow_sustained_ground") == "true")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val bitmap = instrumentation.context.assets.open("rdd_pothole.jpg").use { BitmapFactory.decodeStream(it) }
        val samples = JSONArray()
        val inference = mutableListOf<Long>()
        val processing = mutableListOf<Long>()
        val frameIntervals = mutableListOf<Long>()
        val beforeLoad = pssKb()
        try {
            GroundHazardDetector(context).use { detector ->
                repeat(5) { detector.detect(bitmap, SystemClock.elapsedRealtime()) }
                val start = SystemClock.elapsedRealtime()
                val cpuStart = Process.getElapsedCpuTime()
                val startState = state(context)
                var peakPss = pssKb()
                var previousFrame: Long? = null
                var nextFrame = start
                while (SystemClock.elapsedRealtime() - start < 120_000) {
                    val waitMs = nextFrame - SystemClock.elapsedRealtime()
                    if (waitMs > 0) SystemClock.sleep(waitMs)
                    val frameStart = SystemClock.elapsedRealtime()
                    if (frameStart-start >= 120_000) break
                    previousFrame?.let { frameIntervals += frameStart-it }
                    previousFrame = frameStart
                    val result = detector.detect(bitmap, frameStart)
                    assertTrue("Actual real-photo candidates required", result.candidates.isNotEmpty())
                    assertFalse(bitmap.isRecycled)
                    inference += result.inferenceMs
                    processing += result.processingMs
                    if (inference.size % 25 == 0) {
                        val memory = pssKb(); peakPss = maxOf(peakPss, memory)
                        samples.put(JSONObject().put("elapsed_ms", SystemClock.elapsedRealtime()-start)
                            .put("process_pss_kb", memory).put("device_state", state(context)))
                    }
                    // No catch-up burst if the device suspends or work exceeds the interval.
                    nextFrame = maxOf(frameStart+400, SystemClock.elapsedRealtime())
                }
                val elapsed = SystemClock.elapsedRealtime()-start
                val cpuMs = Process.getElapsedCpuTime()-cpuStart
                val report = JSONObject().put("device", Build.MODEL).put("api", Build.VERSION.SDK_INT)
                    .put("model_sha256", GroundHazardDetector.MODEL_SHA256)
                    .put("fixture", "rdd_pothole.jpg").put("warmup_frames", 5)
                    .put("frames", inference.size).put("target_interval_ms", 400)
                    .put("elapsed_ms", elapsed).put("process_cpu_ms", cpuMs)
                    .put("process_cpu_ms_per_elapsed_ms", cpuMs.toDouble()/elapsed)
                    .put("inference_ms", percentiles(inference)).put("processing_ms", percentiles(processing))
                    .put("frame_interval_ms", percentiles(frameIntervals))
                    .put("process_pss_before_load_kb", beforeLoad).put("process_pss_peak_sampled_kb", peakPss)
                    .put("start_device_state", startState).put("end_device_state", state(context))
                    .put("samples", samples)
                    .put("limitations", JSONArray(listOf(
                        "Single fixture at 400 ms intervals; no live camera, COCO concurrency or assistant.",
                        "Process CPU/PSS include the runtime and test harness; PSS peak is sampled, not continuous.",
                        "Battery counters/current/temperature describe the whole device, not attributable model energy.",
                        "No background-app, screen-brightness or ambient-temperature control; no battery-life estimate.",
                        "Two minutes is not a long-term thermal or navigation-safety study."
                    )))
                File(context.filesDir, "ground-sustained-benchmark.json").writeText(report.toString(2))
                instrumentation.sendStatus(2, Bundle().apply { putString("stream", "\nGroundSustained: $report\n") })
                assertTrue("Device suspension or scheduling prevented a sustained sample", inference.size >= 250)
            }
        } finally { bitmap.recycle() }
    }

    private fun pssKb() = Debug.MemoryInfo().also { Debug.getMemoryInfo(it) }.totalPss

    private fun state(context: Context): JSONObject {
        val battery = context.getSystemService(BatteryManager::class.java)
        val power = context.getSystemService(PowerManager::class.java)
        val intent = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        fun property(id: Int): Any {
            val value = battery.getLongProperty(id)
            return if (value == Long.MIN_VALUE) JSONObject.NULL else value
        }
        return JSONObject().put("charge_counter_uah", property(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER))
            .put("current_now_ua", property(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW))
            .put("battery_level", intent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: JSONObject.NULL)
            .put("plugged", intent?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1) ?: JSONObject.NULL)
            .put("battery_temperature_tenths_c", intent?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) ?: JSONObject.NULL)
            .put("thermal_status", if (Build.VERSION.SDK_INT >= 29) power.currentThermalStatus else JSONObject.NULL)
    }

    private fun percentiles(values: List<Long>): JSONObject {
        val sorted = values.sorted()
        return JSONObject().apply {
            for (p in listOf(50, 95, 99)) put("p$p", if (sorted.isEmpty()) JSONObject.NULL
                else sorted[(ceil(sorted.size*p/100.0).toInt()-1).coerceIn(0,sorted.lastIndex)])
        }
    }
}
