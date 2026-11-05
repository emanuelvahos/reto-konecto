# Konecto Series 76 — Asistente de actuadores eléctricos

Asistente conversacional para consultar, comparar y recomendar los actuadores eléctricos Series 76 (catálogo de 68 modelos extraído de `docs/series_76_electric_data.pdf`). Backend FastAPI + PostgreSQL 16 y una app Android.

## Qué es y cómo funciona

1. Cada mensaje pasa primero por un **router determinista** (es/en, sin LLM) que recorta intentos de inyección, responde lo que está fuera de alcance (precio, plazos, stock) y decide qué herramienta usar.
2. Si el router no está seguro, o para redactar la respuesta, el **agente LLM** llama a tres herramientas: `lookup_actuator_by_part_number`, `recommend_actuators` y `search_engineering_knowledge`.
3. Todas las cifras salen de **PostgreSQL** (`NUMERIC` exactos, índice `pg_trgm` para typos) o de `backend/data/knowledge.json`; el LLM no calcula ni recuerda especificaciones.
4. Un **verificador numérico** comprueba que cada número de la respuesta exista en lo que devolvieron las herramientas (con la unidad correcta). Si falla dos veces, o el LLM no responde, se usa una **plantilla determinista** construida con las filas de la base de datos.
5. La respuesta incluye `ui_payload` (tarjetas, alertas, aclaraciones, seguimientos sugeridos) y `debug_trace` (herramientas, SQL, latencias, tokens).

## Requisitos

- Docker y Docker Compose v2.24 o superior (`docker compose version`).
- Puertos libres en el host: `5433` (PostgreSQL) y `8001` (API). Se pueden cambiar con `DB_HOST_PORT` y `API_HOST_PORT` en `.env`.
- Opcional: una clave de LLM (NVIDIA NIM u OpenRouter). Sin clave el backend arranca y responde en **modo degradado** (ver más abajo).
- Opcional, solo para ejecutar las pruebas desde el host: Python 3.11+ y `pip install -r backend/requirements.txt`.

## Arranque

```bash
git clone <url-del-repositorio> reto-konecto
cd reto-konecto
cp .env.example .env          # en PowerShell: Copy-Item .env.example .env
```

Edita `.env` solo si quieres respuestas redactadas por el modelo: pon `LLM_PROVIDER=nim` y la clave en `LLM_API_KEY_NIM` (o `LLM_PROVIDER=openrouter` y la clave en `LLM_API_KEY`). Si no tocas nada, todo arranca con valores de demostración y sin LLM.

```bash
docker compose up --build
```

La primera vez tarda por la construcción de la imagen. Está listo cuando el log del backend muestra `Application startup complete` y `docker compose ps` marca `series76_backend` como `healthy`.

- API: <http://localhost:8001> (Swagger: <http://localhost:8001/docs>). PostgreSQL en el host: puerto `5433`.
- Al arrancar, `scripts/ingest.py --mode auto` carga `backend/data/series76_catalog.json` (validando las reglas físicas) y siembra 68 actuadores y 3 usuarios demo; después se inicia Uvicorn.
- La imagen del backend es autosuficiente (sin bind mounts ni `--reload`); `db` y `backend` tienen healthcheck y límite de memoria (512 MB y 1 GB). Si cambias código del backend, repite `docker compose up --build`.
- Todas las variables están documentadas en `.env.example`. Las claves van siempre vacías ahí; `.env` está ignorado por git.
- Para detener: `docker compose down` (conserva los datos); `docker compose down -v` también borra el volumen de PostgreSQL.

### Verificar que funciona

Los comandos usan `curl` (en PowerShell de Windows usa `curl.exe` y comillas dobles escapadas, o ejecuta estos comandos desde Git Bash).

