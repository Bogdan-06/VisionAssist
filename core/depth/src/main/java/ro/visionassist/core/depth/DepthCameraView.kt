package ro.visionassist.core.depth

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Matrix
import android.graphics.Paint
import android.media.Image
import android.opengl.GLES11Ext
import android.opengl.GLES20
import android.opengl.GLSurfaceView
import android.os.SystemClock
import com.google.ar.core.Coordinates2d
import com.google.ar.core.Frame
import com.google.ar.core.Session
import com.google.ar.core.TrackingState
import com.google.ar.core.exceptions.NotYetAvailableException
import ro.visionassist.core.ground.GroundCandidate
import ro.visionassist.core.ground.GroundBox
import ro.visionassist.core.ground.GroundMetrics
import ro.visionassist.core.ground.GroundWorker
import java.nio.ByteBuffer
import java.nio.ByteOrder
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10
import kotlin.math.roundToInt

data class DepthCandidate(val visual:GroundCandidate,val regionDepth:RegionDepth?)
data class DepthProbeResult(val candidates:List<DepthCandidate>,val receivedAtMs:Long,
    val diagnostic:DiscontinuityDiagnostic?,val metrics:GroundMetrics?,val hasFreshDepth:Boolean,
    val centerDepth:RegionDepth?=null)

