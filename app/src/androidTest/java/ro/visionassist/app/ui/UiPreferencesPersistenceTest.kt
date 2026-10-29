package ro.visionassist.app.ui

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Test
import java.io.File

/** Real disk IO in an isolated file: no app preference reset or mocked DataStore. */
class UiPreferencesPersistenceTest {
    @Test fun onboardingChoiceThemeAndDeveloperSurviveStoreReopening() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = File(context.cacheDir, "ui-${java.util.UUID.randomUUID()}.preferences_pb")
        val firstScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        val first = UiPreferencesStore(context, PreferenceDataStoreFactory.create(scope = firstScope, produceFile = { file }))
        try {
            assertNull(first.preferences.first().layout)
            first.layout(InterfaceLayout.Compact)
            first.theme(ThemeChoice.Dark)
            first.developer(true)
            first.announcements(true)
        } finally { firstScope.coroutineContext[Job]!!.cancelAndJoin() }
        val secondScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        val second = UiPreferencesStore(context, PreferenceDataStoreFactory.create(scope = secondScope, produceFile = { file }))
        try {
            val value = second.preferences.first()
            assertEquals(InterfaceLayout.Compact, value.layout)
            assertEquals(ThemeChoice.Dark, value.theme)
            assertTrue(value.developer)
            assertTrue(value.localAnnouncements)
            second.layout(InterfaceLayout.CameraFocused)
            assertEquals(InterfaceLayout.CameraFocused, second.preferences.first().layout)
        } finally { secondScope.coroutineContext[Job]!!.cancelAndJoin(); file.delete() }
    }
}