```bash
# 1. Salud: debe listar 68 actuadores y el proveedor/modelo activos
curl -s http://localhost:8001/health
# {"status":"ok","actuators_loaded":68,"llm_provider":"nim","llm_model":"..."}

# 2. Login demo: devuelve access_token, token_type "bearer" y el usuario
curl -s -X POST http://localhost:8001/api/auth/login   -H "Content-Type: application/json"   -d '{"email":"engineer@konecto.io","password":"Konecto2026!"}'

# 3. Una consulta
curl -s -X POST http://localhost:8001/api/conversation   -H "Content-Type: application/json"   -d '{"query":"Specs of 763B00-11300000/A","locale":"en"}'
```

Respuesta esperada de la consulta (JSON completo; resumen de los campos estables, comprobado contra el backend en ejecución):

- `intent`: `lookup`; `ui_payload.display_type`: `SINGLE_SPEC_CARD`; `ui_payload.actuators[0].base_part_number`: `763B00-11300000/A`.
- `answer`: una o dos frases con torque on/off 500 Nm (4400 in-lbs), torque modulante 380 Nm (3350 in-lbs) y potencia 90 W (cifras del catálogo, verificadas contra el oráculo).
- `verification.status`: `verified` si el LLM redactó la respuesta y pasó el verificador; `fallback_template` si respondió la plantilla (siempre en modo degradado). La redacción exacta del LLM varía de una ejecución a otra; las cifras no.

Para ejecutar las pruebas contra esa base de datos, ver «Pruebas» en la sección de ingestión.

## Backend

### Endpoints

| Método y ruta | Uso |
| --- | --- |
| `GET /health` | Estado, número de actuadores cargados, proveedor y modelo activos |
| `POST /api/auth/login` | Login opcional (JWT) |
| `POST /api/conversation` | Un turno de conversación |
| `GET /api/sessions` | Lista de sesiones (las del usuario autenticado, o las anónimas) |
| `GET /api/sessions/{id}/messages` | Historial de una sesión |
| `DELETE /api/sessions/{id}` | Borra una sesión |

### Contrato v2 (`backend/app/schemas.py`)

Petición: `{ session_id?, query, locale?: "es"|"en", input_mode?: "text"|"voice" }`.

Respuesta: `schema_version: 2`, `intent` (`lookup | recommend | knowledge | clarify | error`), `verification` (`verified | fallback_template | unverified`, cifras comprobadas y no respaldadas), `session_id`, `answer`, `ui_payload` (`display_type`: `SINGLE_SPEC_CARD | COMPARISON_TABLE | EDGE_CASE_ALERT | TEXT_ONLY | RECOMMENDATION_LIST | CLARIFICATION`; `actuators`, `alerts`, `recommendation`, `clarification`, `suggested_followups`) y `debug_trace`. Los cambios al contrato son aditivos. Ejemplos reales de cada caso: `backend/evals/fixtures/contract_v2_samples.json`.

### Sesiones multi-turno

Cada sesión guarda mensajes, los números de parte activos y los filtros activos en PostgreSQL, así que sobrevive a reinicios del contenedor (hay una prueba opt-in con reinicio real: `RUN_LIVE=1`). Los seguimientos («¿y su velocidad a 50 Hz?», «compáralo con X») se resuelven con la parte activa. Las sesiones anónimas son públicas para quien conozca el UUID; las de un usuario autenticado devuelven 403 a otro usuario.

### Casos borde cubiertos

- Número de parte con typo u OCR (`761800-…` por `761B00-…`): sugerencia solo si serie y tamaño coinciden; si no, `INVALID_PART_NUMBER` sin tarjetas.
- Modelos listados como N/A en la tabla trifásica (`761A00`, `761B00`, `762A00`, `762B00` con sufijo `11330C00/A`): se conservan con `is_available = FALSE` y se responde `MODEL_LISTED_AS_NA` con alternativas del mismo tamaño.
- Requisitos imposibles (par por encima del máximo del catálogo, 24 V con par alto, CSA en tamaños 6 y 7): diagnóstico con cifras de la base de datos.
- Petición ambigua (p. ej. falta el tipo de servicio): aclaración (`CLARIFICATION`) y se completa con la respuesta.
- Inyección de prompt, preguntas fuera de alcance, números de parte inventados o que el usuario nunca dio (`UNGROUNDED_PART_NUMBER`).
- Base de datos caída, UUID inválido, caracteres NUL, `locale` solo `es`/`en`: error controlado, no excepción.

