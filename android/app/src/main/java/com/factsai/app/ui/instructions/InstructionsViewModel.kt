package com.factsai.app.ui.instructions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.factsai.app.data.local.PreferencesManager
import com.factsai.app.data.model.CategoryItem
import com.factsai.app.data.repository.VideoRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.UUID

data class InstructionsUiState(
    val globalInstructions: String = "",
    val categories: List<CategoryItem> = emptyList(),
    val selectedCategory: CategoryItem? = null,
    val categoryInstructions: String = "",
    val isSaved: Boolean = false,
    val showAddDialog: Boolean = false
)

class InstructionsViewModel(
    private val repository: VideoRepository,
    private val preferencesManager: PreferencesManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(InstructionsUiState())
    val uiState: StateFlow<InstructionsUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        val global = preferencesManager.getGlobalAiInstructions()
        val allCategories = repository.getAllCategories()
        val initialCategory = allCategories.firstOrNull()
        val catInst = initialCategory?.let { preferencesManager.getCategoryInstructions(it.id).ifEmpty { it.instructions } } ?: ""

        _uiState.value = _uiState.value.copy(
            globalInstructions = global,
            categories = allCategories,
            selectedCategory = initialCategory,
            categoryInstructions = catInst,
            isSaved = false
        )
    }

    fun setGlobalInstructions(instructions: String) {
        _uiState.value = _uiState.value.copy(globalInstructions = instructions, isSaved = false)
    }

    fun selectCategory(category: CategoryItem) {
        val catInst = preferencesManager.getCategoryInstructions(category.id).ifEmpty { category.instructions }
        _uiState.value = _uiState.value.copy(
            selectedCategory = category,
            categoryInstructions = catInst,
            isSaved = false
        )
    }

    fun setCategoryInstructions(instructions: String) {
        _uiState.value = _uiState.value.copy(categoryInstructions = instructions, isSaved = false)
    }

    fun saveAllInstructions() {
        val current = _uiState.value
        preferencesManager.saveGlobalAiInstructions(current.globalInstructions)
        current.selectedCategory?.let {
            preferencesManager.saveCategoryInstructions(it.id, current.categoryInstructions)
        }
        _uiState.value = _uiState.value.copy(isSaved = true)
    }

    fun setShowAddDialog(show: Boolean) {
        _uiState.value = _uiState.value.copy(showAddDialog = show)
    }

    fun addCustomCategory(name: String, description: String, instructions: String) {
        val newCategory = CategoryItem(
            id = "custom_" + UUID.randomUUID().toString().take(8),
            name = name.trim(),
            description = description.trim(),
            instructions = instructions.trim(),
            isCustom = true
        )
        preferencesManager.addCustomCategory(newCategory)
        preferencesManager.saveCategoryInstructions(newCategory.id, newCategory.instructions)
        loadData()
        selectCategory(newCategory)
    }

    fun deleteCustomCategory(categoryId: String) {
        preferencesManager.deleteCustomCategory(categoryId)
        loadData()
    }
}
