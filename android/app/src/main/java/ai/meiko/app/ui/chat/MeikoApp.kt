package ai.meiko.app.ui.chat

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import ai.meiko.app.ui.MeikoViewModel
import ai.meiko.app.ui.history.HistoryScreen
import ai.meiko.app.ui.settings.SettingsScreen

object Routes {
    const val CHAT = "chat"
    const val SETTINGS = "settings"
    const val HISTORY = "history"
}

@Composable
fun MeikoApp(viewModel: MeikoViewModel) {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = Routes.CHAT) {
        composable(Routes.CHAT) {
            ChatScreen(
                viewModel = viewModel,
                onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                onOpenHistory = { navController.navigate(Routes.HISTORY) },
            )
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(viewModel = viewModel, onBack = { navController.popBackStack() })
        }
        composable(Routes.HISTORY) {
            HistoryScreen(
                viewModel = viewModel,
                onBack = { navController.popBackStack() },
                onOpenConversation = {
                    viewModel.openConversation(it)
                    navController.popBackStack()
                },
            )
        }
    }
}
