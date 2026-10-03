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

    def test_routine_update_and_ai_actions(self):
        # 1. Create a routine with Barbell Bench Press
        bb_bench = controllers.create_exercise({"name": "Barbell Bench Press", "category": "barbell", "primary_muscle": "pectorals"})
        db_bench = controllers.create_exercise({"name": "Dumbbell Bench Press", "category": "dumbbell", "primary_muscle": "pectorals"})

        rt_list = controllers.create_routine({
            "user_id": "test_user_ai",
            "title": "Chest Power",
            "description": "Heavy bench focus",
            "schedule_days": ["Monday"],
            "exercises": [{"exercise_id": bb_bench["id"], "target_sets": 3, "min_reps": 6, "max_reps": 8}]
        })
        user_rts = [r for r in controllers.list_routines("test_user_ai") if r["title"] == "Chest Power"]
        self.assertEqual(len(user_rts), 1)
        orig_id = user_rts[0]["id"]
        self.assertEqual(user_rts[0]["exercises"][0]["exercise_name"], "Barbell Bench Press")

        # 2. Test execute_routine_actions with routines_to_update (e.g. swap barbell for dumbbell)
        update_payload = {
            "routines_to_update": [
                {
                    "id": orig_id,
                    "title": "Chest Power",
                    "exercises": [
                        {"name": "Dumbbell Bench Press", "target_sets": 3, "min_reps": 8, "max_reps": 12, "rest_seconds": 90}
                    ]
                }
            ]
        }
        res = controllers.execute_routine_actions("test_user_ai", update_payload)
        self.assertEqual(res["routines_updated"], 1)
        self.assertEqual(res["routines_created"], 0)

        # Verify existing routine was modified in-place and schedule days preserved
        updated_rts = [r for r in controllers.list_routines("test_user_ai") if r["title"] == "Chest Power"]
        self.assertEqual(len(updated_rts), 1) # Still only 1 routine, not duplicated!
        self.assertEqual(updated_rts[0]["id"], orig_id)
        self.assertEqual(updated_rts[0]["schedule_days"], ["Monday"])
        self.assertEqual(updated_rts[0]["exercises"][0]["exercise_name"], "Dumbbell Bench Press")

        # 3. Test duplicate collision protection: If AI Coach mistakenly uses routines_to_create with existing title
        collision_payload = {
            "routines_to_create": [
                {
                    "title": "Chest Power",
                    "exercises": [
                        {"name": "Incline Dumbbell Press", "target_sets": 4, "min_reps": 10, "max_reps": 12, "rest_seconds": 75}
                    ]
                }
            ]
        }
        res2 = controllers.execute_routine_actions("test_user_ai", collision_payload)
        self.assertEqual(res2["routines_updated"], 1)
        self.assertEqual(res2["routines_created"], 0)

        # Verify it updated the existing routine instead of creating a second duplicate "Chest Power"
        collision_rts = [r for r in controllers.list_routines("test_user_ai") if r["title"] == "Chest Power"]
        self.assertEqual(len(collision_rts), 1)
        self.assertEqual(collision_rts[0]["id"], orig_id)
        self.assertEqual(collision_rts[0]["exercises"][0]["exercise_name"], "Incline Dumbbell Press")

if __name__ == "__main__":
    unittest.main()
