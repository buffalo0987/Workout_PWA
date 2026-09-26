#!/usr/bin/env python3
import os
import sys
import unittest
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.init_db import init_database
import backend.app.controllers as controllers
from src.models.settings import SettingsRepository

TEST_DB = "test_settings_routines.db"

class TestSettingsAndRoutines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        init_database(TEST_DB)
        controllers.DB_PATH = TEST_DB

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_settings_get_and_update(self):
        # Test initial defaults
        settings = controllers.get_app_settings()
        self.assertIn("ollama_base_url", settings)
        self.assertIn("sparky_base_url", settings)
        self.assertEqual(settings["active_model"], "qwen3:14b")

        # Update settings (custom IP and token)
        updated = controllers.update_app_settings({
            "ollama_base_url": "http://192.168.1.100:11434",
            "sparky_base_url": "http://192.168.1.200:8080",
            "sparky_api_token": "secret_token_abc_123",
            "selected_ollama_model": "gemma4:12b"
        })
        self.assertEqual(updated["ollama_base_url"], "http://192.168.1.100:11434")
        self.assertEqual(updated["sparky_base_url"], "http://192.168.1.200:8080")
        self.assertEqual(updated["sparky_api_token"], "secret_token_abc_123")
        self.assertEqual(updated["active_model"], "gemma4:12b")

    def test_routines_creation_and_listing(self):
        # Create exercise
        ex = controllers.create_exercise({"name": "Leg Extension", "category": "machine", "primary_muscle": "quadriceps"})

        # Create routine
        controllers.create_routine({
            "title": "Quad Focus Routine",
            "description": "Hypertrophy quad routine",
            "schedule_days": ["Mon", "Wed"],
            "exercises": [{"exercise_id": ex["id"], "target_sets": 4, "min_reps": 10, "max_reps": 15}]
        })

        routines = controllers.list_routines()
        self.assertGreaterEqual(len(routines), 1)
        r = routines[0]
        self.assertEqual(r["title"], "Quad Focus Routine")
        self.assertEqual(r["schedule_days"], ["Mon", "Wed"])
        self.assertEqual(len(r["exercises"]), 1)
        self.assertEqual(r["exercises"][0]["exercise_name"], "Leg Extension")

if __name__ == "__main__":
    unittest.main()
