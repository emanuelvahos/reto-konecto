# Galería de Capturas de Pantalla y Auditoría Visual — Series 76 Assistant

Este documento certifica la auditoría visual y funcional exhaustiva de la aplicación móvil nativa Android (**Series 76 Assistant**) operando contra el backend real (FastAPI + OpenRouter LLM) sobre el dispositivo físico **Redmi Note 9S** (resolución nativa 1080 × 2400 px, Android 11 / MIUI).

---

## 1. Tabla Resumen de Capturas Oficiales

| # | Archivo | Descripción Funcional | Resolución | Tema | Barra de Estado Limpia |
|---|---|---|---|---|---|
| 01 | [`01-login.png`](01-login.png) | Pantalla de inicio de sesión con branding y botón de acceso rápido | 1080 × 2400 | Oscuro | ✓ (10:00 AM, 100% bat, sin notif.) |
| 02 | [`02-sesiones.png`](02-sesiones.png) | Historial de consultas técnicas con números de parte completos en FlowRow | 1080 × 2400 | Oscuro | ✓ (10:00 AM, 100% bat, sin notif.) |
| 03 | [`03-ficha-actuador.png`](03-ficha-actuador.png) | Ficha técnica de actuador con relojes de torque, especificaciones e insignia de datos | 1080 × 2400 | Oscuro | ✓ (10:00 AM, 100% bat, sin notif.) |
| 04 | [`04-comparacion.png`](04-comparacion.png) | Comparativa directa entre 763B00-11300000/A y 764B00-11300000/A con marcadores ▲/▼ | 1080 × 2400 | Oscuro | ✓ (10:00 AM, 100% bat, sin notif.) |
| 05 | [`05-ficha-completa.png`](05-ficha-completa.png) | ModalBottomSheet con insets seguros sobre barra de navegación del sistema y scroll al final | 1080 × 2400 | Oscuro | ✓ (10:00 AM, 100% bat, sin notif.) |
| 06 | [`06-voz-escuchando.png`](06-voz-escuchando.png) | Diálogo de voz en estado activo «Te escucho» con onda/micrófono interactivo | 1080 × 2400 | Oscuro | ✓ (10:00 AM, 100% bat, sin notif.) |
| 07 | [`07-alerta.png`](07-alerta.png) | Manejo de modelo N/A (761A00-11330C00/A) con alerta única y tabla de alternativas completa | 1080 × 2400 | Oscuro | ✓ (10:00 AM, 100% bat, sin notif.) |
| 08 | [`08-modo-claro.png`](08-modo-claro.png) | Misma comparativa técnica 763B vs 764B visualizada en tema claro de alto contraste | 1080 × 2400 | Claro | ✓ (10:00 AM, 100% bat, sin notif.) |
| 09 | [`09-saludo.png`](09-saludo.png) | Saludo «hola, que puedes hacer?», chips sugeridos y SIN insignia «Datos verificados» | 1080 × 2400 | Oscuro | ✓ (10:00 AM, 100% bat, sin notif.) |

---

## 2. Auditoría Visual Detallada por Captura

### 01-login.png
- **Elementos Visibles:**
  - Logotipo e isotipo del actuador industrial Serie 76 con detalles de la aguja ranurada y cuerpo protector.
  - Título `Series 76 Assistant` con subtítulo técnico `Referencia Técnica de Ingeniería de Planta`.
  - Campos de entrada: Correo Electrónico corporativo prellenado (`engineer@konecto.io`) y Contraseña (`••••••••••`).
  - Campo URL de Conexión: `http://localhost:8001/` con botón `Cambiar`.
  - Botón secundario rápido: `Usar cuenta demo`.
  - Botón primario de acción: `Iniciar Sesión` en acento amarillo industrial.
  - Enlace inferior: `Continuar sin iniciar sesión`.
- **Barra de Estado:** 10:00 AM, 100 % batería, sin notificaciones personales ni íconos ajenos.

