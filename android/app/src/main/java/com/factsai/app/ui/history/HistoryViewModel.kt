package com.factsai.app.ui.history

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.factsai.app.data.model.TopicHistoryItem
import com.factsai.app.data.model.WorkflowRun
import com.factsai.app.data.repository.VideoRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class HistoryUiState(
    val isLoading: Boolean = false,
    val items: List<TopicHistoryItem> = emptyList(),
    val latestRun: WorkflowRun? = null,
    val runDiagnosis: String? = null,
    val showDiagnosisDialog: Boolean = false,
    val isDiagnosing: Boolean = false,
    val errorMessage: String? = null
)

class HistoryViewModel(private val repository: VideoRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(HistoryUiState())
    val uiState: StateFlow<HistoryUiState> = _uiState.asStateFlow()

    init {
        loadHistory()
    }

    fun loadHistory() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            val result = repository.getVideoHistory()
            val runResult = repository.getLatestWorkflowRun()
            _uiState.value = _uiState.value.copy(
                isLoading = false,
                items = result.getOrNull() ?: emptyList(),
                latestRun = runResult.getOrNull(),
                errorMessage = if (result.isFailure && runResult.isFailure) result.exceptionOrNull()?.message else null
            )
        }
    }

    fun inspectLatestRun() {
        val run = _uiState.value.latestRun ?: return
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isDiagnosing = true, showDiagnosisDialog = true)
            val diagResult = repository.getRunFailureDiagnosis(run.id)
            _uiState.value = _uiState.value.copy(
                isDiagnosing = false,
                runDiagnosis = diagResult.getOrNull() ?: "Status: ${run.conclusion ?: run.status}"
            )
        }
    }

    fun dismissDiagnosisDialog() {
        _uiState.value = _uiState.value.copy(showDiagnosisDialog = false, runDiagnosis = null)
    }
}
