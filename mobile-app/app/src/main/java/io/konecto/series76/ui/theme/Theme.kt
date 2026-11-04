package io.konecto.series76.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.Color

val LocalSemanticColors = staticCompositionLocalOf { DarkSemanticColors }

object ThemeController {
    // Modo oscuro por defecto según requerimiento 5 de Checkpoint 3A-bis
    var isDarkTheme by mutableStateOf(true)

    fun toggleTheme() {
        isDarkTheme = !isDarkTheme
    }
}

private val DarkIndustrialColorScheme = darkColorScheme(
    primary = ElectricAmberDark,
    onPrimary = OnAmberDark,
    primaryContainer = AmberContainerDark,
    onPrimaryContainer = ElectricAmberDark,
    secondary = TealVerifiedDark,
    onSecondary = Color(0xFF042F2E),
    secondaryContainer = TealContainerDark,
    onSecondaryContainer = TealVerifiedDark,
    background = DarkBackground,
    onBackground = DarkTextPrimary,
    surface = DarkSurface,
    onSurface = DarkTextPrimary,
    surfaceVariant = DarkSurfaceVariant,
    onSurfaceVariant = DarkTextSecondary,
    outline = DarkBorder,
    outlineVariant = DarkBorderSubtle,
    error = Color(0xFFEF4444),
    onError = Color(0xFF450A0A)
)

private val LightIndustrialColorScheme = lightColorScheme(
    primary = ElectricAmberLight,
    onPrimary = OnAmberLight,
    primaryContainer = AmberContainerLight,
    onPrimaryContainer = Color(0xFF78350F),
    secondary = TealVerifiedLight,
    onSecondary = Color.White,
    secondaryContainer = TealContainerLight,
    onSecondaryContainer = Color(0xFF134E4A),
    background = LightBackground,
    onBackground = LightTextPrimary,
    surface = LightSurface,
    onSurface = LightTextPrimary,
    surfaceVariant = LightSurfaceVariant,
    onSurfaceVariant = LightTextSecondary,
    outline = LightBorder,
    outlineVariant = LightBorderSubtle,
    error = Color(0xFFDC2626),
    onError = Color.White
)

object KonectoTheme {
    val semantics: SemanticColors
        @Composable
        @ReadOnlyComposable
        get() = LocalSemanticColors.current
}

@Composable
fun Series76Theme(
    darkTheme: Boolean = ThemeController.isDarkTheme,
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkIndustrialColorScheme else LightIndustrialColorScheme
    val semanticColors = if (darkTheme) DarkSemanticColors else LightSemanticColors

    CompositionLocalProvider(LocalSemanticColors provides semanticColors) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = AppTypography,
            shapes = AppShapes,
            content = content
        )
    }
}