### Modo degradado (sin LLM)

Si no hay LLM (clave vacía, proveedor caído, error 429/5xx, presupuesto de tiempo del turno agotado), el backend sigue respondiendo lo que puede resolver con la base de datos y las reglas, sin llamar al modelo:

| Consulta | Respuesta sin LLM |
| --- | --- |
| Número de parte válido o pregunta de ficha (también seguimientos sobre la parte activa) | `SINGLE_SPEC_CARD` con datos de PostgreSQL y una o dos frases de plantilla |
| Comparación de números de parte explícitos | `COMPARISON_TABLE` y una frase por modelo |
| Typo de número de parte, modelo N/A, criterios de selección completos | Tarjeta o lista de la herramienta y plantilla |
| Pregunta conceptual | Fragmento de `knowledge.json` recortado a la pregunta |
| Falta un dato para recomendar | Pregunta de aclaración (`CLARIFICATION`) |
| Fuera de alcance o inyección de prompt | Respuesta fija del router |

En los casos con tarjeta o conocimiento se añade una alerta `LLM_UNAVAILABLE` con `severity: "info"` («el asistente de lenguaje no está disponible; la respuesta se armó con los datos del catálogo») y `verification.status` es `fallback_template`. Una consulta que el router no sabe clasificar (p. ej. «cuéntame algo interesante») sí necesita el LLM: sin él devuelve `intent: "error"` con la misma alerta pero con `severity: "error"`.

Cubierto por `backend/evals/test_degraded_mode.py` (clave vacía y proveedor caído, sin llamar al LLM).

## Ingestión de datos

1. `backend/scripts/extract_from_pdf.py`: extracción por modelo de visión desde imágenes del PDF en dos pasadas independientes (A y B) y reconciliación (`backend/data/extraction/`).
2. `backend/scripts/build_catalog.py`: construye `backend/data/series76_catalog.json` con el valor acordado A=B; los desacuerdos solo se resuelven con `human_resolutions.json` y, si queda alguno sin resolver, aborta. También genera el **oráculo** `backend/evals/oracle/golden.json`.
3. `backend/scripts/ingest.py --mode auto`: lee el catálogo, aplica las reglas físicas (par in-lbs/Nm entre 8.2 y 9.5; LRA ≥ FLA; CSA falso en tamaños 6 y 7), escribe `processed_actuators.json` y siembra la base. `--mode snapshot-only` no toca PostgreSQL.

Reglas del catálogo: en todas las tablas el orden de columnas es 60 Hz | 50 Hz; los trifásicos terminan en `11330C00/A`; los de 24 V tienen sufijos propios (`11370000/A` para 24 V DC, `11380000/A` para 24 V AC/DC); la potencia del motor (celdas combinadas en el PDF) está resuelta para los 64 modelos disponibles.

El **oráculo** (`golden.json`) es independiente de lo que devuelven las herramientas: las pruebas comprueban que cada cifra de una respuesta y cada tarjeta coincidan con él.

Pruebas (desde la raíz del repo, con `docker compose up` ya en marcha para tener PostgreSQL en `localhost:5433`, y `pip install -r backend/requirements.txt`):

```bash
python -m pytest backend/evals -q    # 506 pruebas; una (test_api_e2e multiturno) llama al LLM real y falla si el proveedor no responde
python backend/evals/run_evals.py -v                   # 11 escenarios con LLM
python backend/evals/run_adversarial.py                # 30 casos adversarios con LLM
python backend/evals/run_adversarial.py --cases backend/evals/heldout.json --report backend/evals/HELDOUT_REPORT.md   # 40 casos ciegos
```

Los tres runners requieren clave de LLM en `.env`; sobrescriben sus informes `.md`. Las pruebas de `backend/evals` no necesitan clave salvo la indicada.

