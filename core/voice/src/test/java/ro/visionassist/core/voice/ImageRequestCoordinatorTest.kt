package ro.visionassist.core.voice

import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test

/** Exercises the production consent/capture boundary with controlled asynchronous input.
 * The byte fixtures are transport-test data, not simulated production camera detections.
 */
class ImageRequestCoordinatorTest {
    private class Harness(timeout: Long = 3_000) {
        var allowed = true
        var requested = false
        var busy = false
        var successes = 0
        var errors = 0
        var beforeCommit: () -> Unit = {}
        var afterCommit: () -> Unit = {}
        val uploads = mutableListOf<Pair<String?, List<Byte>>>()
        val declines = mutableListOf<Pair<String, String>>()
        val gate = ImageRequestCoordinator(
            canSend = { allowed },
            dispatch = { id, bytes, commit ->
                beforeCommit()
                if (commit { uploads += id to bytes.toList(); true }) afterCommit()
            },
            decline = { id, reason -> declines += id to reason },
            changed = { request, working -> requested = request; busy = working },
            sent = { successes++ }, captureFailed = { errors++ }, timeoutMs = timeout
        )
    }

    @Test fun toolRequestWaitsForExplicitConsentAndManualPhotoNeedsNoTool() = runBlocking {
        val h = Harness()
        assertTrue(h.gate.request("tool"))
        assertTrue(h.requested); assertTrue(h.uploads.isEmpty())
        h.gate.submit { byteArrayOf(1) }
        h.gate.submit { byteArrayOf(2) }
        assertEquals(listOf("tool", null), h.uploads.map { it.first })
        assertEquals(2, h.successes)
        assertFalse(h.requested); assertFalse(h.busy)
    }

    @Test fun declineDuringNonCooperativeCapturePreventsUploadIncludingManualPhotos() = runBlocking {
        for (tool in listOf<String?>("tool", null)) {
            val h = Harness(); tool?.let { h.gate.request(it) }
            val entered = CompletableDeferred<Unit>(); val release = CompletableDeferred<Unit>()
            val task = launch { h.gate.submit {
                entered.complete(Unit)
                withContext(NonCancellable) { release.await(); byteArrayOf(1) }
            } }
            entered.await()
            h.gate.cancel("user_declined")
            assertFalse(h.requested); assertFalse(h.busy)
            release.complete(Unit); task.join()
            assertTrue(h.uploads.isEmpty())
            assertEquals(if (tool == null) emptyList() else listOf(tool to "user_declined"), h.declines)
        }
    }

    @Test fun oldCompletionCannotAcknowledgeReplacementOrClearItsBusyStateEvenWithReusedToolId() = runBlocking {
        val h = Harness(); h.gate.request("same-id")
        val enteredA = CompletableDeferred<Unit>(); val releaseA = CompletableDeferred<Unit>()
        val old = launch { h.gate.submit {
            enteredA.complete(Unit)
            withContext(NonCancellable) { releaseA.await(); byteArrayOf(1) }
        } }
        enteredA.await(); h.gate.cancel("user_declined")
        assertTrue(h.gate.request("same-id"))
        val enteredB = CompletableDeferred<Unit>(); val releaseB = CompletableDeferred<Unit>()
        val fresh = launch { h.gate.submit { enteredB.complete(Unit); releaseB.await(); byteArrayOf(2) } }
        enteredB.await(); releaseA.complete(Unit); old.join()
        assertTrue(h.requested); assertTrue(h.busy); assertTrue(h.uploads.isEmpty())
        assertEquals(1, h.declines.size)
        releaseB.complete(Unit); fresh.join()
        assertEquals(listOf("same-id" to listOf<Byte>(2)), h.uploads)
    }

    @Test fun oldFailureCannotDeclineANewerUnconfirmedRequest() = runBlocking {
        val h = Harness(); h.gate.request("A")
        val entered = CompletableDeferred<Unit>(); val release = CompletableDeferred<Unit>()
        val task = launch { h.gate.submit {
            entered.complete(Unit)
            withContext(NonCancellable) { release.await(); error("late encoder failure") }
        } }
        entered.await(); h.gate.cancel("user_declined"); h.gate.request("B")
        release.complete(Unit); task.join()
        assertTrue(h.requested); assertEquals(listOf("A" to "user_declined"), h.declines)
        assertEquals(0, h.errors)
        h.gate.submit { byteArrayOf(2) }
        assertEquals("B", h.uploads.single().first)
    }

