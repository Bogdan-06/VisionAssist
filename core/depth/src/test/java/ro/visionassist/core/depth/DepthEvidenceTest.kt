package ro.visionassist.core.depth

import org.junit.Assert.*
import org.junit.Test
import ro.visionassist.core.ground.GroundBox

class DepthEvidenceTest {
    private fun snapshot(depth:Int=2000, confidence:Int=255)=DepthSnapshot(100,100,IntArray(10_000){depth},
        ByteArray(10_000){confidence.toByte()},1_000_000_000,1_000_000_000,ViewToDepth(0f,0f,1f,0f,0f,1f))
    private val box=GroundBox(.2f,.5f,.8f,.9f)
    @Test fun validSamplesReturnAxialMedianAndCount() {
        val result=DepthEvidence.region(snapshot(),box)!!
        assertEquals(2f,result.medianMeters,0f); assertEquals(49,result.samples)
        assertEquals(0,DepthEvidence.discontinuities(snapshot()).abruptPairs)
    }
    @Test fun missingLowConfidenceOldAndOutOfViewDepthStayUnknown() {
        assertNull(DepthEvidence.region(snapshot(0),box))
        assertNull(DepthEvidence.region(snapshot(confidence=100),box))
        assertNull(DepthEvidence.region(snapshot().copy(frameTimestampNs=1_300_000_000),box))
        assertNull(DepthEvidence.region(snapshot().copy(viewToDepth=ViewToDepth(2f,0f,1f,0f,0f,1f)),box))
    }
    @Test fun mixedSurfacesAreNotAveragedAndDuplicatePixelsDoNotCountAsSupport() {
        val sample=snapshot()
        for (y in 0 until 100) for (x in 50 until 100) sample.millimeters[y*100+x]=4000
        assertNull(DepthEvidence.region(sample,box))
        assertNull(DepthEvidence.region(snapshot(),GroundBox(.5f,.5f,.501f,.501f)))
    }
    @Test fun rotationMappingAndInvalidDepthCannotProduceFakeDiscontinuities() {
        val sample=snapshot().copy(viewToDepth=ViewToDepth(1f,0f,0f,1f,-1f,0f))
        assertEquals(2f,DepthEvidence.region(sample,box)!!.medianMeters,0f)
        assertEquals(0,DepthEvidence.discontinuities(snapshot(0)).validPairs)
    }
}
