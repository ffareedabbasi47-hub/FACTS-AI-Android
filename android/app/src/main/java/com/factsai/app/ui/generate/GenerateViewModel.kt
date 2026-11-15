package com.factsai.app.ui.generate

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.factsai.app.data.local.PreferencesManager
import com.factsai.app.data.model.CategoryItem
import com.factsai.app.data.repository.VideoRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class GenerateUiState(
    val topic: String = "",
    val autoDiscoverTrend: Boolean = false,
    val selectedCategory: CategoryItem? = null,
    val availableCategories: List<CategoryItem> = emptyList(),
    val format: String = "short", // short, long
    val privacy: String = "private", // private, unlisted, public
    val voice: String = "hi-IN-MadhurNeural", // hi-IN-MadhurNeural, hi-IN-SwaraNeural
    val isDispatching: Boolean = false,
    val successMessage: String? = null,
    val errorMessage: String? = null
)

class GenerateViewModel(
    private val repository: VideoRepository,
    private val preferencesManager: PreferencesManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(GenerateUiState())
    val uiState: StateFlow<GenerateUiState> = _uiState.asStateFlow()

    init {
        loadSettings()
    }

    fun loadSettings() {
        val settings = preferencesManager.getSettings()
        val categories = repository.getAllCategories()
        _uiState.value = _uiState.value.copy(
            availableCategories = categories,
            selectedCategory = categories.firstOrNull(),
            format = settings.defaultFormat,
            privacy = settings.defaultPrivacy,
            voice = settings.defaultVoice
        )
    }

    fun setTopic(topic: String) {
        _uiState.value = _uiState.value.copy(topic = topic)
    }

    fun setAutoDiscoverTrend(enabled: Boolean) {
        _uiState.value = _uiState.value.copy(autoDiscoverTrend = enabled)
    }

    fun setSelectedCategory(category: CategoryItem) {
        _uiState.value = _uiState.value.copy(selectedCategory = category)
    }

    fun setFormat(format: String) {
        _uiState.value = _uiState.value.copy(format = format)
    }

    fun setPrivacy(privacy: String) {
        _uiState.value = _uiState.value.copy(privacy = privacy)
    }

    fun setVoice(voice: String) {
        _uiState.value = _uiState.value.copy(voice = voice)
    }

    fun dispatchGeneration() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isDispatching = true, successMessage = null, errorMessage = null)
            val currentState = _uiState.value

            val effectiveTopic = if (currentState.autoDiscoverTrend) null else currentState.topic.ifBlank { null }
            val categoryName = currentState.selectedCategory?.name

            // Combine Global AI Instructions and Category Instructions
            val globalInst = preferencesManager.getGlobalAiInstructions().trim()
            val catInst = currentState.selectedCategory?.let { preferencesManager.getCategoryInstructions(it.id).trim() } ?: ""
            val combinedInstructions = buildString {
                if (globalInst.isNotEmpty()) {
                    append("Global Tone: $globalInst. ")
                }
                if (catInst.isNotEmpty()) {
                    append("Category Nuance: $catInst")
                }
            }.trim().ifEmpty { null }

            val result = repository.dispatchVideoGeneration(
                topic = effectiveTopic,
                category = categoryName,
                format = currentState.format,
                privacy = currentState.privacy,
                voice = currentState.voice,
                customInstructions = combinedInstructions
            )

            if (result.isSuccess) {
                _uiState.value = _uiState.value.copy(
                    isDispatching = false,
                    successMessage = "Workflow successfully dispatched to GitHub Actions! Check the Dashboard or History tab for progress.",
                    topic = if (currentState.autoDiscoverTrend) "" else currentState.topic
                )
            } else {
                _uiState.value = _uiState.value.copy(
                    isDispatching = false,
                    errorMessage = result.exceptionOrNull()?.message ?: "Failed to dispatch video generation."
                )
            }
        }
    }
}