## Modelos por entorno

Los perfiles están en `backend/config/llm_profiles.json` y se eligen con `LLM_PROVIDER`; ni modelos ni URLs están escritos en el código.

| | Desarrollo | Entrega |
| --- | --- | --- |
| `LLM_PROVIDER` | `nim` | `openrouter` |
| Modelo | `nvidia/nemotron-3.5-lightning-30b-a3b` | `openai/gpt-4o-mini` |
| Costo | $0 (capa gratuita de NIM) | $0.15 / 1M tokens de entrada, $0.60 / 1M de salida (precio de lista) |

Justificación: NIM permite repetir cientos de corridas de evaluación sin gastar el presupuesto; OpenRouter con `gpt-4o-mini` es el candidato de entrega por su precio. Como no hay embeddings, cambiar de proveedor no exige reingestar ni tocar volúmenes. **Solo se ha medido con NIM** (ver limitaciones).

Resultados medidos (todos con NIM; los informes están en `backend/evals/`):

| Batería | Resultado |
| --- | --- |
| `EVALUATION_REPORT.md` (11 escenarios) | 11/11 |
| `ADVERSARIAL_REPORT.md` (30 casos) | 30/30 |
| `HELDOUT_REPORT.md` (40 casos escritos sin acceso al router) | 39/40 en la corrida final; 32/40 en la primera, antes de las correcciones generales |

## Pantalla de depuración y credenciales demo

La app tiene una pantalla oculta de telemetría (herramientas llamadas, SQL, latencias, tokens, entidades activas de la sesión). Se abre con una **pulsación larga sobre el título** de la barra superior del chat.

Usuarios demo (sembrados por `ingest.py`; las contraseñas se pueden cambiar con `DEMO_PASSWORD_*` en `.env`):

| Correo | Contraseña por defecto |
| --- | --- |
| `engineer@konecto.io` | `Konecto2026!` |
| `supervisor@konecto.io` | `Series76Pass!` |
| `admin@konecto.io` | `AdminKonecto!` |

Son credenciales de demostración, igual que `JWT_SECRET_KEY=demo-only-change-me` y la contraseña de PostgreSQL por defecto: cámbialas fuera de una demo local.

## Diseño y trade-offs

- **Router determinista antes del LLM.** Resuelve sin modelo las consultas con estructura clara (número de parte, criterios numéricos, conceptos, fuera de alcance, inyección). Reduce latencia y variabilidad, pero son reglas escritas a mano solo para español e inglés, y los casos que no reconoce pasan al LLM.
- **Verificador numérico.** Cumple la regla «ningún número visible viene del LLM». Es estricto (cifra + unidad + fila citada), por lo que a veces descarta respuestas correctas y entra la plantilla; es un costo aceptado frente a mostrar una cifra no respaldada. Excepciones configurables en `config/verifier.json`.
- **Plantillas de respaldo.** Respuestas de 1–2 frases armadas solo con filas de la base de datos (`fallback.py`, textos en `i18n.py`). Son menos naturales que las del LLM pero no pueden inventar cifras, y mantienen el servicio útil si el proveedor falla.
- **SQL + `pg_trgm` en lugar de RAG vectorial.** Los 68 números de parte difieren en 1–2 caracteres y las consultas son desigualdades sobre columnas numéricas (`modulating_torque_nm >= 200 AND voltage_num = 24`); un índice de embeddings no las evalúa de forma determinista. **pgvector se retiró** en la fase 2A: el conocimiento (4 fragmentos de `series_76_summary.pdf` y notas de tabla) vive en `backend/data/knowledge.json` y se busca por palabras clave con `pg_trgm` para typos. Si falla, la herramienta devuelve `KNOWLEDGE_ERROR`, nunca todos los fragmentos.
- **Telemetría con `ContextVar`.** Las herramientas mutan en sitio contenedores creados al inicio del turno (LangChain las ejecuta en contextos copiados); ver `.claude/CLAUDE.md` §3.

