package ro.visionassist.core.depth

import com.google.ar.core.Coordinates2d
import com.google.ar.core.Frame
import com.google.ar.core.TrackingState
import com.google.ar.core.exceptions.NotYetAvailableException
import java.nio.ByteOrder

/** Must run on the session owner before the next update(); closes both Android images. */
object RawDepthCapture {
    fun copy(frame:Frame):DepthSnapshot? {
        if (frame.camera.trackingState != TrackingState.TRACKING) return null
        return try {
            frame.acquireRawDepthImage16Bits().use { depth ->
                frame.acquireRawDepthConfidenceImage().use { confidence ->
                    if (depth.width != confidence.width || depth.height != confidence.height ||
                        depth.timestamp != confidence.timestamp) return null
                    val plane=depth.planes[0]; val confPlane=confidence.planes[0]
                    val buffer=plane.buffer.order(ByteOrder.LITTLE_ENDIAN); val confBuffer=confPlane.buffer
                    val values=IntArray(depth.width*depth.height); val scores=ByteArray(values.size)
                    for (y in 0 until depth.height) for (x in 0 until depth.width) {
                        val index=y*depth.width+x
                        values[index]=buffer.getShort(y*plane.rowStride+x*plane.pixelStride).toInt() and 65535
                        scores[index]=confBuffer.get(y*confPlane.rowStride+x*confPlane.pixelStride)
                    }
                    val uv=FloatArray(6)
                    frame.transformCoordinates2d(Coordinates2d.VIEW_NORMALIZED,floatArrayOf(0f,0f,1f,0f,0f,1f),
                        Coordinates2d.TEXTURE_NORMALIZED,uv)
                    DepthSnapshot(depth.width,depth.height,values,scores,depth.timestamp,frame.timestamp,
                        ViewToDepth(uv[0],uv[1],uv[2]-uv[0],uv[3]-uv[1],uv[4]-uv[0],uv[5]-uv[1]))
                        .takeIf { it.isFresh() }
                }
            }
        } catch (_: NotYetAvailableException) { null }
    }
}
