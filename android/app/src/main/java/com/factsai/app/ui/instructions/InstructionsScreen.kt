package com.factsai.app.ui.instructions

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factsai.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InstructionsScreen(viewModel: InstructionsViewModel) {
    val state by viewModel.uiState.collectAsState()
    var categoryDropdownExpanded by remember { mutableStateOf(false) }

    var customName by remember { mutableStateOf("") }
    var customDesc by remember { mutableStateOf("") }
    var customInst by remember { mutableStateOf("") }

    if (state.showAddDialog) {
        AlertDialog(
            onDismissRequest = { viewModel.setShowAddDialog(false) },
            title = { Text("Create Custom Category", color = AccentGold, fontWeight = FontWeight.Bold) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(
                        value = customName,
                        onValueChange = { customName = it },
                        label = { Text("Category Name") },
                        placeholder = { Text("e.g. Ancient Indian Metallurgy") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = customDesc,
                        onValueChange = { customDesc = it },
                        label = { Text("Description") },
                        placeholder = { Text("Historical technologies and scientific monuments") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = customInst,
                        onValueChange = { customInst = it },
                        label = { Text("Niche AI Prompt Instructions") },
                        placeholder = { Text("Highlight archaeological accuracy and dates") },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (customName.isNotBlank()) {
                            viewModel.addCustomCategory(customName, customDesc, customInst)
                            customName = ""
                            customDesc = ""
                            customInst = ""
                            viewModel.setShowAddDialog(false)
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = AccentGold, contentColor = DarkBg)
                ) {
                    Text("Add Category", fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { viewModel.setShowAddDialog(false) }) {
                    Text("Cancel", color = TextSecondary)
                }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBg)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "AI Persona & Instructions",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            color = AccentGold
        )

        if (state.isSaved) {
            Surface(
                color = SuccessGreen.copy(alpha = 0.2f),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = "AI Instructions saved! They will be transmitted on your next video generation.",
                    color = SuccessGreen,
                    fontSize = 13.sp,
                    modifier = Modifier.padding(12.dp)
                )
            }
        }

        // Global Instructions Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardBg)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "Global AI Instructions (All Categories)",
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 16.sp,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = "Define the overall tone, vocabulary persona, and style across all generated videos.",
                    fontSize = 12.sp,
                    color = TextSecondary
                )
                Spacer(modifier = Modifier.height(12.dp))

                OutlinedTextField(
                    value = state.globalInstructions,
                    onValueChange = { viewModel.setGlobalInstructions(it) },
                    placeholder = { Text("e.g. Speak with enthusiasm and suspense. Use relatable Indian analogies. Avoid academic jargon.") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 4,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = AccentGold,
                        unfocusedBorderColor = CardBorder
                    )
                )
            }
        }

        // Category-Specific Instructions Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardBg)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Category Instructions",
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 16.sp,
                        color = TextPrimary
                    )
                    IconButton(onClick = { viewModel.setShowAddDialog(true) }) {
                        Icon(Icons.Default.Add, contentDescription = "Add Category", tint = AccentGold)
                    }
                }

                // Dropdown to select category
                ExposedDropdownMenuBox(
                    expanded = categoryDropdownExpanded,
                    onExpandedChange = { categoryDropdownExpanded = !categoryDropdownExpanded }
                ) {
                    OutlinedTextField(
                        value = state.selectedCategory?.name ?: "Select Category",
                        onValueChange = {},
                        readOnly = true,
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = categoryDropdownExpanded) },
                        modifier = Modifier
                            .menuAnchor()
                            .fillMaxWidth(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary,
                            focusedBorderColor = AccentGold,
                            unfocusedBorderColor = CardBorder
                        )
                    )
                    ExposedDropdownMenu(
                        expanded = categoryDropdownExpanded,
                        onDismissRequest = { categoryDropdownExpanded = false }
                    ) {
                        state.categories.forEach { category ->
                            DropdownMenuItem(
                                text = {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(text = category.name)
                                        if (category.isCustom) {
                                            Text(text = "CUSTOM", fontSize = 10.sp, color = AccentCyan)
                                        }
                                    }
                                },
                                onClick = {
                                    viewModel.selectCategory(category)
                                    categoryDropdownExpanded = false
                                }
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))
                OutlinedTextField(
                    value = state.categoryInstructions,
                    onValueChange = { viewModel.setCategoryInstructions(it) },
                    label = { Text("Instructions for ${state.selectedCategory?.name ?: "Selected Category"}") },
                    placeholder = { Text("Special guidelines for this category...") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = AccentGold,
                        unfocusedBorderColor = CardBorder
                    )
                )

                if (state.selectedCategory?.isCustom == true) {
                    Spacer(modifier = Modifier.height(8.dp))
                    TextButton(
                        onClick = { state.selectedCategory?.let { viewModel.deleteCustomCategory(it.id) } },
                        colors = ButtonDefaults.textButtonColors(contentColor = ErrorRed)
                    ) {
                        Icon(Icons.Default.Delete, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Delete Custom Category", fontSize = 12.sp)
                    }
                }
            }
        }

        // Save Button
        Button(
            onClick = { viewModel.saveAllInstructions() },
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
            shape = RoundedCornerShape(10.dp),
            colors = ButtonDefaults.buttonColors(containerColor = AccentGold, contentColor = DarkBg)
        ) {
            Icon(Icons.Default.Check, contentDescription = null, tint = DarkBg)
            Spacer(modifier = Modifier.width(8.dp))
            Text("SAVE INSTRUCTIONS", fontWeight = FontWeight.Bold, fontSize = 14.sp)
        }
    }
}