## Opcionales

- **Login multiusuario**: JWT (HS256, 7 días por defecto) y sesiones asociadas a `chat_sessions.user_id`. El uso sin login sigue funcionando.
- **Voz**: el reconocimiento y la normalización de números de parte dictados en la app (`VoiceNormalizer.kt`) corren en el dispositivo sin costo de LLM. El backend repite una normalización determinista (`normalize_spoken_pn` en el router) para números dictados con palabras en es/en.

## Limitaciones conocidas

- **HLD-20 y seguimientos ambiguos.** En la batería ciega falla un seguimiento («¿alguno de esos modelos trifásicos pequeños sirve?» tras un N/A): el router lo clasifica `uncertain`, decide el LLM y su respuesta habla de alternativos monofásicos sin decir que los trifásicos no están disponibles. No se corrigió con una regla general.
- **El router solo cubre español e inglés.** Otro idioma pasa al LLM sin las protecciones previas.
- **Variabilidad de NIM.** La capa gratuita es no determinista y a veces falla o tarda; hay reintentos con retroceso y, si no responde, plantilla. Una misma batería puede variar de una corrida a otra (la batería ciega dio 36/40, 36/40, 38/40 y 37–39/40 en distintas corridas).
- **Tasas medidas solo con NIM.** Los resultados de arriba corresponden a `nvidia/nemotron-3.5-lightning-30b-a3b`. No hay corrida con OpenRouter todavía; no se afirma latencia ni tasa de acierto para `gpt-4o-mini`.
- **Dictado de números con palabras fuera de la tabla.** La normalización solo cubre las palabras de dígitos, letras y separadores que reconoce (es/en); si falta un dígito o hay palabras de relleno, la app propone el modelo más cercano y lo avisa en lugar de adivinar.
- **Modo degradado.** Las respuestas de plantilla son más rígidas que las del LLM y las consultas que el router no clasifica no se pueden contestar sin modelo. Las cifras son las mismas (vienen de la base de datos), no la redacción. Esta ruta se probó con pruebas automáticas, no con una corrida de las baterías sin LLM.
- La batería ciega tiene 40 casos y los adversarios 30: sirven para detectar regresiones, no son una estimación estadística de la tasa de acierto real.
- La batería ciega completa no se repitió tras el último cambio menor del verificador (ver `HELDOUT_REPORT.md`).

## App Android

<!-- APP: Gemini -->
<!-- Datos del backend ya conocidos, para completar esta sección:
- URL del servidor desde el emulador: http://10.0.2.2:8001/ (por defecto en la app; editable en la pantalla de login)
- Dispositivo físico por USB: `adb reverse tcp:8001 tcp:8001` y usar http://localhost:8001/ ; por Wi-Fi: http://<IP-de-la-PC>:8001/
- Directorio del proyecto: mobile-app/ (Android Studio, Gradle). Paquete único io.konecto.series76.
- Pantalla de depuración: pulsación larga sobre el título de la barra superior del chat.
- Usuarios demo: ver sección «Pantalla de depuración y credenciales demo».
-->

## Estructura del repositorio

```text
.
├── .claude/               # Reglas de ingeniería (CLAUDE.md), permisos y comandos de verificación
├── backend/
│   ├── app/               # main, agent, router, verifier, fallback, tools, recommend, followups, i18n, schemas, auth, database
│   ├── config/            # llm_profiles.json, verifier.json
│   ├── data/              # series76_catalog.json, processed_actuators.json, knowledge.json, extraction/ (provenance)
│   ├── db/init.sql        # esquema (actuators, users, chat_sessions, chat_messages)
│   ├── scripts/           # extract_from_pdf.py, build_catalog.py, ingest.py, build_contract_samples.py
│   └── evals/             # pruebas, runners, oráculo, informes
├── docs/                  # PDFs de origen
├── mobile-app/            # App Android (Kotlin + Jetpack Compose)
├── docker-compose.yml
└── .env.example
```
