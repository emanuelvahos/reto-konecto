package io.konecto.series76.ui.components

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle

/**
 * Parser Markdown ultra-ligero que filtra listas verticales de viñetas redundantes
 * y tablas ASCII, enfocándose en prosa limpia y legible.
 */
fun parseCleanMarkdown(
    text: String,
    textColor: Color = Color.Unspecified,
    codeBgColor: Color = Color(0xFFF1F5F9),
    codeTextColor: Color = Color(0xFF0F172A)
): AnnotatedString {
    val cleanedLines = mutableListOf<String>()
    for (rawLine in text.lines()) {
        val trimmed = rawLine.trim()
        if (trimmed.startsWith("|") && trimmed.endsWith("|")) continue
        val withoutHeader = trimmed.replace(Regex("""^#{1,6}\s+"""), "")
        cleanedLines.add(withoutHeader)
    }

    val normalizedText = cleanedLines
        .joinToString("\n")
        .replace(Regex("""\n{3,}"""), "\n\n")
        .trim()

    val finalSource = normalizedText.ifEmpty { text.replace("**", "").replace("`", "").trim() }

    return buildAnnotatedString {
        val tokenRegex = Regex("""\*\*(.+?)\*\*|`([^`]+)`|\*([^\*\n]+)\*""", RegexOption.DOT_MATCHES_ALL)
        var lastIndex = 0
        for (match in tokenRegex.findAll(finalSource)) {
            val range = match.range
            if (range.first > lastIndex) {
                append(finalSource.substring(lastIndex, range.first))
            }
            val boldGroup = match.groups[1]?.value
            val codeGroup = match.groups[2]?.value
            val italicGroup = match.groups[3]?.value

            when {
                boldGroup != null -> {
                    withStyle(style = SpanStyle(fontWeight = FontWeight.Bold, color = textColor)) {
                        append(boldGroup)
                    }
                }
                codeGroup != null -> {
                    withStyle(
                        style = SpanStyle(
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            background = codeBgColor,
                            color = codeTextColor
                        )
                    ) {
                        append(" $codeGroup ")
                    }
                }
                italicGroup != null -> {
                    withStyle(style = SpanStyle(fontStyle = FontStyle.Italic)) {
                        append(italicGroup)
                    }
                }
            }
            lastIndex = range.last + 1
        }
        if (lastIndex < finalSource.length) {
            append(finalSource.substring(lastIndex))
        }
    }
}

fun formatMarkdownBold(text: String): AnnotatedString = parseCleanMarkdown(text)

