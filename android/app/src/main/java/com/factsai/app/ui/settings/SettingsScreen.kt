package com.factsai.app.ui.settings

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factsai.app.ui.theme.*

@Composable
fun SettingsScreen(viewModel: SettingsViewModel) {
    val state by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    var tokenVisible by remember { mutableStateOf(false) }
    var openRouterVisible by remember { mutableStateOf(false) }
    var pexelsVisible by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBg)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "API Keys & Engine Settings",
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
                    text = "All API keys and settings saved securely to encrypted storage.",
                    color = AccentCyan,
                    fontSize = 13.sp,
                    modifier = Modifier.padding(12.dp)
                )
            }
        }

        // --- CARD 1: AI & Media API Keys ---
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardBg)
        ) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Key, contentDescription = null, tint = AccentCyan)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(text = "AI & Media API Keys", fontWeight = FontWeight.SemiBold, fontSize = 16.sp, color = TextPrimary)
                }

                Text(
                    text = "These API keys power the automatic video script writing and copyright-free stock video downloader.",
                    fontSize = 12.sp,
                    color = TextSecondary
                )

                // OpenRouter / Gemini API Key
                OutlinedTextField(
                    value = state.openRouterApiKey,
                    onValueChange = { viewModel.setOpenRouterApiKey(it) },
                    label = { Text("OpenRouter / Gemini API Key (OPENROUTER_API_KEY)") },
                    placeholder = { Text("sk-or-v1-...") },
                    visualTransformation = if (openRouterVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    trailingIcon = {
                        IconButton(onClick = { openRouterVisible = !openRouterVisible }) {
                            Icon(if (openRouterVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility, contentDescription = null)
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Powers Gemini 2.5 Flash for Hindi facts", fontSize = 11.sp, color = TextSecondary)
                    TextButton(onClick = {
                        val browserIntent = Intent(Intent.ACTION_VIEW, Uri.parse("https://openrouter.ai/keys"))
                        context.startActivity(browserIntent)
                    }) {
                        Text("Get Free Key", fontSize = 12.sp, color = AccentCyan)
                    }
                }

                // Pexels API Key
                OutlinedTextField(
                    value = state.pexelsApiKey,
                    onValueChange = { viewModel.setPexelsApiKey(it) },
                    label = { Text("Pexels API Key (PEXELS_API_KEY)") },
                    placeholder = { Text("Enter 56-character Pexels Key") },
                    visualTransformation = if (pexelsVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    trailingIcon = {
                        IconButton(onClick = { pexelsVisible = !pexelsVisible }) {
                            Icon(if (pexelsVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility, contentDescription = null)
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Powers 4K/HD background stock footage", fontSize = 11.sp, color = TextSecondary)
                    TextButton(onClick = {
                        val browserIntent = Intent(Intent.ACTION_VIEW, Uri.parse("https://www.pexels.com/api/"))
                        context.startActivity(browserIntent)
                    }) {
                        Text("Get Free Key", fontSize = 12.sp, color = AccentCyan)
                    }
                }

                // YouTube OAuth Token
                OutlinedTextField(
                    value = state.youtubeTokenJson,
                    onValueChange = { viewModel.setYoutubeTokenJson(it) },
                    label = { Text("YouTube Token JSON (YOUTUBE_TOKEN_JSON)") },
                    placeholder = { Text("Paste authorized token JSON or configure in Channel tab") },
                    minLines = 2,
                    maxLines = 4,
                    modifier = Modifier.fillMaxWidth()
                )

                // Copy Secrets helper button
                OutlinedButton(
                    onClick = {
                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        val secretsGuide = """
# Add these 3 secrets to your GitHub Repo -> Settings -> Secrets and variables -> Actions:
1. OPENROUTER_API_KEY = ${state.openRouterApiKey.ifEmpty { "<paste_key>" }}
2. PEXELS_API_KEY = ${state.pexelsApiKey.ifEmpty { "<paste_key>" }}
3. YOUTUBE_TOKEN_JSON = ${state.youtubeTokenJson.ifEmpty { "<paste_token_json>" }}
                        """.trimIndent()
                        clipboard.setPrimaryClip(ClipData.newPlainText("FACTS-AI-Secrets", secretsGuide))
                        Toast.makeText(context, "Copied GitHub Secrets guide to clipboard!", Toast.LENGTH_SHORT).show()
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.ContentCopy, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Copy GitHub Secrets Formatter")
                }
            }
        }

        // --- CARD 2: GitHub Engine Connection ---
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardBg)
        ) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.CloudSync, contentDescription = null, tint = AccentCyan)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(text = "GitHub Runner Connection", fontWeight = FontWeight.SemiBold, fontSize = 16.sp, color = TextPrimary)
                }

                OutlinedTextField(
                    value = state.repoOwner,
                    onValueChange = { viewModel.setRepoOwner(it) },
                    label = { Text("GitHub Username / Repo Owner") },
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

        // --- CARD 3: Video Default Preferences ---
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
            Icon(Icons.Default.Save, contentDescription = null, tint = DarkBg)
            Spacer(modifier = Modifier.width(8.dp))
            Text("SAVE ALL API KEYS & SETTINGS", fontWeight = FontWeight.Bold)
        }
    }
}
