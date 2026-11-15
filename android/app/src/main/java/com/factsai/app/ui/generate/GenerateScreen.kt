package com.factsai.app.ui.generate

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factsai.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GenerateScreen(viewModel: GenerateViewModel) {
    val state by viewModel.uiState.collectAsState()
    var categoryExpanded by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBg)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "Generate Video",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            color = AccentGold
        )

        // Status Feedback
        if (state.successMessage != null) {
            Surface(
                color = SuccessGreen.copy(alpha = 0.2f),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = state.successMessage ?: "",
                    color = SuccessGreen,
                    fontSize = 13.sp,
                    modifier = Modifier.padding(12.dp)
                )
            }
        }
        if (state.errorMessage != null) {
            Surface(
                color = ErrorRed.copy(alpha = 0.2f),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = state.errorMessage ?: "",
                    color = ErrorRed,
                    fontSize = 13.sp,
                    modifier = Modifier.padding(12.dp)
                )
            }
        }

        // Topic Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardBg)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(text = "1. Topic Definition", fontWeight = FontWeight.SemiBold, fontSize = 16.sp, color = TextPrimary)
                Spacer(modifier = Modifier.height(10.dp))

                OutlinedTextField(
                    value = state.topic,
                    onValueChange = { viewModel.setTopic(it) },
                    label = { Text("Custom Video Topic (Optional)") },
                    placeholder = { Text("e.g. Why Venus is hotter than Mercury") },
                    enabled = !state.autoDiscoverTrend,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary,
                        focusedBorderColor = AccentGold,
                        unfocusedBorderColor = CardBorder
                    )
                )

                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.clickable { viewModel.setAutoDiscoverTrend(!state.autoDiscoverTrend) }
                ) {
                    Checkbox(
                        checked = state.autoDiscoverTrend,
                        onCheckedChange = { viewModel.setAutoDiscoverTrend(it) },
                        colors = CheckboxDefaults.colors(checkedColor = AccentGold)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Auto-discover live trending science topics via TrendFinder",
                        fontSize = 13.sp,
                        color = TextSecondary
                    )
                }
            }
        }

        // Category Selection Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardBg)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(text = "2. Video Niche / Category", fontWeight = FontWeight.SemiBold, fontSize = 16.sp, color = TextPrimary)
                Spacer(modifier = Modifier.height(10.dp))

                ExposedDropdownMenuBox(
                    expanded = categoryExpanded,
                    onExpandedChange = { categoryExpanded = !categoryExpanded }
                ) {
                    OutlinedTextField(
                        value = state.selectedCategory?.name ?: "Select Category",
                        onValueChange = {},
                        readOnly = true,
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = categoryExpanded) },
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
                        expanded = categoryExpanded,
                        onDismissRequest = { categoryExpanded = false }
                    ) {
                        state.availableCategories.forEach { category ->
                            DropdownMenuItem(
                                text = {
                                    Column {
                                        Text(text = category.name, fontWeight = FontWeight.Bold)
                                        Text(text = category.description, fontSize = 11.sp, color = TextSecondary)
                                    }
                                },
                                onClick = {
                                    viewModel.setSelectedCategory(category)
                                    categoryExpanded = false
                                }
                            )
                        }
                    }
                }
            }
        }

        // Configuration Card (Format, Privacy, Voice)
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardBg)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(text = "3. Video & Upload Parameters", fontWeight = FontWeight.SemiBold, fontSize = 16.sp, color = TextPrimary)
                Spacer(modifier = Modifier.height(12.dp))

                // Format Selector
                Text(text = "Format:", fontSize = 13.sp, color = TextSecondary)
                Spacer(modifier = Modifier.height(4.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = state.format == "short",
                        onClick = { viewModel.setFormat("short") },
                        label = { Text("Short (9:16 Vertical)") }
                    )
                    FilterChip(
                        selected = state.format == "long",
                        onClick = { viewModel.setFormat("long") },
                        label = { Text("Long (16:9 Standard)") }
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))
                // Privacy Selector
                Text(text = "Publishing Privacy (Testing Default: Private):", fontSize = 13.sp, color = TextSecondary)
                Spacer(modifier = Modifier.height(4.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = state.privacy == "private",
                        onClick = { viewModel.setPrivacy("private") },
                        label = { Text("Private") }
                    )
                    FilterChip(
                        selected = state.privacy == "unlisted",
                        onClick = { viewModel.setPrivacy("unlisted") },
                        label = { Text("Unlisted") }
                    )
                    FilterChip(
                        selected = state.privacy == "public",
                        onClick = { viewModel.setPrivacy("public") },
                        label = { Text("Public") }
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))
                // Voice Selector
                Text(text = "Edge TTS Hindi Voice:", fontSize = 13.sp, color = TextSecondary)
                Spacer(modifier = Modifier.height(4.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = state.voice == "hi-IN-MadhurNeural",
                        onClick = { viewModel.setVoice("hi-IN-MadhurNeural") },
                        label = { Text("Madhur (Male)") }
                    )
                    FilterChip(
                        selected = state.voice == "hi-IN-SwaraNeural",
                        onClick = { viewModel.setVoice("hi-IN-SwaraNeural") },
                        label = { Text("Swara (Female)") }
                    )
                }
            }
        }

        // Dispatch Button
        Button(
            onClick = { viewModel.dispatchGeneration() },
            enabled = !state.isDispatching,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(10.dp),
            colors = ButtonDefaults.buttonColors(containerColor = AccentGold, contentColor = DarkBg)
        ) {
            if (state.isDispatching) {
                CircularProgressIndicator(modifier = Modifier.size(20.dp), color = DarkBg, strokeWidth = 2.dp)
                Spacer(modifier = Modifier.width(8.dp))
                Text(text = "DISPATCHING WORKFLOW...", fontWeight = FontWeight.Bold)
            } else {
                Icon(Icons.Default.Send, contentDescription = null, tint = DarkBg)
                Spacer(modifier = Modifier.width(8.dp))
                Text(text = "LAUNCH VIDEO GENERATION", fontWeight = FontWeight.Bold, fontSize = 15.sp)
            }
        }
    }
}
