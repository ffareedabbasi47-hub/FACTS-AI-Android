package com.factsai.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.factsai.app.data.local.PreferencesManager
import com.factsai.app.data.model.AppSettings
import com.factsai.app.data.repository.VideoRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class SettingsUiState(
    val repoOwner: String = "",
    val repoName: String = "",
    val branch: String = "",
    val githubToken: String = "",
    val openRouterApiKey: String = "",
    val pexelsApiKey: String = "",
    val youtubeTokenJson: String = "",
    val defaultFormat: String = "short",
    val defaultPrivacy: String = "private",
    val defaultVoice: String = "hi-IN-MadhurNeural",
    val isTestingConnection: Boolean = false,
    val connectionSuccessMessage: String? = null,
    val errorMessage: String? = null,
    val isSaved: Boolean = false
)

class SettingsViewModel(
    private val repository: VideoRepository,
    private val preferencesManager: PreferencesManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        loadSettings()
    }

    fun loadSettings() {
        val s = preferencesManager.getSettings()
        _uiState.value = _uiState.value.copy(
            repoOwner = s.repoOwner,
            repoName = s.repoName,
            branch = s.branch,
            githubToken = s.githubToken,
            openRouterApiKey = s.openRouterApiKey,
            pexelsApiKey = s.pexelsApiKey,
            youtubeTokenJson = s.youtubeTokenJson,
            defaultFormat = s.defaultFormat,
            defaultPrivacy = s.defaultPrivacy,
            defaultVoice = s.defaultVoice,
            isSaved = false
        )
    }

    fun setRepoOwner(owner: String) { _uiState.value = _uiState.value.copy(repoOwner = owner, isSaved = false) }
    fun setRepoName(name: String) { _uiState.value = _uiState.value.copy(repoName = name, isSaved = false) }
    fun setBranch(branch: String) { _uiState.value = _uiState.value.copy(branch = branch, isSaved = false) }
    fun setGithubToken(token: String) { _uiState.value = _uiState.value.copy(githubToken = token, isSaved = false) }
    fun setOpenRouterApiKey(key: String) { _uiState.value = _uiState.value.copy(openRouterApiKey = key, isSaved = false) }
    fun setPexelsApiKey(key: String) { _uiState.value = _uiState.value.copy(pexelsApiKey = key, isSaved = false) }
    fun setYoutubeTokenJson(json: String) { _uiState.value = _uiState.value.copy(youtubeTokenJson = json, isSaved = false) }
    fun setDefaultFormat(format: String) { _uiState.value = _uiState.value.copy(defaultFormat = format, isSaved = false) }
    fun setDefaultPrivacy(privacy: String) { _uiState.value = _uiState.value.copy(defaultPrivacy = privacy, isSaved = false) }
    fun setDefaultVoice(voice: String) { _uiState.value = _uiState.value.copy(defaultVoice = voice, isSaved = false) }

    fun saveSettings() {
        val current = _uiState.value
        val existing = preferencesManager.getSettings()
        val settings = AppSettings(
            repoOwner = current.repoOwner.trim(),
            repoName = current.repoName.trim(),
            branch = current.branch.trim(),
            githubToken = current.githubToken.trim(),
            openRouterApiKey = current.openRouterApiKey.trim(),
            pexelsApiKey = current.pexelsApiKey.trim(),
            youtubeTokenJson = current.youtubeTokenJson.trim(),
            youtubeChannelName = existing.youtubeChannelName,
            youtubeChannelId = existing.youtubeChannelId,
            defaultFormat = current.defaultFormat,
            defaultPrivacy = current.defaultPrivacy,
            defaultVoice = current.defaultVoice,
            globalAiInstructions = preferencesManager.getGlobalAiInstructions()
        )
        preferencesManager.saveSettings(settings)
        _uiState.value = _uiState.value.copy(isSaved = true, errorMessage = null)
    }

    fun testConnection() {
        saveSettings()
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isTestingConnection = true, connectionSuccessMessage = null, errorMessage = null)
            val result = repository.testConnection()
            if (result.isSuccess) {
                val repo = result.getOrNull()
                _uiState.value = _uiState.value.copy(
                    isTestingConnection = false,
                    connectionSuccessMessage = "Successfully connected to ${repo?.fullName}! (Public: ${!repo!!.isPrivate})",
                    errorMessage = null
                )
            } else {
                _uiState.value = _uiState.value.copy(
                    isTestingConnection = false,
                    connectionSuccessMessage = null,
                    errorMessage = result.exceptionOrNull()?.message ?: "Connection failed"
                )
            }
        }
    }
}
