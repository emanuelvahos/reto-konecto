package io.konecto.series76.util

object VoiceNormalizer {
    private val wordToSymbol = mapOf(
        // Números en inglés y español
        "zero" to "0", "cero" to "0", "oh" to "0",
        "one" to "1", "uno" to "1", "una" to "1",
        "two" to "2", "dos" to "2",
        "three" to "3", "tres" to "3",
        "four" to "4", "cuatro" to "4",
        "five" to "5", "cinco" to "5",
        "six" to "6", "seis" to "6",
        "seven" to "7", "siete" to "7",
        "eight" to "8", "ocho" to "8",
        "nine" to "9", "nueve" to "9",

        // Letras fonéticas comunes
        "bee" to "B", "be" to "B",
        "see" to "C", "sea" to "C", "ce" to "C",
        "ex" to "X", "equis" to "X",
        "why" to "Y", "ye" to "Y",

        // Separadores y signos
        "dash" to "-", "hyphen" to "-", "minus" to "-", "guion" to "-", "guión" to "-", "menos" to "-",
        "slash" to "/", "stroke" to "/", "barra" to "/", "diagonal" to "/"
    )

    // Patrón robusto para detectar secuencias de Series 76 habladas (con o sin espacios intermedios)
    private val partRegex = Regex(
        """\b(7\s*6\s*[1-7]\s*[ABCXYabcxy]\s*(?:0\s*0|3\s*0)?)\s*[-–—]?\s*(1\s*1\s*3\s*[02378]\s*(?:0\s*){3,6})(?:\s*[/]?\s*([Aa]))?\b"""
    )

    fun normalizeSpokenTechnicalQuery(rawTranscript: String): String {
        if (rawTranscript.isBlank()) return rawTranscript

        // 1. Mapeo palabra por palabra de números y símbolos hablados
        val tokens = rawTranscript.split(Regex("""\s+"""))
        val mapped = tokens.joinToString(" ") { token ->
            val clean = token.lowercase().trim(',', '.', '!', '?')
            wordToSymbol[clean] ?: token
        }

        // 2. Compactar y normalizar secuencias de Part Numbers al formato técnico canónico
        return partRegex.replace(mapped) { match ->
            var prefix = match.groupValues[1].replace(Regex("""\s+"""), "").uppercase()
            if (prefix.length == 4) {
                val sizeLetter = prefix[3]
                prefix += if (sizeLetter == 'X' || sizeLetter == 'Y') "30" else "00"
            }
            val rawCode = match.groupValues[2].replace(Regex("""\s+"""), "").uppercase()
            val voltageDigit = rawCode.getOrNull(3) ?: '0'
            val cleanCode = "113${voltageDigit}0000"
            "$prefix-$cleanCode/A"
        }
    }
}
