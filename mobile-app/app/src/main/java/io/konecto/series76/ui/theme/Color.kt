package io.konecto.series76.ui.theme

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color

// =====================================================================
// TECHNICAL INDUSTRIAL COLOR PALETTE (AA Contrast Compliant)
// =====================================================================

// Brand Accent
val IndustrialBlueLight = Color(0xFF1D4ED8)
val IndustrialBlueDark = Color(0xFF38BDF8)
val IndustrialBlueContainerLight = Color(0xFFDBEAFE)
val IndustrialBlueContainerDark = Color(0xFF0369A1)

// Neutral Grayscale - Light
val LightBackground = Color(0xFFF8F9FA)
val LightSurface = Color(0xFFFFFFFF)
val LightSurfaceVariant = Color(0xFFF1F3F5)
val LightBorder = Color(0xFFE2E8F0)
val LightBorderSubtle = Color(0xFFCBD5E1)
val LightTextPrimary = Color(0xFF0F172A)
val LightTextSecondary = Color(0xFF64748B)

// Neutral Grayscale - Dark
val DarkBackground = Color(0xFF090D16)
val DarkSurface = Color(0xFF131B2E)
val DarkSurfaceVariant = Color(0xFF1E293B)
val DarkBorder = Color(0xFF2E3D56)
val DarkBorderSubtle = Color(0xFF334155)
val DarkTextPrimary = Color(0xFFF8FAFC)
val DarkTextSecondary = Color(0xFF94A3B8)

// Semantic States (Ok, Warning, Error)
@Immutable
data class SemanticColors(
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
    val codeText: Color
)

val LightSemanticColors = SemanticColors(
    successBg = Color(0xFFDCFCE7),
    successText = Color(0xFF166534),
    successBorder = Color(0xFF86EFAC),
    warningBg = Color(0xFFFEF3C7),
    warningText = Color(0xFF92400E),
    warningBorder = Color(0xFFFCD34D),
    errorBg = Color(0xFFFEE2E2),
    errorText = Color(0xFF991B1B),
    errorBorder = Color(0xFFFCA5A5),
    codeBg = Color(0xFFF1F5F9),
    codeText = Color(0xFF0F172A)
)

val DarkSemanticColors = SemanticColors(
    successBg = Color(0xFF064E3B),
    successText = Color(0xFF86EFAC),
    successBorder = Color(0xFF059669),
    warningBg = Color(0xFF451A03),
    warningText = Color(0xFFFDE68A),
    warningBorder = Color(0xFFD97706),
    errorBg = Color(0xFF450A0A),
    errorText = Color(0xFFFCA5A5),
    errorBorder = Color(0xFFDC2626),
    codeBg = Color(0xFF1E293B),
    codeText = Color(0xFFF8FAFC)
)

