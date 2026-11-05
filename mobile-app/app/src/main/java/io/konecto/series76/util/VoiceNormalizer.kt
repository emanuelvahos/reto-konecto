package io.konecto.series76.util

object VoiceNormalizer {
    private val wordToSymbol = mapOf(
        // Dígitos en español e inglés
        "cero" to "0", "zero" to "0", "oh" to "0",
        "uno" to "1", "una" to "1", "un" to "1", "one" to "1",
        "dos" to "2", "two" to "2",
        "tres" to "3", "three" to "3",
        "cuatro" to "4", "four" to "4",
        "cinco" to "5", "five" to "5",
        "seis" to "6", "six" to "6",
        "siete" to "7", "seven" to "7",
        "ocho" to "8", "eight" to "8",
        "nueve" to "9", "nine" to "9",

        // Letras fonéticas en dictado técnico
        "be" to "B", "bee" to "B",
        "ce" to "C", "see" to "C", "sea" to "C",
        "dee" to "D",
        "equis" to "X", "ex" to "X",
        "ye" to "Y", "why" to "Y",

        // Separadores técnicos
        "dash" to "-", "hyphen" to "-", "minus" to "-", "guion" to "-", "guión" to "-", "menos" to "-",
        "slash" to "/", "stroke" to "/", "barra" to "/", "diagonal" to "/"
    )

    // Regex para capturar la estructura de un número de parte Serie 76 en habla continua:
    // Prefijo: 7 6 [1-7] [A-E|X|Y] (opcional 00 o 30)
    // Separador: guion opcional
    // Código intermedio: 1 1 3 [0-9A-Z] ...
    // Sufijo: slash [A-Z]
    private val partRegex = Regex(
        """\b(7\s*6\s*[1-7]\s*[ABCXYabcxy]\s*(?:0\s*0|3\s*0)?)\s*[-–—]?\s*(1\s*1\s*3\s*(?:[0-9A-Za-z]\s*){4,8})(?:\s*[/]\s*([A-Za-z]))?\b"""
    )

    fun normalizeSpokenTechnicalQuery(rawTranscript: String): String {
        if (rawTranscript.isBlank()) return rawTranscript

        // 1. Mapeo token por token de símbolos técnicos
        val tokens = rawTranscript.split(Regex("""\s+"""))
        val mappedTokens = tokens.map { token ->
            val clean = token.lowercase().trim(',', '.', '!', '?', ';', ':')
            wordToSymbol[clean] ?: token
        }
        val mappedText = mappedTokens.joinToString(" ")

        // 2. Detección y reconstrucción canónica del número de parte
        return partRegex.replace(mappedText) { match ->
            var prefix = match.groupValues[1].replace(Regex("""\s+"""), "").uppercase()
            if (prefix.length == 4) {
                val sizeLetter = prefix[3]
                prefix += if (sizeLetter == 'X' || sizeLetter == 'Y') "30" else "00"
            }

            var midCode = match.groupValues[2].replace(Regex("""\s+"""), "").uppercase()
            // Asegurar longitud estándar de 8 caracteres si se trata de 113X...
            if (midCode.startsWith("113")) {
                val voltageChar = midCode.getOrNull(3) ?: '0'
                val rest = midCode.substring(4)
                if (rest.contains("C00")) {
                    midCode = "113${voltageChar}0C00"
                } else if (midCode.length < 8) {
                    midCode = midCode.padEnd(8, '0')
                } else if (midCode.length > 8) {
                    midCode = midCode.substring(0, 8)
                }
            }

            val suffixLetter = match.groupValues[3].ifEmpty { "A" }.uppercase()
            "$prefix-$midCode/$suffixLetter"
        }
    }
}
