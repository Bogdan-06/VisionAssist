package ro.visionassist.core.ground

import android.content.Context
import android.graphics.Bitmap
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

/** At most one copied frame in flight, no queue. Close may race a producer during lifecycle teardown. */
class GroundWorker(context: Context, private val onError: (GroundFailure) -> Unit) : AutoCloseable {
    private val executor = Executors.newSingleThreadExecutor { Thread(it,"VisionAssist-ground") }
    private val closed = AtomicBoolean(false)
    private val busy = AtomicBoolean(true)
    private val failed = AtomicBoolean(false)
    private var detector: GroundHazardDetector? = null
    private var lastAccepted = Long.MIN_VALUE // producer only
    private val offered = AtomicLong(); private val processed = AtomicLong()
    private val skippedBusy = AtomicLong(); private val skippedThrottle = AtomicLong()

    init {
        executor.execute {
            try { if (!closed.get()) detector = GroundHazardDetector(context.applicationContext) }
            catch (_: Exception) { fail(GroundFailure.Model) }
            catch (_: LinkageError) { fail(GroundFailure.Model) }
            finally { busy.set(false) }
        }
    }

    /** Copies pixels BEFORE MediaPipe takes ownership of the same upright source bitmap. */
    @Synchronized fun offer(bitmap: Bitmap, receivedAtMs: Long, onResult: (GroundFrame, GroundMetrics) -> Unit) {
        if (closed.get() || failed.get()) return    
        offered.incrementAndGet()
        if (lastAccepted != Long.MIN_VALUE && receivedAtMs-lastAccepted < 400) { skippedThrottle.incrementAndGet(); return }
        if (!busy.compareAndSet(false,true)) { skippedBusy.incrementAndGet(); return }
        val copy = try { bitmap.copy(Bitmap.Config.ARGB_8888,false) }
            catch (_: Exception) { busy.set(false); return }
        if (copy == null) { busy.set(false); return }
        lastAccepted = receivedAtMs
        executor.execute {
            try {
                if (!closed.get() && !failed.get()) {
                    val result = detector?.detect(copy,receivedAtMs) ?: return@execute
                    processed.incrementAndGet()
                    if (!closed.get()) onResult(result,GroundMetrics(offered.get(),processed.get(),skippedBusy.get(),
                        skippedThrottle.get(),result.inferenceMs,result.processingMs))
                }
            } catch (_: Exception) { fail(GroundFailure.Inference) }
            catch (_: LinkageError) { fail(GroundFailure.Inference) }
            finally { copy.recycle(); busy.set(false) }
        }
    }

    private fun fail(reason: GroundFailure) { failed.set(true); if (!closed.get()) onError(reason) }
    @Synchronized override fun close() {
        if (closed.compareAndSet(false,true)) {
            executor.execute { detector?.close(); detector = null }
            executor.shutdown()
        }
    }
}
