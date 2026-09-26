"""
Settings Manager Model
Provides typed, clean access to the key-value settings table.
"""

import sqlite3
from typing import Optional, Dict, Any

class SettingsRepository:
    def __init__(self, db_path: str = "workout_app.db"):
        self.db_path = db_path

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return default

    def set_setting(self, key: str, value: str, description: Optional[str] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO app_settings (key, value, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    description = COALESCE(excluded.description, app_settings.description),
                    updated_at = CURRENT_TIMESTAMP
            """, (key, value, description))
            conn.commit()

    def get_all_settings(self) -> Dict[str, str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM app_settings")
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

    def get_unit_preference(self, fallback: str = "lbs") -> str:
        return self.get_setting("default_unit_preference", fallback)

    def set_unit_preference(self, unit: str):
        self.set_setting("default_unit_preference", unit, "Weight unit preference (lbs or kg)")
