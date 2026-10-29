package ro.visionassist.core.depth

import ro.visionassist.core.ground.GroundBox
import kotlin.math.abs
import kotlin.math.max

/** Affine conversion copied from ARCore's current frame, never guessed from aspect ratios. */
data class ViewToDepth(val originX: Float,val originY: Float,val xX: Float,val xY: Float,val yX: Float,val yY: Float) {
    fun map(x:Float,y:Float) = (originX+x*xX+y*yX) to (originY+x*xY+y*yY)
}
data class DepthSnapshot(val width:Int,val height:Int,val millimeters:IntArray,val confidence:ByteArray,
    val timestampNs:Long,val frameTimestampNs:Long,val viewToDepth:ViewToDepth) {
    init { require(width > 0 && height > 0 && millimeters.size == width*height && confidence.size == width*height) }
    fun isFresh():Boolean = timestampNs > 0 && frameTimestampNs >= timestampNs && frameTimestampNs-timestampNs <= 200_000_000L
    fun index(x:Float,y:Float):Int? {
        val (u,v)=viewToDepth.map(x,y)
        if (!u.isFinite() || !v.isFinite() || u !in 0f..<1f || v !in 0f..<1f) return null
        return (v*height).toInt()*width+(u*width).toInt()
    }
    fun validMillimeters(index:Int):Int? {
        val value=millimeters[index]
        return value.takeIf { it in 500..8_000 && (confidence[index].toInt() and 255) >= 153 }
    }
}

/** Axial depth to observed pixels INSIDE a candidate, not walking distance or pothole depth. */
data class RegionDepth(val medianMeters:Float,val lowerQuartileMeters:Float,val upperQuartileMeters:Float,val samples:Int)
data class DiscontinuityDiagnostic(val validPairs:Int,val abruptPairs:Int)

object DepthEvidence {
    fun region(snapshot:DepthSnapshot, box:GroundBox):RegionDepth? {
        if (!snapshot.isFresh() || box.right <= box.left || box.bottom <= box.top) return null
        val indices=mutableSetOf<Int>()
        // Central half of the box limits background contamination; still not an instance mask.
        for (y in 0..6) for (x in 0..6) {
            val px=box.left+(box.right-box.left)*(.25f+x/12f)
            val py=box.top+(box.bottom-box.top)*(.25f+y/12f)
            snapshot.index(px,py)?.let { indices += it }
        }
        val values=indices.mapNotNull(snapshot::validMillimeters).sorted()
        if (values.size < 9 || values.size < indices.size*.5f) return null
        val median=values[values.size/2]; val lower=values[values.size/4]; val upper=values[values.size*3/4]
        if (upper-lower > median*.2f) return null // Mixed surfaces: report unknown instead of averaging them.
        return RegionDepth(median/1000f,lower/1000f,upper/1000f,values.size)
    }

    /** Research diagnostic only. Perspective, occlusion and slopes also cause z jumps. */
    fun discontinuities(snapshot:DepthSnapshot):DiscontinuityDiagnostic {
        if (!snapshot.isFresh()) return DiscontinuityDiagnostic(0,0)
        var pairs=0; var abrupt=0
        for (row in 0 until 10) for (column in 0 until 10) {
            val x=.25f+column*.05f; val y=.5f+row*.045f
            val a=snapshot.index(x,y)?.let(snapshot::validMillimeters) ?: continue
            val b=snapshot.index(x,y+.035f)?.let(snapshot::validMillimeters) ?: continue
            pairs++
            if (abs(a-b)>max(200f,minOf(a,b)*.15f)) abrupt++
        }
        return DiscontinuityDiagnostic(pairs,abrupt)
    }
}
