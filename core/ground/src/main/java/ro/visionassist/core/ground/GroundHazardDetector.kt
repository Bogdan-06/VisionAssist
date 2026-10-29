package ro.visionassist.core.ground

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.os.SystemClock
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.math.min
import kotlin.math.roundToInt

/** Thread-confined CPU inference. Reads but never owns/recycles the caller's image. */
class GroundHazardDetector(context: Context) : AutoCloseable {
    private val interpreter: Interpreter
    private val model: ByteBuffer
    private val input = ByteBuffer.allocateDirect(320*320*3*4).order(ByteOrder.nativeOrder())
    private val output = ByteBuffer.allocateDirect(20*20*5*4).order(ByteOrder.nativeOrder())
    private val canvasBitmap = Bitmap.createBitmap(320,320,Bitmap.Config.ARGB_8888)
    private val pixels = IntArray(320*320)
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG)

    init {
        val bytes = context.assets.open("ground_baseline.tflite").use { it.readBytes() }
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        require(digest == MODEL_SHA256) { "Unrecognized ground model" }
        model = ByteBuffer.allocateDirect(bytes.size).order(ByteOrder.nativeOrder()).apply { put(bytes); rewind() }
        interpreter = Interpreter(model, Interpreter.Options().setNumThreads(2).setUseXNNPACK(true))
        try {
            require(interpreter.getInputTensor(0).shape().contentEquals(intArrayOf(1,320,320,3)))
            require(interpreter.getOutputTensor(0).shape().contentEquals(intArrayOf(1,20,20,5)))
            require(interpreter.getInputTensor(0).dataType() == DataType.FLOAT32)
            require(interpreter.getOutputTensor(0).dataType() == DataType.FLOAT32)
        } catch (error: Exception) { interpreter.close(); canvasBitmap.recycle(); throw error }
    }

    fun detect(bitmap: Bitmap, receivedAtMs: Long): GroundFrame {
        val started = SystemClock.elapsedRealtime()
        val scale = min(320f/bitmap.width,320f/bitmap.height)
        val rw = (bitmap.width*scale).roundToInt().coerceIn(1,320)
        val rh = (bitmap.height*scale).roundToInt().coerceIn(1,320)
        val left = (320-rw)/2; val top = (320-rh)/2
        Canvas(canvasBitmap).apply {
            drawColor(Color.rgb(114,114,114))
            drawBitmap(bitmap,null,Rect(left,top,left+rw,top+rh),paint)
        }
        canvasBitmap.getPixels(pixels,0,320,0,0,320,320)
        input.rewind(); output.rewind()
        for (pixel in pixels) {
            input.putFloat(Color.red(pixel)/127.5f-1)
            input.putFloat(Color.green(pixel)/127.5f-1)
            input.putFloat(Color.blue(pixel)/127.5f-1)
        }
        input.rewind()
        val before = SystemClock.elapsedRealtime()
        interpreter.run(input,output)
        val inferenceMs = SystemClock.elapsedRealtime()-before
        output.rewind()
        val values = FloatArray(20*20*5); output.asFloatBuffer().get(values)
        val candidates = GroundDecoder.decode(values,bitmap.width,bitmap.height,rw,rh)
        return GroundFrame(candidates,receivedAtMs,bitmap.width,bitmap.height,inferenceMs,SystemClock.elapsedRealtime()-started)
    }

    override fun close() { interpreter.close(); canvasBitmap.recycle() }
    companion object { const val MODEL_SHA256 = "bb8ebf2bce188df2206e3fa78891888764f095ab40cad5a508c3da307cc7af88" }
}
