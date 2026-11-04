package io.konecto.series76.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

val LocalSemanticColors = staticCompositionLocalOf { LightSemanticColors }

private val LightIndustrialColorScheme = lightColorScheme(
    primary = IndustrialBlueLight,
    onPrimary = Color.White,
    primaryContainer = IndustrialBlueContainerLight,
    onPrimaryContainer = Color(0xFF1E40AF),
    secondary = Color(0xFF475569),
    onSecondary = Color.White,
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

private val DarkIndustrialColorScheme = darkColorScheme(
    primary = IndustrialBlueDark,
    onPrimary = Color(0xFF0F172A),
    primaryContainer = IndustrialBlueContainerDark,
    onPrimaryContainer = Color(0xFFE0F2FE),
    secondary = Color(0xFF94A3B8),
    onSecondary = Color(0xFF0F172A),
    background = DarkBackground,
    onBackground = DarkTextPrimary,
    surface = DarkSurface,
    onSurface = DarkTextPrimary,
    surfaceVariant = DarkSurfaceVariant,
    onSurfaceVariant = DarkTextSecondary,
    outline = DarkBorder,
    outlineVariant = DarkBorderSubtle,
    error = Color(0xFFEF4444),
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
    darkTheme: Boolean = isSystemInDarkTheme(),
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

