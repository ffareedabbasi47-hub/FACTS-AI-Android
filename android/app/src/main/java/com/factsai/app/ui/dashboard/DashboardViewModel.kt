package com.factsai.app.ui.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.factsai.app.data.local.PreferencesManager
import com.factsai.app.data.model.WorkflowRun
import com.factsai.app.data.repository.VideoRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class DashboardUiState(
    val isLoading: Boolean = false,
    val isConnected: Boolean = false,
    val repoName: String = "",
    val latestRun: WorkflowRun? = null,
    val totalVideos: Int = 0,
    val errorMessage: String? = null
)

class DashboardViewModel(
    private val repository: VideoRepository,
    private val preferencesManager: PreferencesManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        refreshDashboard()
    }

    fun refreshDashboard() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            val settings = preferencesManager.getSettings()
            _uiState.value = _uiState.value.copy(repoName = "${settings.repoOwner}/${settings.repoName}")

            val connResult = repository.testConnection()
            val isConn = connResult.isSuccess

            val runResult = repository.getLatestWorkflowRun()
            val latestRun = runResult.getOrNull()

            val histResult = repository.getVideoHistory()
            val totalVideos = histResult.getOrNull()?.size ?: 0

            val errorMsg = if (!isConn && settings.githubToken.isNotBlank()) {
                connResult.exceptionOrNull()?.message
            } else null

            _uiState.value = _uiState.value.copy(
                isLoading = false,
                isConnected = isConn,
                latestRun = latestRun,
                totalVideos = totalVideos,
                errorMessage = errorMsg
            )
        }
    }
}
