package io.konecto.series76.ui.theme

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color

// =====================================================================
// INDUSTRIAL INSTRUMENTATION PALETTE (AA Contrast Compliant)
// Electric Amber Accent, Deep Graphite/Ink Chassis, Teal Verified
// =====================================================================

// Electric Amber Brand & Accent Tokens
val ElectricAmberDark = Color(0xFFFBBF24)       // Glowing electric amber for dark mode
val ElectricAmberLight = Color(0xFFD97706)      // High-contrast industrial amber for light mode controls
val ElectricAmberLightText = Color(0xFFB45309)  // Deep industrial amber (WCAG AA compliant >= 4.5:1 on light backgrounds)
val AmberContainerDark = Color(0xFF452205)
val AmberContainerLight = Color(0xFFFEF3C7)
val OnAmberDark = Color(0xFF1E1303)
val OnAmberLight = Color(0xFFFFFFFF)

// Verified / OK (Teal-Cyan)
val TealVerifiedDark = Color(0xFF2DD4BF)
val TealVerifiedLight = Color(0xFF0F766E)
val TealContainerDark = Color(0xFF09332F)
val TealContainerLight = Color(0xFFCCFBF1)
val TealBorderDark = Color(0xFF14B8A6)
val TealBorderLight = Color(0xFF5EEAD4)

// Neutral Industrial - Dark (Default)
val DarkBackground = Color(0xFF0B0F19)           // Deep ink/graphite
val DarkSurface = Color(0xFF141C2B)              // Instrument panel chassis
val DarkSurfaceVariant = Color(0xFF1E293B)       // Sub-panel / card interior
val DarkSurfaceElevated = Color(0xFF26354D)      // Elevated dial bezel
val DarkBorder = Color(0xFF29394F)               // Chassis hairline border
val DarkBorderSubtle = Color(0xFF1E293B)
val DarkTextPrimary = Color(0xFFF1F5F9)          // Sharp white readout
val DarkTextSecondary = Color(0xFF94A3B8)        // Metallic slate
val DarkTextMuted = Color(0xFF64748B)

// Neutral Industrial - Light
val LightBackground = Color(0xFFF1F5F9)          // Industrial light stone
val LightSurface = Color(0xFFFFFFFF)             // Clean white module
val LightSurfaceVariant = Color(0xFFE2E8F0)      // Slate sub-panel
val LightSurfaceElevated = Color(0xFFF8FAFC)
val LightBorder = Color(0xFFCBD5E1)              // Crisp mechanical hairline
val LightBorderSubtle = Color(0xFFE2E8F0)
val LightTextPrimary = Color(0xFF0F172A)         // Deep dark slate
val LightTextSecondary = Color(0xFF475569)       // Medium slate
val LightTextMuted = Color(0xFF94A3B8)

// Semantic State Container
@Immutable
data class SemanticColors(
    val accent: Color,
    val accentText: Color,
    val onAccent: Color,
    val accentContainer: Color,
    val successBg: Color,
    val successText: Color,
    val successBorder: Color,
    val warningBg: Color,
    val warningText: Color,
    val warningBorder: Color,
    val errorBg: Color,
    val errorText: Color,
    val errorBorder: Color,
    val codeBg: Color,
    val codeText: Color,
    val gaugeTrack: Color,
    val gaugeIndicator: Color
)

val DarkSemanticColors = SemanticColors(
    accent = ElectricAmberDark,
    accentText = ElectricAmberDark,
    onAccent = OnAmberDark,
    accentContainer = AmberContainerDark,
    successBg = TealContainerDark,
    successText = TealVerifiedDark,
    successBorder = TealBorderDark,
    warningBg = Color(0xFF3B1D04),
    warningText = Color(0xFFFBBF24),
    warningBorder = Color(0xFFF59E0B),
    errorBg = Color(0xFF3B0D0D),
    errorText = Color(0xFFFCA5A5),
    errorBorder = Color(0xFFEF4444),
    codeBg = Color(0xFF1E293B),
    codeText = ElectricAmberDark,
    gaugeTrack = Color(0xFF253347),
    gaugeIndicator = ElectricAmberDark
)

val LightSemanticColors = SemanticColors(
    accent = ElectricAmberLight,
    accentText = ElectricAmberLightText,
    onAccent = OnAmberLight,
    accentContainer = AmberContainerLight,
    successBg = TealContainerLight,
    successText = TealVerifiedLight,
    successBorder = TealBorderLight,
    warningBg = Color(0xFFFEF3C7),
    warningText = Color(0xFF92400E),
    warningBorder = Color(0xFFFCD34D),
    errorBg = Color(0xFFFEE2E2),
    errorText = Color(0xFF991B1B),
    errorBorder = Color(0xFFFCA5A5),
    codeBg = Color(0xFFF1F5F9),
    codeText = Color(0xFF0F172A),
    gaugeTrack = Color(0xFFCBD5E1),
    gaugeIndicator = ElectricAmberLight
)
