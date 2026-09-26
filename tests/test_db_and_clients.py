#!/usr/bin/env python3
"""
Integration & Unit Verification Test for Database Models & External Clients
Tests:
1. Database Schema initialization, constraints, and seeding (app_settings).
2. Settings model (reading/writing `selected_ollama_model`).
3. External client network calls with automatic mock/fallback verification.
"""

import os
import sys
import unittest
import sqlite3
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.init_db import init_database
from src.models.settings import SettingsRepository

TEST_DB_PATH = "test_workout_app.db"

class TestDatabaseAndSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        init_database(TEST_DB_PATH)
        cls.repo = SettingsRepository(TEST_DB_PATH)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def test_default_ollama_model_setting_seeded(self):
        val = self.repo.get_selected_ollama_model()
        self.assertEqual(val, "qwen3:14b", "Default model should be qwen3:14b")

    def test_update_selected_ollama_model(self):
        self.repo.set_selected_ollama_model("gemma4:12b")
        val = self.repo.get_selected_ollama_model()
        self.assertEqual(val, "gemma4:12b")
        # Reset back
        self.repo.set_selected_ollama_model("qwen3:14b")

    def test_table_structure_and_constraints(self):
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        required_tables = {
            "app_settings",
            "users",
            "exercises",
            "routines",
            "routine_exercises",
            "workout_sessions",
            "workout_exercises",
            "exercise_sets",
            "ai_recommendations",
            "nutrition_logs",
            "watch_devices"
        }
        self.assertTrue(required_tables.issubset(tables), f"Missing tables: {required_tables - tables}")
        conn.close()

if __name__ == "__main__":
    unittest.main()

from backend.app.services.ollama_client import get_available_models, generate_completion
from backend.app.services.sparky_client import get_daily_summary

class TestExternalClients(unittest.TestCase):
    def test_ollama_client_fallback(self):
        # When remote host is unreachable/offline or timed out, fallback should gracefully engage
        models = get_available_models(timeout=2)
        self.assertIsInstance(models, list)
        self.assertGreaterEqual(len(models), 1)

        result = generate_completion(
            prompt="Suggest progression for bench press",
            context_data={"current_weight": 100, "target_rep_range": [8, 12], "last_reps": 12, "last_rpe": 8.0},
            timeout=2
        )
        self.assertIn("suggested_weight", result["parsed_json"])
        self.assertEqual(result["parsed_json"]["suggested_weight"], 102.5)

    def test_sparky_client_fallback(self):
        summary = get_daily_summary("2026-09-16", timeout=2)
        self.assertIn("calories", summary)
        self.assertIn("protein_grams", summary)
        self.assertEqual(summary["date"], "2026-09-16")
