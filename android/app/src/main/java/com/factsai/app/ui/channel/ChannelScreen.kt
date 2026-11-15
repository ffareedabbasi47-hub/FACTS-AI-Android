package com.factsai.app.ui.channel

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factsai.app.ui.theme.ElectricBlue
import com.factsai.app.ui.theme.NeonGreen
import com.factsai.app.ui.theme.WarningOrange

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChannelScreen(
    viewModel: ChannelViewModel
) {
    val uiState by viewModel.uiState.collectAsState()
    val scrollState = rememberScrollState()
    val context = LocalContext.current

    LaunchedEffect(Unit) {
        viewModel.loadChannel()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "YouTube Channel",
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                },
                actions = {
                    IconButton(onClick = { viewModel.toggleGuide(true) }) {
                        Icon(Icons.Default.HelpOutline, contentDescription = "Setup Guide", tint = ElectricBlue)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp)
                .verticalScroll(scrollState),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Status Banner
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = if (uiState.channelInfo.isConnected)
                        NeonGreen.copy(alpha = 0.12f)
                    else
                        WarningOrange.copy(alpha = 0.12f)
                ),
                border = BorderStroke(
                    1.dp,
                    if (uiState.channelInfo.isConnected) NeonGreen else WarningOrange
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = if (uiState.channelInfo.isConnected) Icons.Default.CheckCircle else Icons.Default.Warning,
                        contentDescription = null,
                        tint = if (uiState.channelInfo.isConnected) NeonGreen else WarningOrange,
                        modifier = Modifier.size(36.dp)
                    )
                    Spacer(modifier = Modifier.width(16.dp))
                    Column {
                        Text(
                            text = if (uiState.channelInfo.isConnected) "Channel Connected" else "Channel Not Connected",
                            fontWeight = FontWeight.Bold,
                            fontSize = 18.sp,
                            color = if (uiState.channelInfo.isConnected) NeonGreen else WarningOrange
                        )
                        Text(
                            text = if (uiState.channelInfo.isConnected)
                                "Ready to automatically upload generated videos"
                            else
                                "Connect OAuth credentials to enable automated YouTube uploads",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.LightGray
                        )
                    }
                }
            }

            // Messages
            uiState.testSuccessMessage?.let { msg ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = NeonGreen.copy(alpha = 0.15f)),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = msg,
                        color = NeonGreen,
                        modifier = Modifier.padding(12.dp),
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            uiState.errorMessage?.let { err ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.error.copy(alpha = 0.15f)),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = err,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(12.dp),
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            // Channel Details Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text(
                        "Channel Configuration",
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                        color = ElectricBlue
                    )

                    OutlinedTextField(
                        value = uiState.channelNameInput,
                        onValueChange = { viewModel.onChannelNameChange(it) },
                        label = { Text("Channel Name / Title") },
                        placeholder = { Text("e.g. FACTS AI Daily") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        leadingIcon = { Icon(Icons.Default.SmartDisplay, contentDescription = null) }
                    )

                    OutlinedTextField(
                        value = uiState.channelIdInput,
                        onValueChange = { viewModel.onChannelIdChange(it) },
                        label = { Text("Channel ID (Optional)") },
                        placeholder = { Text("UCxxxxxxxxxxxxxxxxxx") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        leadingIcon = { Icon(Icons.Default.Tag, contentDescription = null) }
                    )

                    OutlinedTextField(
                        value = uiState.tokenJsonInput,
                        onValueChange = { viewModel.onTokenJsonChange(it) },
                        label = { Text("YouTube OAuth Token JSON") },
                        placeholder = { Text("{\"token\": \"...\", \"refresh_token\": \"...\"}") },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                        maxLines = 6,
                        leadingIcon = { Icon(Icons.Default.Key, contentDescription = null) }
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Button(
                            onClick = { viewModel.saveChannel() },
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(containerColor = ElectricBlue)
                        ) {
                            Icon(Icons.Default.Save, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Save Channel")
                        }

                        if (uiState.channelInfo.isConnected) {
                            OutlinedButton(
                                onClick = { viewModel.disconnectChannel() },
                                colors = ButtonDefaults.outlinedButtonColors(contentColor = Color.Red),
                                border = BorderStroke(1.dp, Color.Red)
                            ) {
                                Icon(Icons.Default.LinkOff, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("Disconnect")
                            }
                        }
                    }
                }
            }

            // Quick Setup Guide Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Info, contentDescription = null, tint = ElectricBlue)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("How to Connect YouTube?", fontWeight = FontWeight.Bold, color = Color.White)
                    }

                    Text(
                        "1. Create an OAuth 2.0 Desktop Client in Google Cloud Console.\n" +
                        "2. Enable YouTube Data API v3 on your Google account.\n" +
                        "3. Run 'python setup_oauth.py' on PC or paste credentials JSON above.\n" +
                        "4. Add the JSON to GitHub Repository Secrets as 'YOUTUBE_TOKEN_JSON'.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.LightGray
                    )

                    Button(
                        onClick = { viewModel.toggleGuide(true) },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                    ) {
                        Text("View Step-by-Step Instructions", color = Color.White)
                    }
                }
            }
        }
    }

    if (uiState.showGuideDialog) {
        AlertDialog(
            onDismissRequest = { viewModel.toggleGuide(false) },
            title = {
                Text("YouTube OAuth Setup Guide", fontWeight = FontWeight.Bold)
            },
            text = {
                Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(
                        "Step 1: Google Cloud Console",
                        fontWeight = FontWeight.Bold,
                        color = ElectricBlue
                    )
                    Text("• Go to console.cloud.google.com and create a project.\n• In 'APIs & Services' -> 'Library', enable 'YouTube Data API v3'.")

                    Text(
                        "Step 2: OAuth Consent Screen",
                        fontWeight = FontWeight.Bold,
                        color = ElectricBlue
                    )
                    Text("• Choose 'External' user type.\n• Add your own email as a Test User.\n• Add scope: https://www.googleapis.com/auth/youtube.upload")

                    Text(
                        "Step 3: Create Credentials",
                        fontWeight = FontWeight.Bold,
                        color = ElectricBlue
                    )
                    Text("• In 'Credentials', click 'Create Credentials' -> 'OAuth client ID'.\n• Select 'Desktop App' and download the JSON file.")

                    Text(
                        "Step 4: Save & Sync",
                        fontWeight = FontWeight.Bold,
                        color = ElectricBlue
                    )
                    Text("• Run 'python setup_oauth.py' or paste the credentials JSON in the box above.\n• Also add it to GitHub Repo -> Settings -> Secrets as 'YOUTUBE_TOKEN_JSON'.")
                }
            },
            confirmButton = {
                TextButton(onClick = { viewModel.toggleGuide(false) }) {
                    Text("Got It")
                }
            }
        )
    }
}
