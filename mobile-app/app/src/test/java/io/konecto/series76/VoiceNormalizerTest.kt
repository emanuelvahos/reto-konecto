package io.konecto.series76

import io.konecto.series76.util.VoiceNormalizer
import org.junit.Assert.assertEquals
import org.junit.Test

class VoiceNormalizerTest {

    @Test
    fun testSpanishDictationStandardSinglePhase() {
        val input = "siete seis tres B cero cero guion uno uno tres cero cero cero cero slash A"
        val expected = "763B00-11300000/A"
        val actual = VoiceNormalizer.normalizeSpokenTechnicalQuery(input)
        assertEquals(expected, actual)
    }

    @Test
    fun testSpanishDictationThreePhaseWithC00() {
        val input = "siete seis uno A cero cero guion uno uno tres tres cero C cero cero slash A"
        val expected = "761A00-11330C00/A"
        val actual = VoiceNormalizer.normalizeSpokenTechnicalQuery(input)
        assertEquals(expected, actual)
    }

    @Test
    fun testEnglishDictationStandard() {
        val input = "seven six three B zero zero dash one one three zero zero zero zero slash A"
        val expected = "763B00-11300000/A"
        val actual = VoiceNormalizer.normalizeSpokenTechnicalQuery(input)
        assertEquals(expected, actual)
    }

    @Test
    fun testEnglishDictationThreePhaseWithC00() {
        val input = "seven six one A zero zero hyphen one one three three zero C zero zero slash A"
        val expected = "761A00-11330C00/A"
        val actual = VoiceNormalizer.normalizeSpokenTechnicalQuery(input)
        assertEquals(expected, actual)
    }

    @Test
    fun testContextualPhrasePreservation() {
        val input = "Dame especificaciones de siete seis tres B cero cero guion uno uno tres cero cero cero cero slash A por favor"
        val expected = "Dame especificaciones de 763B00-11300000/A por favor"
        val actual = VoiceNormalizer.normalizeSpokenTechnicalQuery(input)
        assertEquals(expected, actual)
    }

    @Test
    fun testShortModelCodeAutoExpansion() {
        // Dictado abreviado común en planta: "siete seis tres B guion uno uno tres cero cero cero cero slash A"
        val input = "siete seis tres B guion uno uno tres cero cero cero cero slash A"
        val expected = "763B00-11300000/A"
        val actual = VoiceNormalizer.normalizeSpokenTechnicalQuery(input)
        assertEquals(expected, actual)
    }
}