### 02-sesiones.png
- **Elementos Visibles:**
  - Cabecera: `Consultas`, usuario activo `Lead Plant Engineer • engineer@konecto.io`.
  - Iconos de acción rápida: Cambio de tema (sol), Configuración del servidor (engranaje), Actualizar (flecha circular), Salir.
  - Tarjetas de historial de conversación real con fecha y conteo de mensajes:
    - Tarjetas con múltiples números de parte completos (`761A00-11300000/A`, `761A00-11320000/A`, `763B00-11300000/A`, etc.) formateados mediante `FlowRow` sin truncamientos ni elipsis.
  - Botón flotante inferior: `+ Nueva Consulta` (Extended FAB en amarillo).
- **Barra de Estado:** 10:00 AM, 100 % batería, sin notificaciones.

### 03-ficha-actuador.png
- **Elementos Visibles:**
  - Cabecera con título del actuador consultado (`763B00-11300000/A`).
  - Insignia `✓ Datos verificados` en verde esmeralda.
  - Respuesta técnica del asistente en lenguaje natural.
  - Tarjeta de especificaciones con badges `🛡 WEATHERPROOF`, `⚡ 110V Single Phase`, `✓ Certificado CSA`.
  - Indicadores de torque On/Off (500 Nm) y Modulante (380 Nm) con arcos porcentuales legibles.
  - Mini tabla 60 Hz / 50 Hz con tiempos de giro y corrientes.
  - Botón de acción: `ℹ Ver ficha completa`.
- **Barra de Estado:** 10:00 AM, 100 % batería, sin notificaciones.

### 04-comparacion.png
- **Elementos Visibles:**
  - Consulta en nueva sesión: `compara el 763B00-11300000/A y el 764B00-11300000/A`.
  - Insignia `✓ Datos verificados` presente.
  - Respuesta del asistente mencionando explícitamente ambos modelos:
    `El 763B00-11300000/A tiene un torque de 500 Nm y una potencia de 90 W, mientras que el 764B00-11300000/A ofrece 1100 Nm y 180 W.`
  - Cabecera: `COMPARATIVA SERIE 76`, `2 Actuadores Seleccionados`, badge `60 Hz | 50 Hz`.
  - Tabla comparativa de 2 columnas completas (`763B00-11300000/A` vs `764B00-11300000/A`):
    - Parámetros: Número de parte, Carcasa, Alimentación, Torque On/Off (▼ 500 Nm vs ▲ 1100 Nm), Torque modulante (con wrap en 2 líneas: ▼ 380 Nm vs ▲ 930 Nm), Ciclo (On/Mod), Tiempo de giro (▼ 26.0s|32.0s vs ▲ 36.0s|43.0s), FLA, LRA, Potencia (▼ 90 W vs ▲ 180 W), Certificación (✓ CSA).
    - Marcadores dinámicos ▲/▼ destacando valores superiores e inferiores.
    - Botón `Copiar comparativa`.
  - Barra de texto inferior despejada (sin teclado abierto en pantalla).
- **Barra de Estado:** 10:00 AM, 100 % batería, sin notificaciones.

### 05-ficha-completa.png
- **Elementos Visibles:**
  - Hoja modal inferior (`ModalBottomSheet`) desplegada sobre la conversación.
  - Drag handle centrado.
  - Título `Ficha Técnica Serie 76` y modelo `763A00-11330C00/A` en amarillo acento.
  - Botones de acción rápida: Copiar número de parte y Compartir.
  - Desglose detallado de Especificaciones Mecánicas (Frame 3, Weatherproof, 3 Phase, Torque 300 Nm, Ciclo 70%, 39 ciclos/h, 1200 arranques/h).
  - Desglose de Especificaciones Eléctricas (220V 3 Phase, 40 W, Tiempos 26.0s / 32.0s, FLA 1.0A / 1.0A, LRA 1.2A / 1.2A).
  - Normativas y Certificaciones (✓ Certified UL 429 / CSA C22.2 No. 139).
  - Bloque final con cita de catálogo: `Fuente: Series 76 electric data, pág. 2`.
  - **Ajuste de insets:** El botón de fuente y las últimas filas terminan limpiamente por encima de los tres botones de navegación del sistema (gestos/botones), sin quedar solapadas ni recortadas.
- **Barra de Estado:** 10:00 AM, 100 % batería, sin notificaciones.

