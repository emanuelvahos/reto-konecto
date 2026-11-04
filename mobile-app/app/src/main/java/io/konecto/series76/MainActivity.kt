package io.konecto.series76

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.viewmodel.compose.viewModel
import io.konecto.series76.ui.*

private val AppleIndustrialColorScheme = lightColorScheme(
    primary = Color(0xFF007AFF),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE5F1FF),
    onPrimaryContainer = Color(0xFF0040DD),
    secondary = Color(0xFF5856D6),
    onSecondary = Color.White,
    background = Color(0xFFF2F2F7),
    onBackground = Color(0xFF1C1C1E),
    surface = Color.White,
    onSurface = Color(0xFF1C1C1E),
    surfaceVariant = Color(0xFFF2F2F7),
    onSurfaceVariant = Color(0xFF8E8E93),
    outline = Color(0xFFE5E5EA),
    error = Color(0xFFFF3B30),
    onError = Color.White
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = AppleIndustrialColorScheme) {
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
