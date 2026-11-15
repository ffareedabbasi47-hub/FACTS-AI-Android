package com.factsai.app.ui.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factsai.app.ui.theme.*

@Composable
fun DashboardScreen(
    viewModel: DashboardViewModel,
    onNavigateToGenerate: () -> Unit
) {
    val state by viewModel.uiState.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBg)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // App Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "FACTS AI",
                    fontSize = 26.sp,
                    fontWeight = FontWeight.Bold,
                    color = AccentGold
                )
                Text(
                    text = "Personal Video Automation Studio",
                    fontSize = 13.sp,
                    color = TextSecondary
                )
            }
            IconButton(
                onClick = { viewModel.refreshDashboard() },
                enabled = !state.isLoading
            ) {
                if (state.isLoading) {
                    CircularProgressIndicator(modifier = Modifier.size(24.dp), color = AccentGold, strokeWidth = 2.dp)
                } else {
                    Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentGold)
                }
            }
        }

        // Connection Card
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
                        text = "GitHub Engine Link",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = TextPrimary
                    )
                    Badge(
                        containerColor = if (state.isConnected) SuccessGreen else ErrorRed
                    ) {
                        Text(
                            text = if (state.isConnected) "CONNECTED" else "DISCONNECTED",
                            color = DarkBg,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Repository: ${state.repoName}",
                    fontSize = 14.sp,
                    color = TextSecondary
                )
                if (state.errorMessage != null) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = state.errorMessage ?: "",
                        fontSize = 12.sp,
                        color = ErrorRed
                    )
                }
            }
        }

        // Quick Stats Row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Card(
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = CardBg)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(text = "Total Videos", fontSize = 13.sp, color = TextSecondary)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "${state.totalVideos}",
                        fontSize = 24.sp,
                        fontWeight = FontWeight.Bold,
                        color = AccentGold
                    )
                }
            }
            Card(
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = CardBg)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(text = "YouTube Channel", fontSize = 13.sp, color = TextSecondary)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "Linked",
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Bold,
                        color = SuccessGreen
                    )
                }
            }
        }

        // Latest Workflow Run Card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = CardBg)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = "Latest Cloud Execution",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.height(12.dp))

                val run = state.latestRun
                if (run != null) {
                    val statusColor = when (run.status) {
                        "completed" -> if (run.conclusion == "success") SuccessGreen else ErrorRed
                        "in_progress" -> PendingOrange
                        else -> TextSecondary
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "Run #${run.id}",
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold,
                                color = TextPrimary
                            )
                            Text(
                                text = run.createdAt?.take(16)?.replace("T", " ") ?: "Recent",
                                fontSize = 12.sp,
                                color = TextSecondary
                            )
                        }
                        Surface(
                            shape = RoundedCornerShape(6.dp),
                            color = statusColor.copy(alpha = 0.2f),
                            border = androidx.compose.foundation.BorderStroke(1.dp, statusColor)
                        ) {
                            Text(
                                text = "${run.status.uppercase()}: ${run.conclusion?.uppercase() ?: "RUNNING"}",
                                color = statusColor,
                                fontWeight = FontWeight.Bold,
                                fontSize = 12.sp,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                            )
                        }
                    }
                } else {
                    Text(
                        text = "No recent workflow runs detected. Tap 'Refresh' or trigger a generation.",
                        fontSize = 13.sp,
                        color = TextSecondary
                    )
                }
            }
        }

        // Generate Action Button
        Button(
            onClick = onNavigateToGenerate,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(10.dp),
            colors = ButtonDefaults.buttonColors(containerColor = AccentGold, contentColor = DarkBg)
        ) {
            Icon(Icons.Default.PlayArrow, contentDescription = null, tint = DarkBg)
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "GENERATE NEW VIDEO",
                fontWeight = FontWeight.Bold,
                fontSize = 15.sp
            )
        }
    }
}
