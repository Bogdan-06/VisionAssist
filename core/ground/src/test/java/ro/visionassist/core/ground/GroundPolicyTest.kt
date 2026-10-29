package ro.visionassist.core.ground

import org.junit.Assert.*
import org.junit.Test

class GroundPolicyTest {
    private val candidate = GroundCandidate(.8f,GroundBox(.4f,.6f,.6f,.85f))
    @Test fun requiresThreeSpatiallyConsistentFreshFramesThenCoolsDown() {
        val policy = GroundWarningPolicy()
        assertNull(policy.observe(listOf(candidate),0,0))
        assertNull(policy.observe(listOf(candidate),400,410))
        assertEquals(candidate,policy.observe(listOf(candidate),800,810))
        assertNull(policy.observe(listOf(candidate),1200,1200))
        assertNull(policy.observe(listOf(candidate),1600,1600))
        assertNull(policy.observe(listOf(candidate),2000,2000))
    }
    @Test fun absenceStalenessAndChangingLocationsBreakEvidence() {
        val policy = GroundWarningPolicy()
        policy.observe(listOf(candidate),0,0)
        policy.observe(listOf(candidate),400,400)
        assertNull(policy.observe(emptyList(),800,800))
        assertNull(policy.observe(listOf(candidate),1200,1200))
        assertNull(policy.observe(listOf(candidate),1600,3000))
        assertNull(policy.observe(listOf(candidate),3000,3000))
        assertNull(policy.observe(listOf(candidate.copy(bounds=GroundBox(.05f,.6f,.3f,.9f))),3400,3400))
        assertNull(policy.observe(listOf(candidate),3800,3800))
    }
    @Test fun oldDuplicateAndNonfiniteScoresCannotProduceWarnings() {
        val policy=GroundWarningPolicy()
        policy.observe(listOf(candidate),1000,1000)
        assertNull(policy.observe(listOf(candidate),1000,1000))
        assertNull(policy.observe(listOf(candidate.copy(confidence=Float.NaN)),1400,1400))
        assertNull(policy.observe(listOf(candidate.copy(confidence=.64f)),1800,1800))
        assertFalse(GroundModelReadiness.WARNINGS_VALIDATED)
    }
    @Test fun decoderReversesLetterboxAndSuppressesOverlappingPeaks() {
        val output=FloatArray(20*20*5)
        fun put(x:Int,y:Int,score:Float,bw:Float,bh:Float) {
            val index=(y*20+x)*5
            listOf(score,.5f,.5f,bw,bh).forEachIndexed { channel,value -> output[index+channel]=value }
        }
        put(10,10,.9f,.2f,.2f)
        put(12,10,.8f,.4f,.2f)
        val result=GroundDecoder.decode(output,640,480,320,240)
        assertEquals(1,result.size)
        assertEquals(.425f,result[0].bounds.left,.0001f)
        assertEquals((168-32-40)/240f,result[0].bounds.top,.0001f)
        assertEquals(.625f,result[0].bounds.right,.0001f)
        output[(10*20+10)*5]=Float.NaN
        assertTrue(GroundDecoder.decode(output,640,480,320,240).all { it.confidence.isFinite() })
    }
    @Test fun paddingOnlyAndInvalidBoxOutputsAreDiscarded() {
        val output=FloatArray(20*20*5)
        output[0]=.9f; output[1]=.5f; output[2]=.5f; output[3]=.02f; output[4]=.02f
        assertTrue(GroundDecoder.decode(output,640,320,320,160).isEmpty())
        output[3]=Float.POSITIVE_INFINITY
        assertTrue(GroundDecoder.decode(output,320,320,320,320).isEmpty())
    }
}
