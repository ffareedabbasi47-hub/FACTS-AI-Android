package com.factsai.app.ui.channel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.factsai.app.data.model.ChannelInfo
import com.factsai.app.data.repository.VideoRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ChannelUiState(
    val channelInfo: ChannelInfo = ChannelInfo(),
    val tokenJsonInput: String = "",
    val channelNameInput: String = "",
    val channelIdInput: String = "",
    val isTesting: Boolean = false,
    val testSuccessMessage: String? = null,
    val errorMessage: String? = null,
    val isSavedSuccess: Boolean = false,
    val showGuideDialog: Boolean = false
)

class ChannelViewModel(
    private val repository: VideoRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChannelUiState())
    val uiState: StateFlow<ChannelUiState> = _uiState.asStateFlow()

    init {
        loadChannel()
    }

    fun loadChannel() {
        val info = repository.getChannelInfo()
        val apiKeys = repository.getApiKeysConfig()
        _uiState.value = _uiState.value.copy(
            channelInfo = info,
            tokenJsonInput = apiKeys.youtubeTokenJson,
            channelNameInput = info.channelName.takeIf { it != "Authorized YouTube Channel" && it != "Not Connected" } ?: "",
            channelIdInput = info.channelId
        )
    }

    fun onTokenJsonChange(text: String) {
        _uiState.value = _uiState.value.copy(tokenJsonInput = text, isSavedSuccess = false, errorMessage = null)
    }

    fun onChannelNameChange(text: String) {
        _uiState.value = _uiState.value.copy(channelNameInput = text, isSavedSuccess = false)
    }

    fun onChannelIdChange(text: String) {
        _uiState.value = _uiState.value.copy(channelIdInput = text, isSavedSuccess = false)
    }

    fun saveChannel() {
        val token = _uiState.value.tokenJsonInput.trim()
        val name = _uiState.value.channelNameInput.trim().ifEmpty { "Connected YouTube Channel" }
        val id = _uiState.value.channelIdInput.trim()

        if (token.isEmpty()) {
            _uiState.value = _uiState.value.copy(errorMessage = "Please paste your YOUTUBE_TOKEN_JSON or OAuth credentials.")
            return
        }

        repository.saveChannelInfo(name, id, token)
        val updatedInfo = repository.getChannelInfo()
        _uiState.value = _uiState.value.copy(
            channelInfo = updatedInfo,
            isSavedSuccess = true,
            errorMessage = null,
            testSuccessMessage = "YouTube Channel credentials saved successfully!"
        )
    }

    fun disconnectChannel() {
        repository.disconnectChannel()
        loadChannel()
        _uiState.value = _uiState.value.copy(
            testSuccessMessage = "Channel disconnected.",
            errorMessage = null
        )
    }

    fun toggleGuide(show: Boolean) {
        _uiState.value = _uiState.value.copy(showGuideDialog = show)
    }

    fun clearMessages() {
        _uiState.value = _uiState.value.copy(errorMessage = null, testSuccessMessage = null, isSavedSuccess = false)
    }
}
