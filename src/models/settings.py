"""
Settings Manager Model
Provides typed, clean access to the key-value settings table.
"""

import sqlite3
from typing import Optional, Dict, Any

class SettingsRepository:
    def __init__(self, db_path: str = "workout_app.db", user_id: str = "default_user"):
        self.db_path = db_path
        self.user_id = user_id

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_settings WHERE user_id = ? AND key = ?", (self.user_id, key,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return default

    def set_setting(self, key: str, value: str, description: Optional[str] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_settings (user_id, key, value, description, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, key) DO UPDATE SET
                    value = excluded.value,
                    description = COALESCE(excluded.description, user_settings.description),
                    updated_at = CURRENT_TIMESTAMP
            """, (self.user_id, key, value, description))
            conn.commit()

    def get_all_settings(self) -> Dict[str, str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_settings WHERE user_id = ?", (self.user_id,))
            rows = cursor.fetchall()
            return {r[0]: r[1] for r in rows}

    def get_selected_ollama_model(self, fallback: str = "qwen3:14b") -> str:
        return self.get_setting("selected_ollama_model", fallback)

    def set_selected_ollama_model(self, model_name: str):
        self.set_setting("selected_ollama_model", model_name, "Active Ollama model")

    def get_ollama_base_url(self, fallback: str = "http://localhost:11434") -> str:
        return self.get_setting("ollama_base_url", fallback)

    def set_ollama_base_url(self, url: str):
        self.set_setting("ollama_base_url", url, "Base URL for Ollama service")

    def get_sparky_base_url(self, fallback: str = "http://localhost:8080") -> str:
        return self.get_setting("sparky_base_url", fallback)

    def set_sparky_base_url(self, url: str):
        self.set_setting("sparky_base_url", url, "Base URL for SparkyFitness instance")

    def get_sparky_api_token(self, fallback: str = "") -> str:
        return self.get_setting("sparky_api_token", fallback)

    def set_sparky_api_token(self, token: str):
        self.set_setting("sparky_api_token", token, "Bearer token for authenticating with SparkyFitness API")

    def get_unit_preference(self, fallback: str = "lb") -> str:
        return self.get_setting("default_unit_preference", fallback)

    def set_unit_preference(self, unit: str):
        self.set_setting("default_unit_preference", unit, "Weight unit preference (lbs or kg)")

    def get_training_goal(self, fallback: str = "Hypertrophy (Muscle Growth)") -> str:
        return self.get_setting("training_goal", fallback)

    def set_training_goal(self, goal: str):
        self.set_setting("training_goal", goal, "Primary training goal")

    def get_experience_level(self, fallback: str = "Intermediate (1-3 yrs)") -> str:
        return self.get_setting("experience_level", fallback)

    def set_experience_level(self, level: str):
        self.set_setting("experience_level", level, "Lifter experience level")

    def get_days_per_week(self, fallback: str = "4") -> str:
        return self.get_setting("days_per_week", fallback)

    def set_days_per_week(self, days: str):
        self.set_setting("days_per_week", str(days), "Preferred weekly workout frequency")

    def get_body_weight(self, fallback: float = 145.0) -> float:
        val = self.get_setting("body_weight", str(fallback))
        try:
            return float(val) if val else fallback
        except (ValueError, TypeError):
            return fallback

    def set_body_weight(self, weight: float):
        self.set_setting("body_weight", str(weight), "Athlete body weight")