/** Dedicated ARCore camera owner. Never mount while a CameraX session is active. */
class DepthCameraView(context:Context, private val onResult:(DepthProbeResult)->Unit,
                      private val onStatus:(String)->Unit,
                      experimentalGroundEnabled:Boolean = false) : GLSurfaceView(context), AutoCloseable {
    @Volatile var arSession:Session?=null
    private val ground=if (experimentalGroundEnabled) GroundWorker(context) { onStatus("Modelul experimental de gropi nu este disponibil.") } else null
    private var lastAttempt=0L
    private var lastStatusAt=0L
    private var lastStatusText=""
    @Synchronized private fun publishStatus(message:String) {
        val now=SystemClock.elapsedRealtime()
        if (message==lastStatusText && now-lastStatusAt<1_000) return
        lastStatusAt=now; lastStatusText=message; onStatus(message)
    }
    private val renderer=object:Renderer {
        private var texture=0; private var program=0; private var width=0; private var height=0
        private val vertices=floatArrayOf(-1f,-1f,1f,-1f,-1f,1f,1f,1f)
        private val vertexBuffer=buffer(vertices)
        private val uvBuffer=buffer(FloatArray(8))
        override fun onSurfaceCreated(gl:GL10?,config:EGLConfig?) {
            val names=IntArray(1); GLES20.glGenTextures(1,names,0); texture=names[0]
            GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,texture)
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_MIN_FILTER,GLES20.GL_LINEAR)
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_MAG_FILTER,GLES20.GL_LINEAR)
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_WRAP_S,GLES20.GL_CLAMP_TO_EDGE)
            GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_WRAP_T,GLES20.GL_CLAMP_TO_EDGE)
            program=GLES20.glCreateProgram()
            val vertex=shader(GLES20.GL_VERTEX_SHADER,"attribute vec2 p; attribute vec2 uv; varying vec2 t; void main(){ gl_Position=vec4(p,0.,1.); t=uv; }")
            val fragment=shader(GLES20.GL_FRAGMENT_SHADER,"#extension GL_OES_EGL_image_external : require\nprecision mediump float; uniform samplerExternalOES camera; varying vec2 t; void main(){ gl_FragColor=texture2D(camera,t); }")
            GLES20.glAttachShader(program,vertex); GLES20.glAttachShader(program,fragment); GLES20.glLinkProgram(program)
            GLES20.glDeleteShader(vertex); GLES20.glDeleteShader(fragment)
        }
        override fun onSurfaceChanged(gl:GL10?,w:Int,h:Int) { width=w; height=h; GLES20.glViewport(0,0,w,h) }
        override fun onDrawFrame(gl:GL10?) {
            GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT)
            val session=arSession ?: return
            if (width<=0 || height<=0) return
            try {
                session.setDisplayGeometry(display?.rotation ?: 0,width,height)
                session.setCameraTextureName(texture)
                val frame=session.update()
                if (frame.timestamp==0L) return
                val uv=FloatArray(8)
                frame.transformCoordinates2d(Coordinates2d.OPENGL_NORMALIZED_DEVICE_COORDINATES,vertices,Coordinates2d.TEXTURE_NORMALIZED,uv)
                uvBuffer.rewind(); uvBuffer.put(uv); uvBuffer.rewind()
                GLES20.glUseProgram(program)
                GLES20.glActiveTexture(GLES20.GL_TEXTURE0); GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,texture)
                GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"camera"),0)
                val p=GLES20.glGetAttribLocation(program,"p"); val t=GLES20.glGetAttribLocation(program,"uv")
                GLES20.glEnableVertexAttribArray(p); GLES20.glEnableVertexAttribArray(t)
                GLES20.glVertexAttribPointer(p,2,GLES20.GL_FLOAT,false,0,vertexBuffer)
                GLES20.glVertexAttribPointer(t,2,GLES20.GL_FLOAT,false,0,uvBuffer)
                GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP,0,4)
                GLES20.glDisableVertexAttribArray(p); GLES20.glDisableVertexAttribArray(t)
                val now=SystemClock.elapsedRealtime()
                if (now-lastAttempt<400) return
                lastAttempt=now
                if (frame.camera.trackingState!=TrackingState.TRACKING) {
                    publishStatus("Urmărirea AR nu este stabilă. Distanță necunoscută."); return
                }
                capture(frame,width,height,now)
            } catch (_: NotYetAvailableException) {
                publishStatus("Se așteaptă un cadru și măsurători de adâncime.")
            } catch (_: Exception) {
                // Do not attach old boxes/depth to a new frame after any capture failure.
                publishStatus("Captura de adâncime nu este disponibilă. Revino la camera obișnuită sau reîncearcă.")
            }
        }
    }

    init { setEGLContextClientVersion(2); setRenderer(renderer); importantForAccessibility=IMPORTANT_FOR_ACCESSIBILITY_NO }

    private fun capture(frame:Frame,viewWidth:Int,viewHeight:Int,now:Long) {
        val depth=RawDepthCapture.copy(frame)
        val detector = ground
        if (detector == null) {
            // Surface measurements remain available without loading an unvalidated detector.
            onResult(DepthProbeResult(emptyList(), now, depth?.let(DepthEvidence::discontinuities), null,
                depth != null, depth?.let { DepthEvidence.region(it,GroundBox(.25f,.25f,.75f,.75f)) }))
            return
        }
        frame.acquireCameraImage().use { image ->
            // The CPU image and depth are acquired from this exact Frame before the next update.
            if (image.timestamp != frame.timestamp) return
            val bitmap=uprightViewBitmap(image,frame,viewWidth,viewHeight)
            try {
                detector.offer(bitmap,now) { result,metrics ->
                    onResult(DepthProbeResult(result.candidates.map { DepthCandidate(it,depth?.let { d -> DepthEvidence.region(d,it.bounds) }) },
                        result.receivedAtMs,depth?.let(DepthEvidence::discontinuities),metrics,depth!=null,
                        depth?.let { DepthEvidence.region(it,GroundBox(.25f,.25f,.75f,.75f)) }))
                }
            } finally { bitmap.recycle() }
        }
    }

    override fun close() { arSession=null; ground?.close() }

    companion object {
        private fun buffer(values:FloatArray)=ByteBuffer.allocateDirect(values.size*4).order(ByteOrder.nativeOrder()).asFloatBuffer().apply { put(values); rewind() }
        private fun shader(type:Int,source:String):Int = GLES20.glCreateShader(type).also {
            GLES20.glShaderSource(it,source); GLES20.glCompileShader(it)
        }
        private fun uprightViewBitmap(image:Image,frame:Frame,viewWidth:Int,viewHeight:Int):Bitmap {
            val width=image.width; val height=image.height
            val rgb=IntArray(width*height)
            val yPlane=image.planes[0]; val uPlane=image.planes[1]; val vPlane=image.planes[2]
            for (y in 0 until height) for (x in 0 until width) {
                val yy=(yPlane.buffer.get(y*yPlane.rowStride+x*yPlane.pixelStride).toInt() and 255)-16
                val u=(uPlane.buffer.get(y/2*uPlane.rowStride+x/2*uPlane.pixelStride).toInt() and 255)-128
                val v=(vPlane.buffer.get(y/2*vPlane.rowStride+x/2*vPlane.pixelStride).toInt() and 255)-128
                val r=((298*yy+409*v+128) shr 8).coerceIn(0,255)
                val g=((298*yy-100*u-208*v+128) shr 8).coerceIn(0,255)
                val b=((298*yy+516*u+128) shr 8).coerceIn(0,255)
                rgb[y*width+x]=(255 shl 24) or (r shl 16) or (g shl 8) or b
            }
            val source=Bitmap.createBitmap(rgb,width,height,Bitmap.Config.ARGB_8888)
            try {
                val factor=640f/maxOf(viewWidth,viewHeight)
                val outWidth=(viewWidth*factor).roundToInt().coerceAtLeast(1)
                val outHeight=(viewHeight*factor).roundToInt().coerceAtLeast(1)
                val src=floatArrayOf(0f,0f,width.toFloat(),0f,0f,height.toFloat()); val dest=FloatArray(6)
                frame.transformCoordinates2d(Coordinates2d.IMAGE_PIXELS,src,Coordinates2d.VIEW_NORMALIZED,dest)
                for (i in dest.indices) dest[i] *= if (i%2==0) outWidth else outHeight
                val matrix=Matrix(); check(matrix.setPolyToPoly(src,0,dest,0,3))
                return Bitmap.createBitmap(outWidth,outHeight,Bitmap.Config.ARGB_8888).also {
                    Canvas(it).drawBitmap(source,matrix,Paint(Paint.FILTER_BITMAP_FLAG))
                }
            } finally { source.recycle() }
        }
    }
}
