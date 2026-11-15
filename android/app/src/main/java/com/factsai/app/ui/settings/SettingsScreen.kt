package com.factsai.app.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ElectricalServices
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factsai.app.ui.theme.*

@Composable
fun SettingsScreen(viewModel: SettingsViewModel) {
    val state by viewModel.uiState.collectAsState()
    var tokenVisible by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBg)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "Settings & Security",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            color = AccentGold
        )

        if (state.connectionSuccessMessage != null) {
            Surface(
                color = SuccessGreen.copy(alpha = 0.2f),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = state.connectionSuccessMessage ?: "",
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

        if (state.isSaved && state.connectionSuccessMessage == null && state.errorMessage == null) {
            Surface(
                color = AccentCyan.copy(alpha = 0.2f),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = "Settings saved successfully to encrypted local storage.",
                    color = AccentCyan,
                    fontSize = 13.sp,
                    modifier = Modifier.padding(12.dp)
                )
            }
        }

        // GitHub Repository Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardBg)
        ) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(text = "GitHub Engine Connection", fontWeight = FontWeight.SemiBold, fontSize = 16.sp, color = TextPrimary)
                Text(text = "The personal Android APK connects directly to your GitHub repository to trigger runs and fetch history for ₹0.", fontSize = 12.sp, color = TextSecondary)

                OutlinedTextField(
                    value = state.repoOwner,
                    onValueChange = { viewModel.setRepoOwner(it) },
                    label = { Text("Repository Owner / Username") },
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = state.repoName,
                    onValueChange = { viewModel.setRepoName(it) },
                    label = { Text("Repository Name") },
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = state.branch,
                    onValueChange = { viewModel.setBranch(it) },
                    label = { Text("Default Branch") },
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = state.githubToken,
                    onValueChange = { viewModel.setGithubToken(it) },
                    label = { Text("GitHub Personal Access Token (PAT)") },
                    placeholder = { Text("github_pat_... or ghp_...") },
                    visualTransformation = if (tokenVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    trailingIcon = {
                        IconButton(onClick = { tokenVisible = !tokenVisible }) {
                            Icon(
                                if (tokenVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                contentDescription = "Toggle Token Visibility"
                            )
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                )

                Text(
                    text = "Security note: Token is stored securely inside Android's EncryptedSharedPreferences and never committed or logged.",
                    fontSize = 11.sp,
                    color = TextSecondary
                )

                Button(
                    onClick = { viewModel.testConnection() },
                    enabled = !state.isTestingConnection,
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AccentCyan.copy(alpha = 0.2f), contentColor = AccentCyan),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    if (state.isTestingConnection) {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp), color = AccentCyan, strokeWidth = 2.dp)
                        Spacer(modifier = Modifier.width(8.dp))
                    } else {
                        Icon(Icons.Default.ElectricalServices, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                    }
                    Text("Test GitHub Connection")
                }
            }
        }

        // Default Preferences Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardBg)
        ) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(text = "App Default Preferences", fontWeight = FontWeight.SemiBold, fontSize = 16.sp, color = TextPrimary)

                Text(text = "Default Format:", fontSize = 13.sp, color = TextSecondary)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = state.defaultFormat == "short",
                        onClick = { viewModel.setDefaultFormat("short") },
                        label = { Text("Short (9:16)") }
                    )
                    FilterChip(
                        selected = state.defaultFormat == "long",
                        onClick = { viewModel.setDefaultFormat("long") },
                        label = { Text("Long (16:9)") }
                    )
                }

                Text(text = "Default Upload Privacy:", fontSize = 13.sp, color = TextSecondary)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = state.defaultPrivacy == "private",
                        onClick = { viewModel.setDefaultPrivacy("private") },
                        label = { Text("Private (Testing)") }
                    )
                    FilterChip(
                        selected = state.defaultPrivacy == "unlisted",
                        onClick = { viewModel.setDefaultPrivacy("unlisted") },
                        label = { Text("Unlisted") }
                    )
                    FilterChip(
                        selected = state.defaultPrivacy == "public",
                        onClick = { viewModel.setDefaultPrivacy("public") },
                        label = { Text("Public") }
                    )
                }
            }
        }

        Button(
            onClick = { viewModel.saveSettings() },
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
            shape = RoundedCornerShape(10.dp),
            colors = ButtonDefaults.buttonColors(containerColor = AccentGold, contentColor = DarkBg)
        ) {
            Icon(Icons.Default.Check, contentDescription = null, tint = DarkBg)
            Spacer(modifier = Modifier.width(8.dp))
            Text("SAVE SETTINGS", fontWeight = FontWeight.Bold)
        }
    }
}
