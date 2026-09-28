-- =============================================================================
-- Database Schema Definition (SQLite & PostgreSQL compatible)
-- Self-Hosted Progressive Overload & Nutrition Workout App
-- Strictly mirrors architecture.md specification
-- =============================================================================

-- 1. Key-Value Settings Table

CREATE TABLE IF NOT EXISTS user_settings (
    user_id VARCHAR(36) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, key)
);


-- Seed Default Settings
INSERT OR IGNORE INTO user_settings (user_id, key, value, description)
VALUES 
    ('default_user', 'selected_ollama_model', 'qwen3:14b', 'Selected local Ollama LLM model for progressive overload and recovery'),
    ('default_user', 'ollama_base_url', 'http://localhost:11434', 'Base URL for Ollama service'),
    ('default_user', 'sparky_base_url', 'http://localhost:8080', 'Base URL for SparkyFitness instance'),
    ('default_user', 'sparky_api_token', '', 'Bearer token for authenticating with SparkyFitness API'),
    ('default_user', 'default_unit_preference', 'kg', 'Default weight unit preference (kg or lbs)'),
    ('default_user', 'double_progression_threshold_rpe', '8.5', 'Maximum RPE at top rep target before triggering weight increment');

-- 2. Users Table
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    name VARCHAR(128) NOT NULL,
    unit_preference VARCHAR(8) DEFAULT 'kg',
    settings TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Exercises Table
CREATE TABLE IF NOT EXISTS exercises (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    name VARCHAR(128) NOT NULL,
    category VARCHAR(64) NOT NULL, -- barbell, dumbbell, machine, cable, bodyweight
    primary_muscle VARCHAR(64) NOT NULL,
    secondary_muscles TEXT DEFAULT '[]', -- JSON array of strings
    is_custom BOOLEAN DEFAULT 0,
    description TEXT DEFAULT '',
    equipment VARCHAR(64) DEFAULT '',
    animation_svg TEXT DEFAULT '',
    images TEXT DEFAULT '[]', -- JSON array of local/wger image URLs
    muscle_ids TEXT DEFAULT '[]', -- JSON array of wger muscle IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 4. Routines & Templates Table
CREATE TABLE IF NOT EXISTS routines (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    title VARCHAR(128) NOT NULL,
    description TEXT,
    schedule_days TEXT DEFAULT '[]', -- JSON array e.g. ["Monday", "Thursday"] or ["Day 1"]
    is_archived BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 5. Routine Exercises Join Table
CREATE TABLE IF NOT EXISTS routine_exercises (
    id VARCHAR(36) PRIMARY KEY,
    routine_id VARCHAR(36) NOT NULL,
    exercise_id VARCHAR(36) NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0,
    target_sets INTEGER NOT NULL DEFAULT 3,
    min_reps INTEGER NOT NULL DEFAULT 8,
    max_reps INTEGER NOT NULL DEFAULT 12,
    rest_seconds INTEGER DEFAULT 90,
    FOREIGN KEY (routine_id) REFERENCES routines(id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
);

-- 6. Workout Sessions Table
CREATE TABLE IF NOT EXISTS workout_sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    routine_id VARCHAR(36),
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'in_progress', -- in_progress, completed, discarded
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    notes TEXT,
    source VARCHAR(32) DEFAULT 'mobile_pwa', -- mobile_pwa, watch, web
    sync_id VARCHAR(64) UNIQUE, -- Client/offline idempotency key
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (routine_id) REFERENCES routines(id) ON DELETE SET NULL
);

-- 7. Workout Exercises Table
CREATE TABLE IF NOT EXISTS workout_exercises (
    id VARCHAR(36) PRIMARY KEY,
    workout_session_id VARCHAR(36) NOT NULL,
    exercise_id VARCHAR(36) NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (workout_session_id) REFERENCES workout_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
);

-- 8. Exercise Sets Table (Logged Sets)
CREATE TABLE IF NOT EXISTS exercise_sets (
    id VARCHAR(36) PRIMARY KEY,
    workout_exercise_id VARCHAR(36) NOT NULL,
    set_number INTEGER NOT NULL,
    set_type VARCHAR(32) DEFAULT 'working', -- warmup, working, dropset, failure
    weight NUMERIC(7, 2) NOT NULL DEFAULT 0.0,
    reps INTEGER NOT NULL DEFAULT 0,
    rpe NUMERIC(3, 1), -- Rate of Perceived Exertion (1.0 to 10.0)
    rest_after_seconds INTEGER DEFAULT 90,
    is_completed BOOLEAN DEFAULT 1,
    completed_at TIMESTAMP,
    sync_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workout_exercise_id) REFERENCES workout_exercises(id) ON DELETE CASCADE
);

-- 9. AI Recommendations & Feedback Summaries
CREATE TABLE IF NOT EXISTS ai_recommendations (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    workout_exercise_id VARCHAR(36),
    recommendation_type VARCHAR(64) NOT NULL, -- progressive_overload, recovery_nutrition
    input_context TEXT NOT NULL, -- JSON snapshot of past volume, macros, RPE
    suggested_targets TEXT NOT NULL, -- JSON formatted weight, reps, sets, rationale
    raw_response TEXT,
    model_used VARCHAR(128) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (workout_exercise_id) REFERENCES workout_exercises(id) ON DELETE SET NULL
);

-- 10. Daily Nutrition Summaries (SparkyFitness Ingestion)
CREATE TABLE IF NOT EXISTS nutrition_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    log_date DATE NOT NULL,
    calories NUMERIC(7, 2) NOT NULL DEFAULT 0.0,
    protein_grams NUMERIC(6, 2) NOT NULL DEFAULT 0.0,
    carbs_grams NUMERIC(6, 2) NOT NULL DEFAULT 0.0,
    fat_grams NUMERIC(6, 2) NOT NULL DEFAULT 0.0,
    water_ml NUMERIC(7, 2) DEFAULT 0.0,
    raw_sparky_payload TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, log_date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 11. Watch Devices Pairing Table
CREATE TABLE IF NOT EXISTS watch_devices (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    device_id VARCHAR(128) NOT NULL,
    device_type VARCHAR(32) NOT NULL, -- wear_os, apple_watch
    device_name VARCHAR(128),
    pairing_token VARCHAR(255) NOT NULL,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, device_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for fast queries & analytics
CREATE INDEX IF NOT EXISTS idx_workout_sessions_user_date ON workout_sessions(user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_exercise_sets_exercise ON exercise_sets(workout_exercise_id);
CREATE INDEX IF NOT EXISTS idx_nutrition_logs_user_date ON nutrition_logs(user_id, log_date);
CREATE INDEX IF NOT EXISTS idx_ai_recs_user ON ai_recommendations(user_id, created_at);

-- 12. AI Coach Chat Messages Table (Persistent Conversation History)
CREATE TABLE IF NOT EXISTS coach_messages (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    role VARCHAR(16) NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,
    thought TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_coach_messages_user_created ON coach_messages(user_id, created_at);
