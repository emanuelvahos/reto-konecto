-- 1. Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Tabla de Usuarios (para el feature opcional de Login)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'plant_engineer',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla Maestra de Actuadores Serie 76 (Datos Estructurados Exactos)
CREATE TABLE IF NOT EXISTS actuators (
    id SERIAL PRIMARY KEY,
    base_part_number VARCHAR(64) NOT NULL,       -- Ej: 761A00-11300000/A; 3-fase: 763A00-11330C00/A (sin '*' de nota al pie)
    normalized_part_number VARCHAR(64) NOT NULL, -- Sin guiones ni barras para bÃºsqueda rÃ¡pida
    size_code VARCHAR(16) NOT NULL,              -- Ej: 761A, 761B, 762X, etc.
    frame_size INTEGER NOT NULL,                 -- 1 al 7 (para filtrar Nota de TamaÃ±os 6 y 7)
    enclosure_type VARCHAR(32) NOT NULL,         -- 'Weatherproof' | 'Explosionproof'
    power_supply VARCHAR(64) NOT NULL,           -- '110V Single Phase' | '220V Single Phase' | '220V 3 Phase' | '24V AC/DC' | '24V DC'
    voltage_num INTEGER NOT NULL,                -- 24, 110, 220
    phase_type VARCHAR(32) NOT NULL,             -- 'Single Phase', '3 Phase', 'AC/DC', 'DC'
    service_support VARCHAR(64) NOT NULL,        -- 'Both On/Off & Modulating', 'On/Off Only', 'Modulating Only'
    is_available BOOLEAN NOT NULL DEFAULT TRUE,  -- FALSE para las filas N/A en 220V 3-Phase

    -- MÃ©tricas On/Off
    on_off_torque_in_lbs NUMERIC(10, 2),
    on_off_torque_nm NUMERIC(10, 2),
    on_off_duty_cycle_pct INTEGER,
    cycles_per_hour INTEGER,

    -- MÃ©tricas Modulating
    modulating_torque_in_lbs NUMERIC(10, 2),
    modulating_torque_nm NUMERIC(10, 2),
    modulating_duty_cycle_pct INTEGER,
    starts_per_hour INTEGER,

    -- Velocidad de OperaciÃ³n (90 grados en segundos)
    speed_60hz_sec NUMERIC(8, 2),
    speed_50hz_sec NUMERIC(8, 2),
    speed_dc_or_fixed_sec NUMERIC(8, 2),

    -- Corriente a Plena Carga (FLA en Amperios)
    fla_60hz_amps NUMERIC(8, 2),
    fla_50hz_amps NUMERIC(8, 2),
    fla_dc_or_fixed_amps NUMERIC(8, 2),

    -- Corriente de Rotor Bloqueado (LRA en Amperios)
    lra_60hz_amps NUMERIC(8, 2),
    lra_50hz_amps NUMERIC(8, 2),
    lra_dc_or_fixed_amps NUMERIC(8, 2),

    -- Potencia del Motor (resuelta desde celdas combinadas / rowspans)
    motor_power_watts INTEGER,

    -- Certificaciones y Notas de PÃ¡gina
    csa_certified BOOLEAN NOT NULL DEFAULT TRUE,
    ce_ukca_certified BOOLEAN NOT NULL DEFAULT FALSE,
    hazardous_classification TEXT,
    table_notes JSONB DEFAULT '[]'::jsonb,
    source_page INTEGER NOT NULL,
    source_method TEXT,

    UNIQUE(base_part_number, power_supply, service_support)
);

-- Ãndices para bÃºsqueda instantÃ¡nea y tolerancia a typos (pg_trgm)
CREATE INDEX IF NOT EXISTS idx_actuators_part_trgm ON actuators USING gin (base_part_number gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_actuators_enclosure ON actuators(enclosure_type);
CREATE INDEX IF NOT EXISTS idx_actuators_power ON actuators(power_supply);
CREATE INDEX IF NOT EXISTS idx_actuators_torque_onoff ON actuators(on_off_torque_nm);
CREATE INDEX IF NOT EXISTS idx_actuators_torque_mod ON actuators(modulating_torque_nm);

-- 4. (Retirado) knowledge_chunks/pgvector: el conocimiento vive en backend/data/knowledge.json

-- 5. Tablas de Persistencia de Conversaciones Multi-Turno
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL DEFAULT 'New Actuator Consultation',
    active_part_numbers JSONB DEFAULT '[]'::jsonb, -- Memoria de entidades para preguntas de seguimiento
    active_filters JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    ui_payload JSONB DEFAULT '{}'::jsonb,   -- Datos estructurados para las tarjetas en la App Android
    debug_trace JSONB DEFAULT '{}'::jsonb,  -- Trazas de tools, SQL y latencia para la Debug Screen
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id, created_at ASC);

-- Los usuarios de prueba (bcrypt) los siembra backend/scripts/ingest.py

