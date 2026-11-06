package io.konecto.series76

import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.animation.*
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
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
                val context = LocalContext.current
                LaunchedEffect(Unit) {
                    vm.initPrefs(this@MainActivity)
                }

                val reduceMotion = remember {
                    try {
                        val scale = Settings.Global.getFloat(
                            context.contentResolver,
                            Settings.Global.TRANSITION_ANIMATION_SCALE,
                            1f
                        )
                        scale == 0f
                    } catch (e: Exception) {
                        false
                    }
                }

                // Control nativo de botón 'Atrás'
                BackHandler(enabled = vm.currentScreen == AppScreen.DEBUG) {
                    vm.currentScreen = AppScreen.CHAT
                }
                BackHandler(enabled = vm.currentScreen == AppScreen.CHAT) {
                    vm.currentScreen = AppScreen.SESSIONS
                    vm.loadSessions()
                }

                AnimatedContent(
                    targetState = vm.currentScreen,
                    transitionSpec = {
                        if (reduceMotion) {
                            EnterTransition.None togetherWith ExitTransition.None
                        } else {
                            (fadeIn(animationSpec = spring(stiffness = Spring.StiffnessMediumLow)) +
                             slideInVertically(animationSpec = spring(stiffness = Spring.StiffnessMediumLow)) { it / 8 })
                                .togetherWith(
                                    fadeOut(animationSpec = spring(stiffness = Spring.StiffnessMediumLow)) +
                                    slideOutVertically(animationSpec = spring(stiffness = Spring.StiffnessMediumLow)) { -it / 8 }
                                )
                        }
                    },
                    label = "ScreenTransition"
                ) { screen ->
                    when (screen) {
                        AppScreen.LOGIN -> LoginScreen(vm)
                        AppScreen.SESSIONS -> SessionsScreen(vm)
                        AppScreen.CHAT -> ChatScreen(vm)
                        AppScreen.DEBUG -> DebugScreen(vm)
                    }
                }
            }
        }
    }
}