    @Test fun sessionEndReconnectProviderCloseAndCameraStopRevokeCaptures() = runBlocking {
        for (reason in listOf("session_ended", "network_lost", "provider_switched", "camera_stopped", "local_warning")) {
            val h = Harness(); h.gate.request("old")
            val entered = CompletableDeferred<Unit>(); val release = CompletableDeferred<Unit>()
            val old = launch { h.gate.submit {
                entered.complete(Unit)
                withContext(NonCancellable) { release.await(); byteArrayOf(1) }
            } }
            entered.await(); h.allowed = false; h.gate.cancel(reason, notify = false)
            h.allowed = true; h.gate.request("new-session")
            release.complete(Unit); old.join()
            assertTrue(h.uploads.isEmpty()); assertTrue(h.requested)
            h.gate.submit { byteArrayOf(2) }
            assertEquals("new-session", h.uploads.single().first)
        }
    }

    @Test fun cancellationOfCallerTimeoutAndCaptureFailureReleaseOnlyTheirOwnApproval() = runBlocking {
        val h = Harness(); h.gate.request("caller")
        val entered = CompletableDeferred<Unit>()
        val task = launch { h.gate.submit { entered.complete(Unit); awaitCancellation() } }
        entered.await(); task.cancelAndJoin()
        assertFalse(h.busy); assertFalse(h.requested); assertTrue(h.uploads.isEmpty())
        assertEquals(listOf("caller" to "capture_cancelled"), h.declines)
        val timed = Harness(timeout = 25); timed.gate.request("timeout")
        val timeoutTask = launch { timed.gate.submit { awaitCancellation() } }
        withTimeout(2_000) { timeoutTask.join() }
        assertFalse(timed.busy); assertEquals(1, timed.errors); assertTrue(timed.uploads.isEmpty())
        h.gate.request("failure"); h.gate.submit { error("test encoder failure") }
        assertFalse(h.busy); assertTrue(h.uploads.isEmpty()); assertEquals(1, h.errors)
    }

    @Test fun duplicateSubmissionAndRemoteCancellationDoNotDispatchTwice() = runBlocking {
        val h = Harness(); h.gate.request("tool")
        val entered = CompletableDeferred<Unit>(); val release = CompletableDeferred<Unit>()
        val task = launch { h.gate.submit { entered.complete(Unit); release.await(); byteArrayOf(1) } }
        entered.await()
        h.gate.submit { error("duplicate capture must not start") }
        assertFalse(h.gate.request("replacement"))
        h.gate.cancelTool("other"); assertTrue(h.busy)
        h.gate.cancelTool("tool"); h.gate.cancelTool("tool")
        release.complete(Unit); task.join()
        assertTrue(h.uploads.isEmpty()); assertTrue(h.declines.isEmpty())
    }

    @Test fun policyIsRecheckedAfterCaptureAndInvalidPayloadNeverReachesSink() = runBlocking {
        val h = Harness(); h.gate.request("tool")
        h.gate.submit { h.allowed = false; byteArrayOf(1) }
        assertTrue(h.uploads.isEmpty()); assertFalse(h.busy)
        for (bytes in listOf(byteArrayOf(), ByteArray(44_001))) {
            val invalid = Harness(); invalid.gate.submit { bytes }
            assertTrue(invalid.uploads.isEmpty()); assertEquals(1, invalid.errors)
        }
    }

    @Test fun declineAfterDispatchDoesNotClaimRecallOrReuseConsent() = runBlocking {
        val h = Harness(); h.gate.request("tool"); h.gate.submit { byteArrayOf(1) }
        h.gate.cancel("user_declined")
        assertEquals(1, h.uploads.size); assertEquals(1, h.successes)
        assertTrue(h.declines.isEmpty())
        h.gate.request("later"); assertEquals(1, h.uploads.size)
    }

    @Test fun cancellationDuringProtocolPreparationIsRecheckedAtActualImageSink() = runBlocking {
        val h = Harness(); h.gate.request("old")
        h.beforeCommit = { h.gate.cancel("user_declined"); h.gate.request("replacement") }
        val cancelled = launch { h.gate.submit { byteArrayOf(1) } }
        cancelled.join()
        assertTrue(h.uploads.isEmpty()); assertTrue(h.requested); assertFalse(h.busy)
        assertEquals(0, h.successes)
        h.beforeCommit = {}; h.gate.submit { byteArrayOf(2) }
        assertEquals("replacement", h.uploads.single().first)
    }

    @Test fun transportFailureAfterImageAcceptanceDoesNotTurnItIntoARecalledPhoto() = runBlocking {
        val h = Harness(); h.gate.request("tool")
        h.afterCommit = { h.allowed = false; h.gate.cancel("session_ended", notify = false) }
        val task = launch { h.gate.submit { byteArrayOf(1) } }
        task.join()
        assertEquals(1, h.uploads.size); assertEquals(1, h.successes)
        assertTrue(h.declines.isEmpty()); assertFalse(h.busy); assertFalse(h.requested)
    }
}
