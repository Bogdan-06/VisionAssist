package ro.visionassist.app.ui

import android.app.Application
import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

enum class InterfaceLayout(val title: String, val description: String) {
    CameraFocused("Cameră în prim-plan", "Previzualizare mare, cu chenare pentru obiectele recunoscute."),
    Compact("Compact", "Previzualizare mică și mai mult spațiu pentru informații și comenzi.")
}
enum class ThemeChoice(val title: String) { System("Ca pe telefon"), Light("Luminoasă"), Dark("Întunecată") }
data class UiPreferences(
    val layout: InterfaceLayout? = null,
    val theme: ThemeChoice = ThemeChoice.System,
    val developer: Boolean = false,
    val localAnnouncements: Boolean = false
)
private val Context.interfaceDataStore by preferencesDataStore("interface_preferences")

/** Single app-scoped DataStore. A missing layout means onboarding has not been completed. */
class UiPreferencesStore(context: Context,
    private val store: androidx.datastore.core.DataStore<androidx.datastore.preferences.core.Preferences> = context.applicationContext.interfaceDataStore) {
    private val layoutKey = stringPreferencesKey("layout")
    private val themeKey = stringPreferencesKey("theme")
    private val developerKey = booleanPreferencesKey("developer")
    private val announcementsKey = booleanPreferencesKey("local_announcements")
    val preferences = store.data.map { values ->
        UiPreferences(
            InterfaceLayout.entries.firstOrNull { it.name == values[layoutKey] },
            ThemeChoice.entries.firstOrNull { it.name == values[themeKey] } ?: ThemeChoice.System,
            values[developerKey] ?: false, values[announcementsKey] ?: false
        )
    }
    suspend fun layout(value: InterfaceLayout) { store.edit { it[layoutKey] = value.name } }
    suspend fun theme(value: ThemeChoice) { store.edit { it[themeKey] = value.name } }
    suspend fun developer(value: Boolean) { store.edit { it[developerKey] = value } }
    suspend fun announcements(value: Boolean) { store.edit { it[announcementsKey] = value } }
}

data class UiPreferencesState(val value: UiPreferences? = null, val error: String? = null, val saving: Boolean = false)

class UiPreferencesViewModel(application: Application) : AndroidViewModel(application) {
    private val store = UiPreferencesStore(application)
    private val mutableState = MutableStateFlow(UiPreferencesState())
    val state = mutableState.asStateFlow()
    private var reader: Job? = null
    init { reload() }
    fun reload() {
        reader?.cancel()
        reader = viewModelScope.launch {
            try { store.preferences.collect { mutableState.value = UiPreferencesState(it) } }
            catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
            catch (_: Exception) { mutableState.value = mutableState.value.copy(error = "Preferințele nu au putut fi citite. Încearcă din nou.") }
        }
    }
    private fun write(block: suspend () -> Unit) {
        viewModelScope.launch {
            mutableState.value = mutableState.value.copy(saving = true, error = null)
            try { block() }
            catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
            catch (_: Exception) { mutableState.value = mutableState.value.copy(error = "Preferința nu a fost salvată. Încearcă din nou.") }
            finally { mutableState.value = mutableState.value.copy(saving = false) }
        }
    }
    fun layout(value: InterfaceLayout) = write { store.layout(value) }
    fun theme(value: ThemeChoice) = write { store.theme(value) }
    fun developer(value: Boolean) = write { store.developer(value) }
    fun announcements(value: Boolean) = write { store.announcements(value) }
}
