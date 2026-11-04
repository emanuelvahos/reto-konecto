package io.konecto.series76

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.lifecycle.viewmodel.compose.viewModel
import io.konecto.series76.ui.AppScreen
import io.konecto.series76.ui.MainViewModel
import io.konecto.series76.ui.chat.ChatScreen
import io.konecto.series76.ui.debug.DebugScreen
import io.konecto.series76.ui.login.LoginScreen
import io.konecto.series76.ui.sessions.SessionsScreen
import io.konecto.series76.ui.theme.Series76Theme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            Series76Theme {
                val vm: MainViewModel = viewModel()
                androidx.compose.runtime.LaunchedEffect(Unit) {
                    vm.initPrefs(this@MainActivity)
                }

                // Control nativo de botón 'Atrás'
                BackHandler(enabled = vm.currentScreen == AppScreen.DEBUG) {
                    vm.currentScreen = AppScreen.CHAT
                }
                BackHandler(enabled = vm.currentScreen == AppScreen.CHAT) {
                    vm.currentScreen = AppScreen.SESSIONS
                    vm.loadSessions()
                }

                when (vm.currentScreen) {
                    AppScreen.LOGIN -> LoginScreen(vm)
                    AppScreen.SESSIONS -> SessionsScreen(vm)
                    AppScreen.CHAT -> ChatScreen(vm)
                    AppScreen.DEBUG -> DebugScreen(vm)
                }
            }
        }
    }
}
