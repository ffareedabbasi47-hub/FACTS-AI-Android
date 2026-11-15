package com.factsai.app.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.factsai.app.data.model.ApiKeysConfig
import com.factsai.app.data.model.AppSettings
import com.factsai.app.data.model.CategoryItem
import com.factsai.app.data.model.ChannelInfo
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken

class PreferencesManager(context: Context) {

    private val gson = Gson()
    private val prefs: SharedPreferences = try {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        EncryptedSharedPreferences.create(
            context,
            "facts_ai_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    } catch (e: Exception) {
        // Fallback for environments where Android Keystore may be unavailable
        context.getSharedPreferences("facts_ai_prefs_fallback", Context.MODE_PRIVATE)
    }

    fun getSettings(): AppSettings {
        return AppSettings(
            repoOwner = prefs.getString(KEY_REPO_OWNER, "ffareedabbasi47-hub") ?: "ffareedabbasi47-hub",
            repoName = prefs.getString(KEY_REPO_NAME, "FACTS-AI-Android") ?: "FACTS-AI-Android",
            branch = prefs.getString(KEY_BRANCH, "main") ?: "main",
            githubToken = prefs.getString(KEY_GITHUB_TOKEN, "") ?: "",
            openRouterApiKey = prefs.getString(KEY_OPENROUTER_API_KEY, "") ?: "",
            pexelsApiKey = prefs.getString(KEY_PEXELS_API_KEY, "") ?: "",
            youtubeTokenJson = prefs.getString(KEY_YOUTUBE_TOKEN_JSON, "") ?: "",
            youtubeChannelName = prefs.getString(KEY_YOUTUBE_CHANNEL_NAME, "") ?: "",
            youtubeChannelId = prefs.getString(KEY_YOUTUBE_CHANNEL_ID, "") ?: "",
            defaultFormat = prefs.getString(KEY_DEFAULT_FORMAT, "short") ?: "short",
            defaultPrivacy = prefs.getString(KEY_DEFAULT_PRIVACY, "private") ?: "private",
            defaultVoice = prefs.getString(KEY_DEFAULT_VOICE, "hi-IN-MadhurNeural") ?: "hi-IN-MadhurNeural",
            globalAiInstructions = prefs.getString(KEY_GLOBAL_INSTRUCTIONS, "") ?: ""
        )
    }

    fun saveSettings(settings: AppSettings) {
        prefs.edit()
            .putString(KEY_REPO_OWNER, settings.repoOwner.trim())
            .putString(KEY_REPO_NAME, settings.repoName.trim())
            .putString(KEY_BRANCH, settings.branch.trim())
            .putString(KEY_GITHUB_TOKEN, settings.githubToken.trim())
            .putString(KEY_OPENROUTER_API_KEY, settings.openRouterApiKey.trim())
            .putString(KEY_PEXELS_API_KEY, settings.pexelsApiKey.trim())
            .putString(KEY_YOUTUBE_TOKEN_JSON, settings.youtubeTokenJson.trim())
            .putString(KEY_YOUTUBE_CHANNEL_NAME, settings.youtubeChannelName.trim())
            .putString(KEY_YOUTUBE_CHANNEL_ID, settings.youtubeChannelId.trim())
            .putString(KEY_DEFAULT_FORMAT, settings.defaultFormat)
            .putString(KEY_DEFAULT_PRIVACY, settings.defaultPrivacy)
            .putString(KEY_DEFAULT_VOICE, settings.defaultVoice)
            .putString(KEY_GLOBAL_INSTRUCTIONS, settings.globalAiInstructions.trim())
            .apply()
    }

    fun getApiKeysConfig(): ApiKeysConfig {
        return ApiKeysConfig(
            openRouterApiKey = prefs.getString(KEY_OPENROUTER_API_KEY, "") ?: "",
            pexelsApiKey = prefs.getString(KEY_PEXELS_API_KEY, "") ?: "",
            youtubeTokenJson = prefs.getString(KEY_YOUTUBE_TOKEN_JSON, "") ?: "",
            githubToken = prefs.getString(KEY_GITHUB_TOKEN, "") ?: ""
        )
    }

    fun saveApiKeys(openRouter: String, pexels: String, youtubeJson: String, githubToken: String) {
        prefs.edit()
            .putString(KEY_OPENROUTER_API_KEY, openRouter.trim())
            .putString(KEY_PEXELS_API_KEY, pexels.trim())
            .putString(KEY_YOUTUBE_TOKEN_JSON, youtubeJson.trim())
            .putString(KEY_GITHUB_TOKEN, githubToken.trim())
            .apply()
    }

    fun getChannelInfo(): ChannelInfo {
        val tokenJson = prefs.getString(KEY_YOUTUBE_TOKEN_JSON, "") ?: ""
        val name = prefs.getString(KEY_YOUTUBE_CHANNEL_NAME, "") ?: ""
        val id = prefs.getString(KEY_YOUTUBE_CHANNEL_ID, "") ?: ""
        val privacy = prefs.getString(KEY_DEFAULT_PRIVACY, "private") ?: "private"
        val lastSync = prefs.getString(KEY_LAST_CHANNEL_SYNC, "") ?: ""
        val isConnected = tokenJson.isNotBlank() && (tokenJson.contains("refresh_token") || tokenJson.contains("client_id") || tokenJson.length > 30)
        return ChannelInfo(
            channelName = if (name.isNotBlank()) name else if (isConnected) "Authorized YouTube Channel" else "Not Connected",
            channelId = id,
            isConnected = isConnected,
            lastSyncTime = lastSync,
            uploadPrivacy = privacy
        )
    }

    fun saveChannelInfo(name: String, channelId: String, tokenJson: String) {
        prefs.edit()
            .putString(KEY_YOUTUBE_CHANNEL_NAME, name.trim())
            .putString(KEY_YOUTUBE_CHANNEL_ID, channelId.trim())
            .putString(KEY_YOUTUBE_TOKEN_JSON, tokenJson.trim())
            .putString(KEY_LAST_CHANNEL_SYNC, java.text.SimpleDateFormat("dd MMM yyyy, hh:mm a", java.util.Locale.getDefault()).format(java.util.Date()))
            .apply()
    }

    fun disconnectChannel() {
        prefs.edit()
            .remove(KEY_YOUTUBE_CHANNEL_NAME)
            .remove(KEY_YOUTUBE_CHANNEL_ID)
            .remove(KEY_YOUTUBE_TOKEN_JSON)
            .remove(KEY_LAST_CHANNEL_SYNC)
            .apply()
    }

    fun getGlobalAiInstructions(): String {
        return prefs.getString(KEY_GLOBAL_INSTRUCTIONS, "") ?: ""
    }

    fun saveGlobalAiInstructions(instructions: String) {
        prefs.edit().putString(KEY_GLOBAL_INSTRUCTIONS, instructions.trim()).apply()
    }

    fun getCategoryInstructions(categoryId: String): String {
        val json = prefs.getString(KEY_CATEGORY_INSTRUCTIONS_MAP, "{}") ?: "{}"
        val type = object : TypeToken<Map<String, String>>() {}.type
        val map: Map<String, String> = try { gson.fromJson(json, type) } catch (e: Exception) { emptyMap() }
        return map[categoryId] ?: ""
    }

    fun saveCategoryInstructions(categoryId: String, instructions: String) {
        val json = prefs.getString(KEY_CATEGORY_INSTRUCTIONS_MAP, "{}") ?: "{}"
        val type = object : TypeToken<Map<String, String>>() {}.type
        val map: MutableMap<String, String> = try {
            gson.fromJson(json, type) ?: mutableMapOf()
        } catch (e: Exception) {
            mutableMapOf()
        }
        map[categoryId] = instructions.trim()
        prefs.edit().putString(KEY_CATEGORY_INSTRUCTIONS_MAP, gson.toJson(map)).apply()
    }

    fun getCustomCategories(): List<CategoryItem> {
        val json = prefs.getString(KEY_CUSTOM_CATEGORIES, "[]") ?: "[]"
        val type = object : TypeToken<List<CategoryItem>>() {}.type
        return try {
            gson.fromJson(json, type) ?: emptyList()
        } catch (e: Exception) {
            emptyList()
        }
    }

    fun addCustomCategory(category: CategoryItem) {
        val current = getCustomCategories().toMutableList()
        current.removeAll { it.id == category.id }
        current.add(category)
        prefs.edit().putString(KEY_CUSTOM_CATEGORIES, gson.toJson(current)).apply()
    }

    fun deleteCustomCategory(categoryId: String) {
        val current = getCustomCategories().toMutableList()
        current.removeAll { it.id == categoryId }
        prefs.edit().putString(KEY_CUSTOM_CATEGORIES, gson.toJson(current)).apply()
    }

    fun getMaskedToken(token: String): String {
        return if (token.length > 8) {
            "${token.take(4)}••••••••${token.takeLast(4)}"
        } else if (token.isNotEmpty()) {
            "••••••••"
        } else {
            ""
        }
    }

    companion object {
        private const val KEY_REPO_OWNER = "repo_owner"
        private const val KEY_REPO_NAME = "repo_name"
        private const val KEY_BRANCH = "repo_branch"
        private const val KEY_GITHUB_TOKEN = "github_token"
        private const val KEY_OPENROUTER_API_KEY = "openrouter_api_key"
        private const val KEY_PEXELS_API_KEY = "pexels_api_key"
        private const val KEY_YOUTUBE_TOKEN_JSON = "youtube_token_json"
        private const val KEY_YOUTUBE_CHANNEL_NAME = "youtube_channel_name"
        private const val KEY_YOUTUBE_CHANNEL_ID = "youtube_channel_id"
        private const val KEY_LAST_CHANNEL_SYNC = "last_channel_sync"
        private const val KEY_DEFAULT_FORMAT = "default_format"
        private const val KEY_DEFAULT_PRIVACY = "default_privacy"
        private const val KEY_DEFAULT_VOICE = "default_voice"
        private const val KEY_GLOBAL_INSTRUCTIONS = "global_ai_instructions"
        private const val KEY_CATEGORY_INSTRUCTIONS_MAP = "category_instructions_map"
        private const val KEY_CUSTOM_CATEGORIES = "custom_categories_list"
    }
}
