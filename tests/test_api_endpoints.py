#!/usr/bin/env python3
"""
Unit and API Integration Tests for HTTP Endpoints:
1. Exercise CRUD (GET & POST /api/exercises)
2. Workout Session & Set Logging (POST /api/workouts/sessions, POST & GET /api/workouts/sets)
3. Progressive Overload Suggestion (POST /api/workouts/suggest)
4. Weekly Coaching Feedback (POST /api/coaching/feedback)
"""

import os
import sys
import json
import unittest
import threading
from http.client import HTTPConnection
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.init_db import init_database
import backend.app.controllers as controllers
from backend.app.server import run_server
from http.server import HTTPServer
from backend.app.server import WorkoutAPIRequestHandler

TEST_DB_PATH = "test_server_api.db"
TEST_PORT = 8999

class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        init_database(TEST_DB_PATH)
        controllers.DB_PATH = TEST_DB_PATH

        cls.httpd = HTTPServer(("127.0.0.1", TEST_PORT), WorkoutAPIRequestHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def _request(self, method, path, body=None):
        conn = HTTPConnection("127.0.0.1", TEST_PORT)
        headers = {"Content-Type": "application/json"} if body else {}
        data = json.dumps(body) if body else None
        conn.request(method, path, body=data, headers=headers)
        res = conn.getresponse()
        res_data = res.read().decode("utf-8")
        conn.close()
        return res.status, json.loads(res_data) if res_data else {}

    def test_01_exercise_crud(self):
        # Create exercise
        status, body = self._request("POST", "/api/exercises", {
            "name": "Overhead Press",
            "category": "barbell",
            "primary_muscle": "shoulders"
        })
        self.assertEqual(status, 201)
        self.assertIn("id", body)
        self.assertEqual(body["name"], "Overhead Press")

        # List exercises
        status, body = self._request("GET", "/api/exercises")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["count"], 1)

    def test_02_workout_session_and_set_logging(self):
        # Create session
        status, session = self._request("POST", "/api/workouts/sessions", {
            "name": "Push Day B",
            "status": "in_progress"
        })
        self.assertEqual(status, 201)
        self.assertIn("id", session)

        # Get exercise ID
        _, ex_res = self._request("GET", "/api/exercises")
        exercise_id = ex_res["data"][0]["id"]

        # Log set
        status, logged_set = self._request("POST", "/api/workouts/sets", {
            "workout_session_id": session["id"],
            "exercise_id": exercise_id,
            "set_number": 1,
            "weight": 50.0,
            "reps": 8,
            "rpe": 8.0
        })
        self.assertEqual(status, 201)
        self.assertEqual(logged_set["weight"], 50.0)

        # List sets for session
        status, sets_res = self._request("GET", f"/api/workouts/sets?session_id={session['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(sets_res["count"], 1)

    def test_03_workouts_suggest_endpoint(self):
        _, ex_res = self._request("GET", "/api/exercises")
        exercise_id = ex_res["data"][0]["id"]

        # Call /api/workouts/suggest
        status, res = self._request("POST", "/api/workouts/suggest", {
            "exercise_ids": [exercise_id]
        })
        self.assertEqual(status, 200)
        self.assertIn("suggestions", res)
        self.assertIn("nutrition_averages", res)
        self.assertEqual(len(res["suggestions"]), 1)
        sugg = res["suggestions"][0]
        self.assertIn("suggested_weight", sugg)
        self.assertIn("target_reps", sugg)
        self.assertIn("strategy", sugg)

    def test_04_coaching_feedback_endpoint(self):
        status, res = self._request("POST", "/api/coaching/feedback", {})
        self.assertEqual(status, 200)
        self.assertIn("insights", res)
        self.assertIsInstance(res["insights"], list)
        self.assertEqual(len(res["insights"]), 3, "Must return exactly 3 structured bullet insights")
        self.assertIn("weekly_metrics", res)

if __name__ == "__main__":
    unittest.main()
