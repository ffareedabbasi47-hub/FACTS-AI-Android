package com.factsai.app

import android.app.Application
import com.factsai.app.data.local.PreferencesManager
import com.factsai.app.data.remote.GitHubApiService
import com.factsai.app.data.repository.VideoRepository

class FactsAiApplication : Application() {

    lateinit var preferencesManager: PreferencesManager
        private set

    lateinit var videoRepository: VideoRepository
        private set

    override fun onCreate() {
        super.onCreate()
        preferencesManager = PreferencesManager(this)
        val apiService = GitHubApiService.create {
            preferencesManager.getSettings().githubToken
        }
        videoRepository = VideoRepository(preferencesManager, apiService)
    }
}
