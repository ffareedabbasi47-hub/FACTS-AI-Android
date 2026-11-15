package com.factsai.app.ui.history

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factsai.app.data.model.TopicHistoryItem
import com.factsai.app.ui.theme.*

@Composable
fun HistoryScreen(viewModel: HistoryViewModel) {
    val state by viewModel.uiState.collectAsState()
    val context = LocalContext.current

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBg)
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "Video History & Logs",
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Bold,
                    color = AccentGold
                )
                Text(
                    text = "Live workflow runs & used_topics.txt deduplication",
                    fontSize = 12.sp,
                    color = TextSecondary
                )
            }
            IconButton(
                onClick = { viewModel.loadHistory() },
                enabled = !state.isLoading
            ) {
                if (state.isLoading) {
                    CircularProgressIndicator(modifier = Modifier.size(22.dp), color = AccentGold, strokeWidth = 2.dp)
                } else {
                    Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentGold)
                }
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Latest Workflow Run Status Card
        state.latestRun?.let { run ->
            val isSuccess = run.conclusion == "success"
            val isFailure = run.conclusion == "failure"
            val isInProgress = run.status == "in_progress" || run.status == "queued"

            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(
                    containerColor = when {
                        isSuccess -> SuccessGreen.copy(alpha = 0.15f)
                        isFailure -> ErrorRed.copy(alpha = 0.15f)
                        else -> AccentCyan.copy(alpha = 0.15f)
                    }
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "Latest Pipeline: ${run.name ?: "Daily Video"}",
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp,
                            color = TextPrimary
                        )
                        Text(
                            text = "Status: ${run.conclusion ?: run.status}",
                            fontSize = 12.sp,
                            color = when {
                                isSuccess -> SuccessGreen
                                isFailure -> ErrorRed
                                else -> AccentCyan
                            }
                        )
                    }

                    Row {
                        if (isFailure) {
                            TextButton(onClick = { viewModel.inspectLatestRun() }) {
                                Icon(Icons.Default.BugReport, contentDescription = null, tint = ErrorRed, modifier = Modifier.size(16.dp))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("Why Failed?", color = ErrorRed, fontSize = 12.sp)
                            }
                        }

                        run.htmlUrl?.let { url ->
                            IconButton(onClick = {
                                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                                context.startActivity(intent)
                            }) {
                                Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = "GitHub", tint = AccentGold)
                            }
                        }
                    }
                }
            }
            Spacer(modifier = Modifier.height(12.dp))
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
            Spacer(modifier = Modifier.height(12.dp))
        }

        if (state.items.isEmpty() && !state.isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = "No recorded video history found in repository.",
                    color = TextSecondary,
                    fontSize = 14.sp
                )
            }
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.fillMaxSize()
            ) {
                items(state.items) { item ->
                    HistoryItemCard(item = item, onOpenUrl = { url ->
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                        context.startActivity(intent)
                    })
                }
            }
        }
    }

    if (state.showDiagnosisDialog) {
        AlertDialog(
            onDismissRequest = { viewModel.dismissDiagnosisDialog() },
            title = {
                Text("Pipeline Failure Diagnostics", fontWeight = FontWeight.Bold)
            },
            text = {
                Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    if (state.isDiagnosing) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                            Spacer(modifier = Modifier.width(10.dp))
                            Text("Inspecting failed step logs...")
                        }
                    } else {
                        Text(
                            text = state.runDiagnosis ?: "No diagnostic details available.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextPrimary
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { viewModel.dismissDiagnosisDialog() }) {
                    Text("Close")
                }
            }
        )
    }
}

@Composable
fun HistoryItemCard(item: TopicHistoryItem, onOpenUrl: (String) -> Unit) {
    val statusColor = when (item.status) {
        "CONFIRMED" -> SuccessGreen
        "PENDING" -> AccentCyan
        "REVIEW_REQUIRED" -> AccentGold
        "FAILED" -> ErrorRed
        else -> TextSecondary
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBg)
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Surface(
                    color = statusColor.copy(alpha = 0.2f),
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text(
                        text = item.status,
                        color = statusColor,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                    )
                }

                if (item.operationId != null) {
                    Text(
                        text = item.operationId,
                        color = TextSecondary,
                        fontSize = 11.sp
                    )
                }
            }

            Text(
                text = item.topic,
                fontWeight = FontWeight.SemiBold,
                fontSize = 15.sp,
                color = TextPrimary
            )

            if (item.videoUrl != null) {
                TextButton(
                    onClick = { onOpenUrl(item.videoUrl) },
                    contentPadding = PaddingValues(0.dp)
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.OpenInNew,
                        contentDescription = "Open Video",
                        tint = AccentCyan,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Watch on YouTube",
                        color = AccentCyan,
                        fontSize = 12.sp
                    )
                }
            }
        }
    }
}