### 06-voz-escuchando.png
- **Elementos Visibles:**
  - Diálogo modal de reconocimiento por voz capturado activamente.
  - Título exacto: **`Te escucho`** (no «Preparando...»).
  - Círculo central con icono de micrófono activo en color amarillo acento.
  - Subtítulo: `Dicte números de parte o consultas en español o inglés`.
  - Botones de acción: `Cancelar` y `Detener` (en amarillo acento).
  - Fondo oscurecido con la comparativa detrás.
- **Barra de Estado:** 10:00 AM, 100 % batería, sin notificaciones.

### 07-alerta.png
- **Elementos Visibles:**
  - Consulta: `specs del 761A00-11330C00/A`.
  - Insignia `✓ Datos verificados`.
  - Respuesta explicativa:
    `El modelo 761A00-11330C00/A está listado como N/A en la tabla de 220V 3 Fases. Las alternativas disponibles del tamaño 761A son: 761A00-11300000/A: 110V Monofásico, Torque On/Off: 80 Nm, Velocidad a 60 Hz: 17 s.`
  - Alerta de caso de borde:
    - Tarjeta ámbar con icono `⚠️`.
    - Título: `No disponible en esta tabla`.
    - Detalle: `761A00-11330C00/A figura como N/D en la tabla 220V 3 Phase. Se muestran alternativas disponibles del tamaño 761A.`
    - **Alerta única**, sin duplicidad.
  - Tabla comparativa de alternativas del tamaño 761A (`761A00-11300000/A` vs `761A00-11320000/A`) ajustada completamente a lo ancho sin recorte horizontal ni necesidad de scroll.
  - Sin teclado abierto tapando el contenido.
- **Barra de Estado:** 10:00 AM, 100 % batería, sin notificaciones.

### 08-modo-claro.png
- **Elementos Visibles:**
  - Idéntica comparativa técnica 763B00-11300000/A vs 764B00-11300000/A conmutada al tema claro.
  - Fondo blanco perla con tarjetas y celdas en gris azulado de alto contraste.
  - Icono de media luna naranja en la barra superior para volver a modo oscuro.
  - Insignia de datos verificados, marcadores ▲/▼ en dorado y azul, y texto en negro carbón completamente legible.
- **Barra de Estado:** 10:00 AM, 100 % batería, sin notificaciones.

### 09-saludo.png
- **Elementos Visibles:**
  - Consulta en consulta nueva: `hola, que puedes hacer?`.
  - Respuesta del asistente detallando sus capacidades técnicas:
    `Puedo darte la ficha de un modelo a partir de su número de parte, comparar modelos, recomendar actuadores según voltaje, torque, zona clasificada, tipo de servicio y otros requisitos, y explicar conceptos como el ciclo S4, FLA y LRA. No tengo precios, plazos de entrega, stock, garantía ni datos de otras marcas.`
  - **Insignia «Datos verificados» ausente** (cumpliendo estrictamente la directiva de no mostrarla en consultas generales/saludos).
  - Chips sugeridos interactivos al pie: `Ficha de un modelo ↗`, `Recomendar un actuador ↗`, `Comparar dos modelos ↗`.
  - Sin teclado en pantalla.
- **Barra de Estado:** 10:00 AM, 100 % batería, sin notificaciones.

---

## 3. Entrega del APK Release

- **Nombre del artefacto entregable:** `series76-assistant.apk`
- **Ruta de instalación:** `C:\Users\Admin\Desktop\series76-assistant.apk`
- **Ruta en workspace:** `mobile-app\app\build\outputs\apk\release\app-release.apk`
- **Tamaño exacto:** **12,296,241 bytes** (~11.73 MB)
- **Firma:** Variante `release` firmada con la clave debug/release para instalación directa en dispositivos físicos.
- **Seguridad y Producción:**
  - Interruptor de Mock: **Deshabilitado / Inexistente en release**.
  - Banners de depuración: **Completamente eliminados**.
  - Conexión: Retrofit2 + OkHttp3 apuntando por defecto al stack real FastAPI / OpenRouter.

---

## 4. Verificación de Compilación y Tests
- `./gradlew testDebugUnitTest`: Exitoso (100% pruebas unitarias superadas).
- `./gradlew testReleaseUnitTest`: Exitoso.
- Gradle Daemon detenido formalmente tras las verificaciones (`./gradlew --stop`).
