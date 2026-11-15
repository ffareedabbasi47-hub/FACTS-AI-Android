package com.factsai.app.data.repository

import android.util.Base64
import com.factsai.app.data.local.PreferencesManager
import com.factsai.app.data.model.CategoryItem
import com.factsai.app.data.model.GitHubRepoResponse
import com.factsai.app.data.model.TopicHistoryItem
import com.factsai.app.data.model.WorkflowDispatchRequest
import com.factsai.app.data.model.WorkflowRun
import com.factsai.app.data.remote.GitHubApiService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class VideoRepository(
    private val preferencesManager: PreferencesManager,
    private val apiService: GitHubApiService
) {
    val defaultCategories: List<CategoryItem> = listOf(
        CategoryItem("space_astronomy", "Space & Cosmic Mysteries", "Explore NASA/ISRO astronomy, planets, black holes, and space phenomena.", "Emphasize deep space marvels and observational facts."),
        CategoryItem("personal_finance", "Personal Finance & UPI", "Fintech hacks, savings strategies, UPI security, and Indian banking insights.", "Focus on practical daily financial safety and actionable advice."),
        CategoryItem("crisis_collapse", "Indian Crisis & Collapse Stories", "Infrastructure issues, urban challenges, and socio-economic deep-dives.", "Keep an analytical, journalistic, and empathetic perspective."),
        CategoryItem("disasters_nature", "Disaster & Volcano Explainers", "Earthquakes, floods, tsunamis, volcanic eruptions, and meteor impacts.", "Highlight meteorological and geological causes with scientific clarity."),
        CategoryItem("mythology_stories", "Sleep & Mythology Narrations", "Indian folklore, ancient stories, and relaxing nighttime explainers.", "Maintain a calming, serene, and respectful storytelling tone."),
        CategoryItem("productivity_study", "Productivity & Exam Hacks", "UPSC, JEE, SSC study routines, cognitive psychology, and memory retention.", "Deliver crisp, practical student routines and study psychology."),
        CategoryItem("tech_ai_tools", "AI Tools & Automation", "Modern artificial intelligence, coding hacks, and practical productivity tools.", "Explain tool mechanics simply with real-world Indian use cases.")
    )

    fun getAllCategories(): List<CategoryItem> {
        val custom = preferencesManager.getCustomCategories()
        return defaultCategories + custom
    }

    suspend fun testConnection(): Result<GitHubRepoResponse> = withContext(Dispatchers.IO) {
        try {
            val settings = preferencesManager.getSettings()
            if (settings.githubToken.isBlank()) {
                return@withContext Result.failure(Exception("GitHub Personal Access Token is not set."))
            }
            val response = apiService.getRepository(settings.repoOwner, settings.repoName)
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!)
            } else {
                val code = response.code()
                val msg = if (code == 401) "Invalid or expired GitHub Token." else if (code == 404) "Repository not found or token lacks access." else "Error: ${response.message()} ($code)"
                Result.failure(Exception(msg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun dispatchVideoGeneration(
        topic: String?,
        category: String?,
        format: String,
        privacy: String,
        voice: String,
        customInstructions: String?
    ): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val settings = preferencesManager.getSettings()
            if (settings.githubToken.isBlank()) {
                return@withContext Result.failure(Exception("GitHub Token is required to trigger workflows."))
            }

            val inputs = mutableMapOf<String, String>()
            if (!topic.isNullOrBlank()) {
                inputs["topic"] = topic.trim()
            }
            if (!category.isNullOrBlank()) {
                inputs["category"] = category.trim()
            }
            inputs["format"] = format
            inputs["privacy"] = privacy
            inputs["voice"] = voice
            if (!customInstructions.isNullOrBlank()) {
                inputs["instructions"] = customInstructions.trim()
            }

            val request = WorkflowDispatchRequest(
                ref = settings.branch,
                inputs = inputs
            )

            val response = apiService.dispatchWorkflow(
                owner = settings.repoOwner,
                repo = settings.repoName,
                workflowId = "daily_upload.yml",
                request = request
            )

            if (response.isSuccessful || response.code() == 204) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to trigger workflow: HTTP ${response.code()} ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getLatestWorkflowRun(): Result<WorkflowRun?> = withContext(Dispatchers.IO) {
        try {
            val settings = preferencesManager.getSettings()
            if (settings.githubToken.isBlank()) {
                return@withContext Result.failure(Exception("GitHub Token is not configured."))
            }

            val response = apiService.getWorkflowRuns(
                owner = settings.repoOwner,
                repo = settings.repoName,
                workflowId = "daily_upload.yml",
                perPage = 5
            )

            if (response.isSuccessful) {
                val runs = response.body()?.workflowRuns ?: emptyList()
                Result.success(runs.firstOrNull())
            } else {
                Result.failure(Exception("Failed to fetch workflow runs: HTTP ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getVideoHistory(): Result<List<TopicHistoryItem>> = withContext(Dispatchers.IO) {
        try {
            val settings = preferencesManager.getSettings()
            if (settings.githubToken.isBlank()) {
                return@withContext Result.failure(Exception("GitHub Token is not configured."))
            }

            val response = apiService.getFileContent(
                owner = settings.repoOwner,
                repo = settings.repoName,
                path = "used_topics.txt",
                ref = settings.branch
            )

            if (response.isSuccessful && response.body() != null) {
                val encoded = response.body()!!.content.replace("\n", "").trim()
                val decodedBytes = Base64.decode(encoded, Base64.DEFAULT)
                val text = String(decodedBytes, Charsets.UTF_8)
                val items = parseUsedTopics(text)
                Result.success(items)
            } else {
                Result.failure(Exception("Could not retrieve used_topics.txt: HTTP ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun parseUsedTopics(content: String): List<TopicHistoryItem> {
        val lines = content.lines()
        val items = mutableListOf<TopicHistoryItem>()

        for (line in lines) {
            val clean = line.trim()
            if (clean.isEmpty() || clean.startsWith("#") || clean.startsWith("<<<<<<<") || clean.startsWith("=======") || clean.startsWith(">>>>>>>")) {
                continue
            }

            var status = "CONFIRMED"
            var remainder = clean
            var opId: String? = null
            var videoUrl: String? = null
            var topic = clean

            if (clean.startsWith("[PENDING]")) {
                status = "PENDING"
                remainder = clean.removePrefix("[PENDING]").trim()
            } else if (clean.startsWith("[REVIEW_REQUIRED]")) {
                status = "REVIEW_REQUIRED"
                remainder = clean.removePrefix("[REVIEW_REQUIRED]").trim()
            } else if (clean.startsWith("[FAILED]")) {
                status = "FAILED"
                remainder = clean.removePrefix("[FAILED]").trim()
            }

            val parts = remainder.split("|").map { it.trim() }
            for (p in parts) {
                if (p.startsWith("op_id=")) {
                    opId = p.removePrefix("op_id=").trim()
                } else if (p.startsWith("topic=")) {
                    topic = p.removePrefix("topic=").trim()
                } else if (p.contains("youtu.be/")) {
                    videoUrl = p
                }
            }

            if (topic == clean && parts.isNotEmpty()) {
                topic = parts[0]
            }

            items.add(
                TopicHistoryItem(
                    raw = clean,
                    topic = topic,
                    videoUrl = videoUrl,
                    operationId = opId,
                    status = status
                )
            )
        }
        return items.reversed() // Most recent first
    }
}
