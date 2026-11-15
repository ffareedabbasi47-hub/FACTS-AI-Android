package com.factsai.app.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.factsai.app.data.model.AppSettings
import com.factsai.app.data.model.CategoryItem
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
            .putString(KEY_DEFAULT_FORMAT, settings.defaultFormat)
            .putString(KEY_DEFAULT_PRIVACY, settings.defaultPrivacy)
            .putString(KEY_DEFAULT_VOICE, settings.defaultVoice)
            .putString(KEY_GLOBAL_INSTRUCTIONS, settings.globalAiInstructions.trim())
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

    fun getMaskedToken(): String {
        val token = prefs.getString(KEY_GITHUB_TOKEN, "") ?: ""
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
        private const val KEY_DEFAULT_FORMAT = "default_format"
        private const val KEY_DEFAULT_PRIVACY = "default_privacy"
        private const val KEY_DEFAULT_VOICE = "default_voice"
        private const val KEY_GLOBAL_INSTRUCTIONS = "global_ai_instructions"
        private const val KEY_CATEGORY_INSTRUCTIONS_MAP = "category_instructions_map"
        private const val KEY_CUSTOM_CATEGORIES = "custom_categories_list"
    }
}
