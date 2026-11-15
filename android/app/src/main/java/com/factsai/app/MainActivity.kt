package com.factsai.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.factsai.app.ui.dashboard.DashboardScreen
import com.factsai.app.ui.dashboard.DashboardViewModel
import com.factsai.app.ui.generate.GenerateScreen
import com.factsai.app.ui.generate.GenerateViewModel
import com.factsai.app.ui.history.HistoryScreen
import com.factsai.app.ui.history.HistoryViewModel
import com.factsai.app.ui.instructions.InstructionsScreen
import com.factsai.app.ui.instructions.InstructionsViewModel
import com.factsai.app.ui.navigation.Screen
import com.factsai.app.ui.settings.SettingsScreen
import com.factsai.app.ui.settings.SettingsViewModel
import com.factsai.app.ui.theme.DarkBg
import com.factsai.app.ui.theme.FactsAiTheme
import com.factsai.app.ui.theme.TextSecondary
import com.factsai.app.ui.theme.AccentGold

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val app = application as FactsAiApplication
        val repository = app.videoRepository
        val prefs = app.preferencesManager

        val dashboardViewModel = DashboardViewModel(repository, prefs)
        val generateViewModel = GenerateViewModel(repository, prefs)
        val instructionsViewModel = InstructionsViewModel(repository, prefs)
        val historyViewModel = HistoryViewModel(repository)
        val settingsViewModel = SettingsViewModel(repository, prefs)

        setContent {
            FactsAiTheme {
                MainAppScaffold(
                    dashboardViewModel = dashboardViewModel,
                    generateViewModel = generateViewModel,
                    instructionsViewModel = instructionsViewModel,
                    historyViewModel = historyViewModel,
                    settingsViewModel = settingsViewModel
                )
            }
        }
    }
}

@Composable
fun MainAppScaffold(
    dashboardViewModel: DashboardViewModel,
    generateViewModel: GenerateViewModel,
    instructionsViewModel: InstructionsViewModel,
    historyViewModel: HistoryViewModel,
    settingsViewModel: SettingsViewModel
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    val screens = listOf(
        Screen.Dashboard,
        Screen.Generate,
        Screen.Instructions,
        Screen.History,
        Screen.Settings
    )

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        containerColor = DarkBg,
        bottomBar = {
            NavigationBar(
                containerColor = com.factsai.app.ui.theme.CardBg
            ) {
                screens.forEach { screen ->
                    val selected = currentRoute == screen.route
                    NavigationBarItem(
                        selected = selected,
                        onClick = {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = {
                            Icon(
                                screen.icon,
                                contentDescription = screen.title,
                                tint = if (selected) AccentGold else TextSecondary
                            )
                        },
                        label = {
                            Text(
                                screen.title,
                                color = if (selected) AccentGold else TextSecondary
                            )
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Dashboard.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Dashboard.route) {
                DashboardScreen(
                    viewModel = dashboardViewModel,
                    onNavigateToGenerate = {
                        navController.navigate(Screen.Generate.route)
                    }
                )
            }
            composable(Screen.Generate.route) {
                GenerateScreen(viewModel = generateViewModel)
            }
            composable(Screen.Instructions.route) {
                InstructionsScreen(viewModel = instructionsViewModel)
            }
            composable(Screen.History.route) {
                HistoryScreen(viewModel = historyViewModel)
            }
            composable(Screen.Settings.route) {
                SettingsScreen(viewModel = settingsViewModel)
            }
        }
    }
}
