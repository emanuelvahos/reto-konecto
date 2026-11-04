package io.konecto.series76

import io.konecto.series76.data.ServerPreferences
import org.junit.Assert.*
import org.junit.Test

class ServerConfigTest {

    @Test
    fun testNormalizeUrl() {
        assertEquals("http://10.0.2.2:8001/", ServerPreferences.normalizeUrl("10.0.2.2:8001"))
        assertEquals("http://10.0.2.2:8001/", ServerPreferences.normalizeUrl("http://10.0.2.2:8001"))
        assertEquals("https://api.konecto.io/", ServerPreferences.normalizeUrl("https://api.konecto.io"))
        assertEquals("http://192.168.1.50:8001/", ServerPreferences.normalizeUrl("  192.168.1.50:8001  "))
    }

    @Test
    fun testIsValidUrl() {
        assertTrue(ServerPreferences.isValidUrl("http://10.0.2.2:8001/"))
        assertTrue(ServerPreferences.isValidUrl("10.0.2.2:8001"))
        assertTrue(ServerPreferences.isValidUrl("http://localhost:8001"))
        assertTrue(ServerPreferences.isValidUrl("https://konecto.io/api"))
        assertTrue(ServerPreferences.isValidUrl("192.168.0.12:8001"))
        assertFalse(ServerPreferences.isValidUrl("   "))
        assertFalse(ServerPreferences.isValidUrl("http://"))
    }
}
