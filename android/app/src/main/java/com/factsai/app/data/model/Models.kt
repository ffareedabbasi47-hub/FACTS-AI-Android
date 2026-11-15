package com.factsai.app.data.model

import com.google.gson.annotations.SerializedName

data class WorkflowDispatchRequest(
    @SerializedName("ref") val ref: String = "main",
    @SerializedName("inputs") val inputs: Map<String, String>
)

data class WorkflowRunsResponse(
    @SerializedName("total_count") val totalCount: Int,
    @SerializedName("workflow_runs") val workflowRuns: List<WorkflowRun>
)

data class WorkflowRun(
    @SerializedName("id") val id: Long,
    @SerializedName("name") val name: String?,
    @SerializedName("status") val status: String, // queued, in_progress, completed
    @SerializedName("conclusion") val conclusion: String?, // success, failure, cancelled
    @SerializedName("html_url") val htmlUrl: String?,
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("updated_at") val updatedAt: String?
)

data class GitHubFileContentResponse(
    @SerializedName("name") val name: String,
    @SerializedName("path") val path: String,
    @SerializedName("content") val content: String, // base64 encoded
    @SerializedName("encoding") val encoding: String
)

data class GitHubRepoResponse(
    @SerializedName("id") val id: Long,
    @SerializedName("name") val name: String,
    @SerializedName("full_name") val fullName: String,
    @SerializedName("private") val isPrivate: Boolean
)

data class TopicHistoryItem(
    val raw: String,
    val topic: String,
    val videoUrl: String?,
    val operationId: String?,
    val status: String // CONFIRMED, PENDING, REVIEW_REQUIRED, FAILED
)

data class CategoryItem(
    val id: String,
    val name: String,
    val description: String,
    val instructions: String = "",
    val isCustom: Boolean = false
)

data class AppSettings(
    val repoOwner: String = "ffareedabbasi47-hub",
    val repoName: String = "FACTS-AI-Android",
    val branch: String = "main",
    val githubToken: String = "",
    val defaultFormat: String = "short",
    val defaultPrivacy: String = "private",
    val defaultVoice: String = "hi-IN-MadhurNeural",
    val globalAiInstructions: String = ""
)
